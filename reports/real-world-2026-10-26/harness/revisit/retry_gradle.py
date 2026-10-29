"""Use each consumer's checked-in wrapper and native artifact resolution."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
sys.dont_write_bytecode=True
from retry import OLD, OUT, git, load
sys.path.insert(0,str(OLD))
from campaign import execute
from run_builds import GRADLE_IMAGE

IDS=[4,32,35,36,42,45,47,49,54,62,63,92]
INIT='''import groovy.json.JsonOutput
allprojects { p ->
  if (p.path == System.getProperty('bbg.target')) {
    tasks.create('bbgRevisitNative') {
      doLast {
        def graphs = [:]
        ['compileClasspath','runtimeClasspath','testCompileClasspath','testRuntimeClasspath','compile','runtime','testCompile','testRuntime'].each { name ->
          def c = configurations.findByName(name)
          if (c != null && (!c.hasProperty('canBeResolved') || c.canBeResolved)) {
            def resolved = c.resolvedConfiguration.lenientConfiguration
            def modules = []
            def visited = [] as Set
            def walk
            walk = { d ->
              def key = d.moduleGroup+':'+d.moduleName+':'+d.moduleVersion
              if (visited.add(key)) {
                modules << [key:d.moduleGroup+':'+d.moduleName,version:d.moduleVersion]
                d.children.each { walk(it) }
              }
            }
            if (resolved.unresolvedModuleDependencies.isEmpty()) c.resolvedConfiguration.firstLevelModuleDependencies.each { walk(it) }
            modules = modules.unique().sort { it.key }
            def missing = resolved.unresolvedModuleDependencies.collect { [requested:it.selector.toString(),problem:it.problem.message] }
            def artifacts = resolved.unresolvedModuleDependencies.isEmpty() ? c.resolvedConfiguration.resolvedArtifacts.collect { it.file.name }.sort() : []
            graphs[name] = [modules:modules,unresolved:missing,artifacts:artifacts]
          }
        }
        new File('/out/native.json').text = JsonOutput.prettyPrint(JsonOutput.toJson(graphs))
        if (graphs.isEmpty() || graphs.values().any { !it.unresolved.isEmpty() }) throw new GradleException('Native artifacts incomplete; see native.json')
      }
    }
  }
}
'''
GUARD='''initscript { dependencies { classpath files('/guard/gradle-plugin/build/libs/gradle-plugin-0.1.0-SNAPSHOT.jar','/guard/core/build/libs/boot-bom-guard-core-0.1.0-SNAPSHOT.jar') } }
allprojects { p ->
  if (p.path == System.getProperty('bbg.target')) {
    apply plugin: io.github.bootbomguard.gradle.BootBomGuardPlugin
    bootBomGuard { failOnDrift.set(Boolean.getBoolean('bbg.strict')) }
  }
}
'''

def retry(num):
    row=load(num); root=Path(row['clone_path']); directory=OUT/f'{num:03d}'
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/'result.json').exists():
        history=directory/'history'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        history.mkdir(parents=True)
        for file in directory.iterdir():
            if file.is_file():shutil.copyfile(file,history/file.name)
    assert git(root,'rev-parse','HEAD')==row['sha']
    assert not git(root,'status','--porcelain=v1','--untracked-files=no')
    build=(root/row['build_root']).parent; wrapper=build
    while wrapper != root and not (wrapper/'gradle/wrapper/gradle-wrapper.properties').exists():wrapper=wrapper.parent
    relative=wrapper.relative_to(root).as_posix()
    target=':'+build.relative_to(wrapper).as_posix().replace('/',':') if build!=wrapper else ':'
    if num==49:target=':realworld-app:web'
    if num==92:target=':genie-web'
    properties=(wrapper/'gradle/wrapper/gradle-wrapper.properties').read_text()
    version=re.search(r'gradle-([\d.]+)-(?:bin|all)\.zip',properties)[1]
    jdk='jdk8' if num in [4,54] else 'jdk17' if num==32 else 'azul17' if num==92 else None
    result={k:row.get(k) for k in ['id','repo','sha','build_root','build_tool','tier_proposed','boot_version']}
    result.update(previous_outcome=row['outcome'],wrapper=version,target=target,jdk=jdk or 'temurin21',runs=[],outcome='BASELINE_BLOCKED')
    (directory/'native.init.gradle').write_text(INIT,encoding='utf-8',newline='')
    (directory/'guard.init.gradle').write_text(GUARD,encoding='utf-8',newline='')
    def command(label,tasks,guard=False,offline=False):
        name=f'bbg-revisit-{num}-{label}'
        path='/work'+('/'+relative if relative!='.' else '')
        args=['docker','run','--rm','--name',name,'--cap-drop','ALL','--security-opt','no-new-privileges','--memory','3g','--cpus','2','--pids-limit','512',
              '--mount',f'type=bind,source={root},target=/work','--mount',f'type=bind,source={directory},target=/out',
              '--mount',f'type=bind,source={OUT / "guard"},target=/guard,readonly',
              '--mount','type=volume,source=bbg-revisit-gradle-20261026,target=/cache',
              '--mount','type=volume,source=bbg-revisit-toolchains-20261026,target=/toolchains,readonly',
              '-e','GRADLE_USER_HOME=/cache','-e','CI=true','-w',path]
        if offline:args+=['--network','none']
        if jdk:args+=['-e',f'JAVA_HOME=/toolchains/{jdk}']
        args += [GRADLE_IMAGE]
        if (wrapper/'gradle/wrapper/gradle-wrapper.jar').exists():
            args += [f'/toolchains/{jdk}/bin/java' if jdk else '/opt/java/openjdk/bin/java','-cp',path+'/gradle/wrapper/gradle-wrapper.jar','org.gradle.wrapper.GradleWrapperMain']
        else:
            assert re.fullmatch(r'[0-9.]+',version)
            args += [f'/cache/native-distributions/gradle-{version}/bin/gradle']
        args += [
               '--no-daemon','--console=plain','--max-workers=2','-Dorg.gradle.jvmargs=-Xmx1536m',
               '-Porg.gradle.java.installations.paths=/toolchains/jdk8,/toolchains/jdk17,/toolchains/jdk25,/toolchains/azul17',f'-Dbbg.target={target}']
        if int(version.split('.')[0])>=4:args+=['--no-scan']
        if guard:args+=['-I','/out/guard.init.gradle']
        else:args+=['-I','/out/native.init.gradle']
        if offline:args+=['--offline']
        args+=tasks
        code,seconds,output=execute(args,OUT,directory/(label+'.log'),timeout=600)
        if code==124:subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=30)
        result['runs'].append(dict(label=label,exit=code,elapsed_s=seconds))
        print(f'{num:03d} {label}: exit={code} seconds={seconds}',flush=True)
        (directory/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return code,output
    try:
        code,output=command('wrapper-native',[target.rstrip(':')+':bbgRevisitNative'])
        if code:
            result['blocker']=output[-10000:]
            return
        native=json.loads((directory/'native.json').read_text())
        boots=sorted({m['version'] for g in native.values() for m in g['modules'] if m['key'].startswith('org.springframework.boot:')})
        result.update(native_boot_versions=boots,baseline='NATIVE_METADATA_AND_ARTIFACTS_PASSED')
        if jdk:
            result.update(outcome='EXPECTED_UNSUPPORTED',guard_execution='NOT_RUN: original Boot/Gradle/JVM outside supported boundary')
            return
        code,output=command('guard-warning',[target.rstrip(':')+':bootBomGuard'],guard=True)
        result['warning_exit']=code
        code,strict=command('guard-strict',[target.rstrip(':')+':bootBomGuard','-Dbbg.strict=true'],guard=True)
        result['strict_exit']=code
        summaries=re.findall(r'(PASS|WARN) checked=(\d+) drift=(\d+) unknown=(\d+)',output)
        result['summaries']=summaries
        result['outcome']='GUARD_UNKNOWN' if not summaries or any(int(s[3]) for s in summaries) else 'DRIFT' if any(int(s[2]) for s in summaries) else 'PASS'
        if summaries and any(int(s[3]) for s in summaries) and 'Missing Spring Boot BOM; import a native Gradle platform.' in output:
            result.update(outcome='EXPECTED_UNSUPPORTED',boundary='Original dependency-management DSL has no native Boot platform',boundary_verified=result['warning_exit']==0 and result['strict_exit']==1)
        code,repeated=command('guard-repeat-offline',[target.rstrip(':')+':bootBomGuard'],guard=True,offline=True)
        def report(log):return '\n'.join(line for line in log.splitlines() if line.startswith(('configuration=','boot-bom-guard ','PASS checked=','WARN checked=','DRIFT ','ALLOWED ','UNKNOWN ')))
        result['repeat_identical']=code==0 and report(output)==report(repeated)
    finally:
        assert git(root,'rev-parse','HEAD')==row['sha']
        assert not git(root,'status','--porcelain=v1','--untracked-files=no')
        (directory/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ids',nargs='+',type=int,default=IDS);args=parser.parse_args()
    assert len(set(IDS))==12 and "classpath files" in GUARD
    for num in args.ids:retry(num)
