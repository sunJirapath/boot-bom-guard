"""Run reviewed public builds only inside resource-limited Docker containers."""
import argparse
import concurrent.futures
import difflib
import json
from pathlib import Path
import re
import subprocess
import time
import threading
import xml.etree.ElementTree as ET
from campaign import HERE, WORK, PILOT, catalog, execute, strip_ns, write_results

MAVEN_IMAGE = 'maven@sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320'
GRADLE_IMAGE = 'gradle@sha256:21bd311ed01360c189b8870c6b6e988199ff10f72d445d02fb39d3cff9da91d7'
GOAL = 'io.github.bootbomguard:boot-bom-guard-maven-plugin:0.1.0-SNAPSHOT:check'
TREE = 'org.apache.maven.plugins:maven-dependency-plugin:3.10.0:tree'
HELP = 'org.apache.maven.plugins:maven-help-plugin:3.5.1:effective-pom'
GRADLE_LOCK = threading.Lock()
SELECT = {
    1: ('Maven', 'pom.xml'), 2: ('Maven', 'pom.xml'), 3: ('Gradle', 'build.gradle'),
    9: ('Gradle', 'build.gradle.kts'), 26: ('Maven', 'pom.xml'), 27: ('Maven', 'pom.xml'),
    40: ('Gradle', 'build.gradle.kts'), 41: ('Gradle', 'build.gradle'),
    51: ('Maven', 'spring-petclinic-customers-service/pom.xml'),
    57: ('Maven', 'pom.xml'), 62: ('Gradle', 'build.gradle'),
    68: ('Maven', 'spring-boot/pom.xml'), 76: ('Maven', 'pom.xml'),
    77: ('Maven', 'spring-boot-admin-client/pom.xml'), 92: ('Gradle', 'build.gradle'),
    95: ('Maven', 'pom.xml'),
}
SELECT.update({5: ('Maven', 'complete/pom.xml'), 6: ('Maven', 'complete/pom.xml'),
               7: ('Maven', 'complete/pom.xml'), 36: ('Gradle', 'use-cases/chatbot/build.gradle'),
               57: ('Maven', 'lab-01-spring-security/lab-01-springsecurity-demo/pom.xml'),
               76: ('Maven', 'tests/camel-itest-spring-boot/pom.xml'),
               95: ('Maven', 'integration-tests/integration-tests-class-instance-loader/integration-tests-class-instance-loader-spring/pom.xml')})
SELECT.update({62: ('Gradle', 'order-service/order-service-main/build.gradle'),
               63: ('Gradle', 'order-service/order-service-main/build.gradle')})


def load(num):
    path = HERE / 'evidence' / f'{num:03d}'
    return json.loads((path / 'inventory.json').read_text(encoding='utf-8')), path


def container(row, evidence, label, command, tool='Maven', timeout=180, network=True):
    name = f"bbg-137b-{row['id']}-{label}".lower().replace('_', '-')[:100]
    image = MAVEN_IMAGE if tool == 'Maven' else GRADLE_IMAGE
    args = ['docker', 'run', '--rm', '--name', name, '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '3g', '--cpus', '2', '--pids-limit', '512',
            '--mount', f"type=bind,source={row['clone_path']},target=/work", '-w', '/work', '-e', 'CI=true']
    if not network:
        args += ['--network', 'none']
    if tool == 'Maven':
        args += ['--mount', 'type=volume,source=bbg-campaign-m2-137b,target=/root/.m2', '-e', 'MAVEN_OPTS=-Xmx2g']
    else:
        args += ['--mount', f'type=volume,source={row.get("gradle_cache", "bbg-campaign-gradle-137b")},target=/cache', '-e', 'GRADLE_USER_HOME=/cache', '--mount', f'type=bind,source={row.get("guard_path", str(WORK / "guard"))},target=/guard', '--mount', 'type=volume,source=bbg-campaign-toolchains-137b,target=/toolchains,readonly']
    args += [image] + command
    code, duration, output = execute(args, HERE, evidence / (label + '.log'), timeout=timeout)
    if code == 124:
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    return dict(label=label, exit=code, elapsed_s=duration), output


def maven(pom, goals, flags=()):
    return ['mvn', '-B', '-ntp', '-N', '-f', '/work/' + pom,
            '-Daether.connector.connectTimeout=10000', '-Daether.connector.requestTimeout=20000'] + goals + list(flags)


def save(row, evidence, runs):
    (evidence / 'runs.json').write_text(json.dumps(runs, indent=2), encoding='utf-8')
    (evidence / 'result.json').write_text(json.dumps(row, indent=2), encoding='utf-8')


def selected(num, row):
    if num in SELECT:
        return SELECT[num]
    builds = [b for b in row.get('builds', []) if Path(b['path']).name.startswith('build.gradle') or b['path'].endswith('pom.xml')]
    if not builds:
        return '', ''
    def rank(b):
        boot = str(b['boot'])
        return (not bool(re.search(r'[\'\"]4\.', boot)), not bool(b['boot']), b['path'].count('/'), b['path'])
    first = min(builds, key=rank)
    if first['tool'] == 'Maven':
        root = Path(row['clone_path'])
        try:
            project = strip_ns(ET.fromstring((root / first['path']).read_bytes()))
            if project.findtext('packaging', 'jar') == 'pom':
                leaves = []
                for b in builds:
                    if b['tool'] != 'Maven':
                        continue
                    try:
                        ep = strip_ns(ET.fromstring((root / b['path']).read_bytes()))
                    except ET.ParseError:
                        continue
                    if ep.findtext('packaging', 'jar') != 'pom':
                        boot_deps = sum(d.findtext('groupId') == 'org.springframework.boot' for d in ep.findall('./dependencies/dependency'))
                        leaves.append((boot_deps, len(ep.findall('./dependencies/dependency')), -b['path'].count('/'), b['path']))
                if leaves:
                    return 'Maven', max(leaves)[-1]
        except ET.ParseError:
            pass
    return first['tool'], first['path']


def maven_baseline(row, evidence, pom):
    scratch = Path(row['clone_path']) / '.bbg'
    scratch.mkdir(exist_ok=True)
    run, out = container(row, evidence, 'baseline', maven(pom, [HELP, TREE], ['-Doutput=/work/.bbg/effective.xml', '-DoutputFile=/work/.bbg/tree.json', '-DoutputType=json']))
    runs = [run]
    if run['exit']:
        row.update(baseline_status='TIMEOUT' if run['exit'] == 124 else 'FAILED', outcome='ENV_BLOCKED' if run['exit'] == 124 or 'Non-resolvable parent' in out or 'Non-resolvable import POM' in out or 'Could not transfer' in out else 'BASELINE_BROKEN', scenario='unmodified-resolution', elapsed_s=run['elapsed_s'])
        save(row, evidence, runs)
        return
    effective = scratch / 'effective.xml'
    tree = scratch / 'tree.json'
    if not effective.exists() or not tree.exists():
        row.update(baseline_status='NO_ORACLE_OUTPUT', outcome='ENV_BLOCKED')
        save(row, evidence, runs)
        return
    ep = strip_ns(ET.fromstring(effective.read_bytes()))
    tree_data = json.loads(tree.read_text())
    (evidence / 'effective.xml').write_bytes(effective.read_bytes())
    (evidence / 'tree.json').write_bytes(tree.read_bytes())
    props = {e.tag: e.text for e in ep.findall('./properties/*')}
    row.update(baseline_status='RESOLUTION_PASSED', module_count=1 + len(ep.findall('./modules/module')), jdk=props.get('java.version', props.get('maven.compiler.release', '21 runtime')), scenario='original-warning-strict', elapsed_s=run['elapsed_s'])
    row['native_graph_nodes'] = len(flatten_tree(tree_data))
    run, out = container(row, evidence, 'original-warning', maven(pom, [GOAL]))
    runs.append(run)
    row['guard_warn_exit'] = run['exit']
    boot = re.search(r'BOM=org.springframework.boot:spring-boot-dependencies:([^\s]+)', out)
    row['boot_version'] = boot.group(1) if boot else 'unknown'
    row['bom_mechanism'] = 'Maven effective dependencyManagement provenance'
    counts = re.findall(r'(?:PASS|WARN) checked=(\d+) drift=(\d+) unknown=(\d+)', out)
    if counts:
        row.update(checked=int(counts[-1][0]), drift_count=int(counts[-1][1]), unknown_count=int(counts[-1][2]))
    run, strict_out = container(row, evidence, 'original-strict', maven(pom, [GOAL], ['-DbootBomGuard.failOnDrift=true']))
    runs.append(run)
    row['guard_strict_exit'] = run['exit']
    if 'Unsupported Spring Boot BOM' in out or 'Missing Spring Boot BOM' in out:
        row['outcome'] = 'EXPECTED_UNSUPPORTED' if row['guard_warn_exit'] == 0 and row['guard_strict_exit'] != 0 else 'SUSPECTED_LIB_BUG'
    elif row.get('unknown_count', 1):
        row['outcome'] = 'ENV_BLOCKED'
    elif row.get('drift_count', 0):
        row['outcome'] = 'NOT_RUN'  # Attribution remains pending until the independent oracle runs.
        row['oracle_status'] = 'PENDING_PRISTINE_BOM_COMPARISON'
    elif row.get('checked', 0):
        row['outcome'] = 'NOT_RUN'
        row['oracle_status'] = 'PENDING_PRISTINE_BOM_COMPARISON'
    else:
        row['outcome'] = 'EXPECTED_UNSUPPORTED'
        row['boundary'] = 'No comparable Boot-managed resolved libraries in selected module'
    save(row, evidence, runs)
    print(f"{row['id']:03d} {row['repo']} baseline={row['baseline_status']} outcome={row['outcome']} boot={row['boot_version']} graph={row['native_graph_nodes']}", flush=True)


def flatten_tree(node):
    return [node] + [n for child in node.get('children', []) for n in flatten_tree(child)]


def gradle_baseline(row, evidence, build):
    root = Path(build).parent.as_posix()
    base = ['gradle', '--no-daemon', '--console=plain', '--max-workers=2', '-Dorg.gradle.jvmargs=-Xmx1536m', '-Porg.gradle.java.installations.paths=/toolchains/jdk17,/toolchains/jdk25', '-p', '/work/' + root]
    run, out = container(row, evidence, 'baseline', base + ['dependencies', '--configuration', 'runtimeClasspath'], tool='Gradle', timeout=240)
    runs = [run]
    if run['exit'] or re.search(r'\bFAILED\b', out):
        row.update(baseline_status='TIMEOUT' if run['exit'] == 124 else 'FAILED_OR_INCOMPLETE', outcome='ENV_BLOCKED', scenario='unmodified-resolution', elapsed_s=run['elapsed_s'])
        save(row, evidence, runs)
        print(f"{row['id']:03d} Gradle baseline blocked", flush=True)
        return
    row.update(baseline_status='RESOLUTION_PASSED', scenario='original-warning-strict', elapsed_s=run['elapsed_s'])
    build_path = Path(row['clone_path']) / build
    kotlin = build_path.name.endswith('.kts')
    settings = build_path.parent / ('settings.gradle.kts' if kotlin else 'settings.gradle')
    alternative = build_path.parent / ('settings.gradle' if kotlin else 'settings.gradle.kts')
    if alternative.exists() and not settings.exists():
        settings = alternative
    before_settings = settings.read_bytes() if settings.exists() else None
    before_build = build_path.read_bytes()
    settings_text = (before_settings or b'').decode('utf-8')
    statement = '\n    includeBuild("/guard")\n'
    if re.search(r'pluginManagement\s*\{', settings_text):
        settings_text = re.sub(r'(pluginManagement\s*\{)', lambda m: m.group(1) + statement, settings_text, count=1)
    else:
        settings_text = 'pluginManagement {' + statement + '}\n' + settings_text
    build_text = before_build.decode('utf-8')
    plugin = '\n    id("io.github.bootbomguard")\n' if kotlin else "\n    id 'io.github.bootbomguard'\n"
    if not re.search(r'plugins\s*\{', build_text):
        row.update(outcome='ENV_BLOCKED', boundary='No safe automatic root plugins block; manual integration required')
        save(row, evidence, runs)
        return
    build_text = re.sub(r'(plugins\s*\{)', lambda m: m.group(1) + plugin, build_text, count=1)
    build_text += '\nbootBomGuard { failOnDrift.set(providers.gradleProperty("auditStrict").map { it.toBoolean() }.getOrElse(false)) }\n'
    diff = ''.join(difflib.unified_diff(before_build.decode().splitlines(True), build_text.splitlines(True), fromfile=build, tofile=build))
    diff += ''.join(difflib.unified_diff((before_settings or b'').decode().splitlines(True), settings_text.splitlines(True), fromfile=settings.name, tofile=settings.name))
    (evidence / 'integration.patch').write_text(diff, encoding='utf-8')
    try:
        build_path.write_bytes(build_text.encode())
        settings.write_bytes(settings_text.encode())
        for label, flags in [('original-warning', []), ('original-strict', ['-PauditStrict=true'])]:
            run, report = container(row, evidence, label, base + ['bootBomGuard'] + flags, tool='Gradle', timeout=240)
            runs.append(run)
            if label.endswith('warning'):
                out = report
                row['guard_warn_exit'] = run['exit']
            else:
                row['guard_strict_exit'] = run['exit']
        counts = re.findall(r'(?:PASS|WARN) checked=(\d+) drift=(\d+) unknown=(\d+)', out)
        row.update(drift_count=sum(int(x[1]) for x in counts), unknown_count=sum(int(x[2]) for x in counts))
        row['outcome'] = 'EXPECTED_UNSUPPORTED' if counts and ('Missing Spring Boot BOM' in out or 'Unsupported Spring Boot BOM' in out) and row['guard_warn_exit'] == 0 and row['guard_strict_exit'] != 0 else 'ENV_BLOCKED'
        row['bom_mechanism'] = 'Spring dependency-management DSL' if 'io.spring.dependency-management' in build_text else 'see native graph'
    finally:
        build_path.write_bytes(before_build)
        if before_settings is None:
            settings.unlink(missing_ok=True)
        else:
            settings.write_bytes(before_settings)
    save(row, evidence, runs)
    print(f"{row['id']:03d} {row['repo']} {row['outcome']}", flush=True)


def baseline(num):
    row, evidence = load(num)
    if not row.get('clone_path'):
        return
    tool, build = selected(num, row)
    row.update(build_tool=tool, build_root=build, tier_measured='UNMEASURED')
    if not build or not (Path(row['clone_path']) / build).exists():
        row.update(outcome='ENV_BLOCKED', boundary='No selected build file; manual inspection required')
        save(row, evidence, [])
        return
    if tool == 'Maven':
        maven_baseline(row, evidence, build)
    else:
        # Separate Docker PID namespaces cannot coordinate Gradle's shared journal lock.
        with GRADLE_LOCK:
            gradle_baseline(row, evidence, build)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['pilot', 'baselines'])
    parser.add_argument('--ids', nargs='*', type=int)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    ids = args.ids or sorted(PILOT if args.action == 'pilot' else {r['id'] for r in catalog()})
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(baseline, ids))
    write_results()
