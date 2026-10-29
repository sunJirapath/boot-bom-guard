"""Controlled subproject experiments, keeping the real root build intact."""
import json
from pathlib import Path
import re
import shutil
from campaign import HERE, WORK
from run_builds import load, container
from audit_gradle import INIT, check

def main():
    row,e=load(3);root=Path(row['clone_path'])
    row.update(gradle_cache='bbg-campaign-gradle-audit-137b',guard_path=str(WORK/'guard-audit'))
    settings=root/'settings.gradle';original=settings.read_bytes()
    integrated='pluginManagement { includeBuild("/guard") }\n'+original.decode()+"\ninclude(':bbgAudit', ':bbgBridge')\n"
    leaf=root/'bbgAudit';bridge=root/'bbgBridge'
    assert not leaf.exists() and not bridge.exists()
    leaf.mkdir();bridge.mkdir()
    (root/'.bbg/native.init.gradle').write_text(INIT,newline='')
    (bridge/'build.gradle').write_text("plugins { id 'java-library' }\nrepositories { mavenCentral() }\ndependencies { api('org.slf4j:slf4j-api:2.0.20') }\n",newline='')
    base=['gradle','--no-daemon','--console=plain','--max-workers=2','-Dorg.gradle.jvmargs=-Xmx1536m','-I','/work/.bbg/native.init.gradle','-p','/work','--offline']
    preamble="plugins { id 'java'; id 'io.github.bootbomguard' }\nrepositories { mavenCentral() }\nbootBomGuard { failOnDrift.set(providers.gradleProperty('auditStrict').map { it.toBoolean() }.getOrElse(false)) }\n"
    expected=json.loads((e/'platform-platform-pristine.json').read_text())
    cases=[
        ('direct',"implementation(platform('org.springframework.boot:spring-boot-dependencies:4.0.0')); implementation('org.slf4j:slf4j-api:2.0.20')",'', 'DIRECT_OVERRIDE'),
        ('constraint',"implementation(platform('org.springframework.boot:spring-boot-dependencies:4.0.0')); implementation('org.slf4j:slf4j-api'); constraints { implementation('org.slf4j:slf4j-api:2.0.20') }",'','MANAGED_OVERRIDE'),
        ('transitive',"implementation(platform('org.springframework.boot:spring-boot-dependencies:4.0.0')); implementation(project(':bbgBridge'))",'','TRANSITIVE_DRIFT'),
        ('enforced',"implementation(enforcedPlatform('org.springframework.boot:spring-boot-dependencies:4.0.0')); implementation('org.slf4j:slf4j-api:2.0.20')",'',None),
        ('forced',"implementation(platform('org.springframework.boot:spring-boot-dependencies:4.0.0')); implementation('org.slf4j:slf4j-api')","configurations.configureEach { resolutionStrategy.force('org.slf4j:slf4j-api:2.0.20') }",'UNKNOWN_ORIGIN'),
        ('configuration-boundary',"implementation(platform('org.springframework.boot:spring-boot-dependencies:4.0.0')); implementation('org.slf4j:slf4j-api'); testImplementation('org.slf4j:slf4j-api:2.0.20')",'',None),
    ]
    results=[]
    try:
        settings.write_text(integrated,newline='')
        for label,deps,extra,classification in cases:
            source=preamble+'dependencies { '+deps+' }\n'+extra+'\n'
            (leaf/'build.gradle').write_text(source,newline='');(e/f'subproject-{label}.gradle').write_text(source,newline='')
            r,out=container(row,e,'subproject-'+label+'-warning',base+[':bbgAudit:bbgNativeOracle',':bbgAudit:bootBomGuard'],tool='Gradle',timeout=180,network=False)
            if r['exit']:results.append(dict(scenario=label,blocked=r));continue
            data=(leaf/'.bbg/gradle-native.json').read_bytes();(e/f'subproject-{label}-native.json').write_bytes(data)
            oracle=check(json.loads(data),expected,out)
            r2,strict=container(row,e,'subproject-'+label+'-strict',base+[':bbgAudit:bootBomGuard','-PauditStrict=true'],tool='Gradle',timeout=180,network=False)
            found=[v['classification'] for g in oracle.values() for v in g['reported'].values()]
            verified=not any(g['mismatch'] for g in oracle.values()) and bool(r2['exit'])==any(g['should_fail'] for g in oracle.values())
            if classification:verified &= bool(found) and all(c==classification for c in found)
            if label=='configuration-boundary':verified &= not oracle['runtimeClasspath']['reported'] and bool(oracle['testRuntimeClasspath']['reported'])
            results.append(dict(scenario=label,runs=[r,r2],oracle=oracle,verified=verified))
            (e/'gradle-boundaries.json').write_text(json.dumps(results,indent=2));print(label,verified,flush=True)
    finally:
        settings.write_bytes(original)
        # Exact, task-created directories only; no user content can be present here.
        assert leaf.parent==root and bridge.parent==root
        shutil.rmtree(leaf);shutil.rmtree(bridge)
        (e/'gradle-boundaries.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':
    assert check({'runtimeClasspath':dict(modules=[],unresolved=[])},{'runtimeClasspath':dict(modules=[],constraints=[])},'configuration=runtimeClasspath\nPASS checked=0 drift=0 unknown=0')['runtimeClasspath']['mismatch'] is False
    main()
