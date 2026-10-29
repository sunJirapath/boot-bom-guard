"""Separate native-platform experiment on unchanged Boot versions; retain DSL."""
import argparse
import difflib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from campaign import WORK
from run_builds import container, load
from oracle import findings

INIT = '''import groovy.json.JsonOutput
import org.gradle.api.artifacts.component.ModuleComponentIdentifier
import org.gradle.api.artifacts.component.ModuleComponentSelector
import org.gradle.api.artifacts.result.ResolvedDependencyResult
import org.gradle.api.artifacts.result.UnresolvedDependencyResult
import org.gradle.api.attributes.Category
allprojects {
  tasks.register('bbgNativeOracle') {
    doLast {
      def result = [:]
      ['compileClasspath','runtimeClasspath','testCompileClasspath','testRuntimeClasspath'].each { name ->
        def c = configurations.findByName(name)
        if (c != null && c.canBeResolved) {
          def rr = c.incoming.resolutionResult
          def edges = rr.allDependencies
          def modules = rr.allComponents.findAll { it.id instanceof ModuleComponentIdentifier }.collect { n ->
            def library = edges.any { e ->
              if (!(e instanceof ResolvedDependencyResult) || e.constraint || e.selected != n) return false
              def category = e.resolvedVariant.attributes.getAttribute(Category.CATEGORY_ATTRIBUTE)?.name
              return !(category in ['platform','enforced-platform'])
            }
            [key:n.id.group+':'+n.id.module,version:n.id.version,library:library,reason:n.selectionReason.toString()]
          }
          def constraints = edges.findAll { it.constraint && it.requested instanceof ModuleComponentSelector }.collect { it.requested.group+':'+it.requested.module }.unique().sort()
          def unresolved = edges.findAll { it instanceof UnresolvedDependencyResult }.collect { it.requested.displayName }
          result[name] = [modules:modules,constraints:constraints,unresolved:unresolved]
        }
      }
      def output = file('.bbg/gradle-native.json'); output.parentFile.mkdirs()
      output.text = JsonOutput.prettyPrint(JsonOutput.toJson(result))
      println 'BBG_NATIVE_ORACLE_WRITTEN '+output
    }
  }
}
'''


def guard_reports(output):
    return {m[0]: m[1] for m in re.findall(r'^configuration=(\w+)\n(.*?)(?=^configuration=|\Z)', output, re.M | re.S)}


def check(native, pristine, output, allowed=False, expect_unknown=False):
    reports = guard_reports(output)
    result = {}
    for config, graph in native.items():
        expected = {n['key']: n['version'] for n in pristine[config]['modules'] if n['key'] in pristine[config]['constraints']}
        actual = {n['key']: n['version'] for n in graph['modules'] if n['library']}
        drift = {k: dict(expected=expected[k], resolved=v) for k, v in actual.items() if k in expected and expected[k] != v}
        reported = findings(reports.get(config, ''))
        mismatch = drift.keys() != reported.keys() or any(any(drift[k][f] != reported[k][f] for f in ['expected','resolved']) for k in drift.keys() & reported.keys())
        unknown = bool(graph['unresolved']) or expect_unknown
        counts = re.search(r'(PASS|WARN) checked=(\d+) drift=(\d+) unknown=(\d+)', reports.get(config, ''))
        if not counts or (unknown and int(counts[4]) == 0):
            mismatch = True
        remaining = set(drift) - ({'org.slf4j:slf4j-api'} if allowed else set())
        result[config] = dict(expected_drift=drift, reported=reported, mismatch=mismatch, should_fail=bool(remaining) or unknown, counts=counts.groups() if counts else None)
    return result


def audit(num):
    row, evidence = load(num)
    row.update(gradle_cache='bbg-campaign-gradle-audit-137b', guard_path=str(WORK / 'guard-audit'))
    root = Path(row['clone_path'])
    kotlin = num == 40
    name = 'build.gradle.kts' if kotlin else 'build.gradle'
    build, settings = root / name, root / ('settings.gradle.kts' if kotlin else 'settings.gradle')
    original, original_settings = build.read_bytes(), settings.read_bytes() if settings.exists() else None
    text, setting_text = original.decode(), (original_settings or b'').decode()
    plugin = '\n    id("io.github.bootbomguard")\n' if kotlin else "\n    id 'io.github.bootbomguard'\n"
    integrated = re.sub(r'(plugins\s*\{)', lambda m: m[1]+plugin, text, count=1)
    integrated += '\nbootBomGuard { failOnDrift.set(providers.gradleProperty("auditStrict").map { it.toBoolean() }.getOrElse(false)) }\n'
    if re.search(r'pluginManagement\s*\{', setting_text):
        setting_text = re.sub(r'(pluginManagement\s*\{)', lambda m: m[1]+' includeBuild("/guard")\n', setting_text, count=1)
    else:
        setting_text = 'pluginManagement { includeBuild("/guard") }\n' + setting_text
    version = '4.0.1' if kotlin else '4.0.0'
    platform = f'\ndependencies {{ implementation(platform("org.springframework.boot:spring-boot-dependencies:{version}")) }}\n'
    metadata = ET.fromstring((evidence.parent / '002/alternate-metadata.log').read_text())
    candidates = [x.text for x in metadata.findall('./versioning/versions/version') if re.fullmatch(r'2\.0\.\d+', x.text or '')]
    alternate = max(candidates, key=lambda x: tuple(map(int,x.split('.'))))
    mutation = f'\ndependencies {{ implementation("org.slf4j:slf4j-api:{alternate}") }}\n'
    cases = [('platform', ''), ('direct', mutation)]
    if not kotlin:
        cases += [('constraint', f'\ndependencies {{ constraints {{ implementation("org.slf4j:slf4j-api:{alternate}") }} }}\n'),
                  ('dsl-managed', f'\next["slf4j.version"] = "{alternate}"\n'),
                  ('allowed', mutation+'\nbootBomGuard { exceptions.put("org.slf4j:slf4j-api", "Campaign intentional exception") }\n'),
                  ('forced', f'\nconfigurations.configureEach {{ resolutionStrategy.force("org.slf4j:slf4j-api:{alternate}") }}\n'),
                  ('incomplete', '\ndependencies { implementation("guard.audit:deliberately-missing:1") }\n')]
    scratch = root / '.bbg'
    scratch.mkdir(exist_ok=True)
    (scratch / 'native.init.gradle').write_text(INIT, newline='')
    base = ['gradle','--no-daemon','--console=plain','--max-workers=2','-Dorg.gradle.jvmargs=-Xmx1536m','-Porg.gradle.java.installations.paths=/toolchains/jdk17,/toolchains/jdk25','-I','/work/.bbg/native.init.gradle','-p','/work']
    results=[]
    try:
        # Read every original classpath before adding the platform or guard.
        run, log = container(row, evidence, 'native-original-all', base+['bbgNativeOracle'], tool='Gradle', timeout=240)
        if run['exit']:
            (evidence/'gradle-audit.json').write_text(json.dumps(dict(blocked=run),indent=2))
            return
        (evidence/'gradle-native-original.json').write_bytes((scratch/'gradle-native.json').read_bytes())
        settings.write_bytes(setting_text.encode())
        for case, addition in cases:
            variant = integrated + platform + addition
            build.write_bytes(variant.encode())
            diff = ''.join(difflib.unified_diff(original.decode().splitlines(True),variant.splitlines(True),fromfile=name,tofile=name))
            diff += ''.join(difflib.unified_diff((original_settings or b'').decode().splitlines(True),setting_text.splitlines(True),fromfile=settings.name,tofile=settings.name))
            (evidence/f'platform-{case}.patch').write_text(diff, newline='')
            offline = ['--offline'] if case == 'incomplete' else []
            runs=[]
            run, output = container(row,evidence,'platform-'+case+'-warning',base+['bbgNativeOracle','bootBomGuard']+offline,tool='Gradle',timeout=240,network=case!='incomplete')
            runs.append(run)
            if run['exit']:
                results.append(dict(scenario=case,blocked=run));continue
            data = (scratch/'gradle-native.json').read_bytes()
            native = json.loads(data)
            (evidence/f'platform-{case}-native.json').write_bytes(data)
            # A separate clean Gradle project has no consumer plugins, rules, forces or properties.
            clean = scratch/'pristine-gradle';clean.mkdir(exist_ok=True)
            (clean/'settings.gradle').write_text("rootProject.name='bbg-pristine'\n",newline='')
            keys = sorted({n['key'] for g in native.values() for n in g['modules'] if n['library']})
            requests = '\n'.join(f' implementation("{key}") {{ transitive = false }}' for key in keys)
            (clean/'build.gradle').write_text("plugins { id 'java' }\nrepositories { mavenCentral() }\ndependencies {\n"+f' implementation(platform("org.springframework.boot:spring-boot-dependencies:{version}"))\n'+requests+'\n}\n',newline='')
            pristine_base=base[:-1]+['/work/.bbg/pristine-gradle']
            oracle_run, oracle_output=container(row,evidence,'platform-'+case+'-pristine',pristine_base+['bbgNativeOracle'],tool='Gradle',timeout=240)
            runs.append(oracle_run)
            if oracle_run['exit']:
                results.append(dict(scenario=case,blocked=oracle_run));continue
            pristine=json.loads((clean/'.bbg/gradle-native.json').read_text())
            (evidence/f'platform-{case}-pristine.json').write_text(json.dumps(pristine,indent=2))
            native_check=check(native,pristine,output,allowed=case=='allowed')
            run, strict=container(row,evidence,'platform-'+case+'-strict',base+['bootBomGuard','-PauditStrict=true']+offline,tool='Gradle',timeout=240,network=case!='incomplete')
            runs.append(run)
            should_fail=any(x['should_fail'] for x in native_check.values())
            result=dict(scenario=case,alternate=alternate,runs=runs,oracle=native_check,verified=not any(x['mismatch'] for x in native_check.values()) and bool(run['exit'])==should_fail)
            results.append(result)
            (evidence/'gradle-audit.json').write_text(json.dumps(results,indent=2))
            print(f'{num:03d} Gradle platform/{case} verified={result["verified"]}',flush=True)
    finally:
        build.write_bytes(original)
        if original_settings is None:settings.unlink(missing_ok=True)
        else:settings.write_bytes(original_settings)
        (evidence/'gradle-audit.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ids',nargs='*',type=int,default=[3,40]);args=parser.parse_args()
    assert guard_reports('configuration=runtimeClasspath\nPASS checked=1 drift=0 unknown=0')['runtimeClasspath'].startswith('PASS')
    for num in args.ids:audit(num)
