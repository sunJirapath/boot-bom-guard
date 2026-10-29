"""Minimize an observed real-repository SNAPSHOT alias mismatch; no guard edits."""
import json
from pathlib import Path
import shutil
import sys
from campaign import HERE, WORK
from run_builds import container, maven, HELP, TREE, GOAL, flatten_tree
from oracle import compare, management, findings

POM = '''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>guard.audit</groupId><artifactId>aligned-snapshot</artifactId><version>1</version>
<dependencyManagement><dependencies><dependency><groupId>org.springframework.boot</groupId>
<artifactId>spring-boot-dependencies</artifactId><version>4.2.0-SNAPSHOT</version><type>pom</type><scope>import</scope>
</dependency></dependencies></dependencyManagement>
<dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter</artifactId></dependency></dependencies>
<repositories><repository><id>spring-snapshots</id><url>https://repo.spring.io/snapshot</url></repository>
<repository><id>spring-milestones</id><url>https://repo.spring.io/milestone</url></repository>
<repository><id>spring-releases</id><url>https://repo.spring.io/release</url></repository></repositories>
</project>
'''

def run(label):
    root=WORK/'repros/BBG-001';root.mkdir(parents=True,exist_ok=True)
    e=HERE/'bugs/BBG-001'/label;e.mkdir(parents=True,exist_ok=True)
    (root/'pom.xml').write_text(POM,newline='');(e/'pom.xml').write_text(POM,newline='')
    (root/'.bbg').mkdir(exist_ok=True)
    row=dict(id='bug1',clone_path=str(root))
    runs=[]
    native,out=container(row,e,'native',maven('pom.xml',[HELP,TREE],['--offline','-Doutput=/work/.bbg/effective.xml','-DoutputFile=/work/.bbg/tree.json','-DoutputType=json']),network=False)
    runs.append(native)
    resolved,out=container(row,e,'native-artifacts',maven('pom.xml',['org.apache.maven.plugins:maven-dependency-plugin:3.10.0:resolve'],['--offline']),network=False)
    runs.append(resolved)
    if native['exit'] or resolved['exit']:
        (e/'result.json').write_text(json.dumps(dict(blocked=runs),indent=2));return
    for f in ['effective.xml','tree.json']:shutil.copyfile(root/'.bbg'/f,e/f)
    expected=management((HERE/'evidence/078/pristine.xml').read_bytes())
    outputs=[]
    for mode,flags in [('warning',[]),('repeat',[]),('strict',['-DbootBomGuard.failOnDrift=true'])]:
        r,out=container(row,e,mode,maven('pom.xml',[GOAL],['--offline']+flags),network=False);runs.append(r);outputs.append(out)
    oracle=compare(json.loads((e/'tree.json').read_text()),expected,outputs[0])
    metadata="find /root/.m2/repository/org/springframework/boot/spring-boot/4.2.0-SNAPSHOT -maxdepth 1 -type f \\( -name 'maven-metadata-*.xml' -o -name '*.jar.sha1' \\) -print -exec cat {} \\;"
    container(row,e,'snapshot-metadata',['sh','-c',metadata],network=False)
    result=dict(runs=runs,oracle=oracle,repeat_identical=findings(outputs[0])==findings(outputs[1]),confirmed=not oracle['expected_drift'] and bool(oracle['mismatches']) and all(r['exit']==0 for r in runs[:4]) and runs[4]['exit']!=0)
    assert all(n['version']=='4.2.0-SNAPSHOT' for n in flatten_tree(json.loads((e/'tree.json').read_text())) if n['groupId']=='org.springframework.boot')
    (e/'result.json').write_text(json.dumps(result,indent=2));print(label,'confirmed=',result['confirmed'],'findings=',len(oracle['guard_findings']),flush=True)

if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else '137b0026')
