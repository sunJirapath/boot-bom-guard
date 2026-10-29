"""Additional native controls for artifact resolution, provenance and reactors."""
import difflib
import json
from pathlib import Path
import re
from campaign import HERE
from run_builds import GOAL, HELP, TREE, container, load, maven
from mutate_maven import profile, report_text
from oracle import compare, management


def incomplete_controls():
    for num in [2,26,51,77]:
        inv,e=load(num);row=json.loads((e/'result.json').read_text());path=Path(row['clone_path'])/row['build_root'];original=path.read_bytes()
        try:
            path.write_bytes(profile(original,'<dependencies><dependency><groupId>guard.audit</groupId><artifactId>deliberately-missing</artifactId><version>1</version></dependency></dependencies>'))
            run,out=container(row,e,'incomplete-artifacts',maven(row['build_root'],[TREE.replace(':tree',':resolve')],['--offline','-Pbbg-audit']),network=False)
            results=json.loads((e/'mutations.json').read_text())
            case=next(x for x in results if x['scenario']=='incomplete')
            case.update(native_artifact_control=run,verified=run['exit']!=0 and 'guard.audit:deliberately-missing' in out and case['runs'][0]['exit']==0 and case['runs'][1]['exit']!=0 and 'UNKNOWN Maven model/dependency resolution failed' in (e/'incomplete-warning.log').read_text())
            (e/'mutations.json').write_text(json.dumps(results,indent=2))
            row['scenario']=row['scenario'].replace('incomplete=unverified','incomplete=verified' if case['verified'] else 'incomplete=unverified')
            (e/'result.json').write_text(json.dumps(row,indent=2))
            print(num,'incomplete artifact control',case['verified'],flush=True)
        finally:path.write_bytes(original)


def extra(num,case,contents):
    inv,e=load(num);row=json.loads((e/'result.json').read_text());path=Path(row['clone_path'])/row['build_root'];original=path.read_bytes()
    variant=profile(original,contents)
    (e/f'{case}.patch').write_text(''.join(difflib.unified_diff(original.decode().splitlines(True),variant.decode().splitlines(True),fromfile=row['build_root'],tofile=row['build_root'])),newline='')
    try:
        path.write_bytes(variant)
        runs=[]
        run,out=container(row,e,case+'-native',maven(row['build_root'],[HELP,TREE],['-Pbbg-audit','-Dverbose','-Doutput=/work/.bbg/verbose.xml','-DoutputType=json','-DoutputFile=/work/.bbg/extra-tree.json']))
        runs.append(run)
        if run['exit']:
            return dict(scenario=case,blocked=run)
        scratch=Path(row['clone_path'])/'.bbg'
        tree=json.loads((scratch/'extra-tree.json').read_text())
        (e/f'{case}-tree.json').write_text(json.dumps(tree,indent=2))
        effective=(scratch/'verbose.xml').read_bytes();(e/f'{case}-effective.xml').write_bytes(effective)
        dm=re.search(rb'<dependencyManagement>(.*?)</dependencyManagement>',effective,re.S)
        native_boms=sorted(set(re.findall(rb'org.springframework.boot:spring-boot-dependencies:([A-Za-z0-9_.-]+)',dm[1] if dm else b'')))
        outputs=[]
        for mode,flags in [('warning',[]),('strict',['-DbootBomGuard.failOnDrift=true'])]:
            run,out=container(row,e,case+'-'+mode,maven(row['build_root'],[GOAL],['-Pbbg-audit']+flags));runs.append(run);outputs.append(out)
        result=dict(scenario=case,runs=runs,native_source_boms=[x.decode() for x in native_boms])
        if case=='import-precedence':
            result['verified']=len(native_boms)>1 and 'UNKNOWN Ambiguous Spring Boot BOM versions:' in outputs[0] and runs[1]['exit']==0 and runs[2]['exit']!=0
            if len(native_boms)<=1:result['not_exercised']='Native model did not retain multiple Boot BOM sources'
        else:
            oracle=compare(tree,management((e/'pristine.xml').read_bytes()),outputs[0]);result['oracle']=oracle
            result['verified']=not oracle['mismatches'] and runs[1]['exit']==0 and bool(runs[2]['exit'])==bool(oracle['expected_drift'])
        print(num,case,result['verified'],flush=True)
        return result
    finally:path.write_bytes(original)


def security_control():
    inv,e=load(2);row=json.loads((e/'result.json').read_text());path=Path(row['clone_path'])/row['build_root'];original=path.read_bytes()
    content='<repositories><repository><id>bbg-synthetic-credentials</id><url>https://audit-user:audit-sentinel-password@127.0.0.1:9/repo</url></repository></repositories><dependencies><dependency><groupId>guard.audit</groupId><artifactId>synthetic-credential-probe</artifactId><version>1</version></dependency></dependencies>'
    try:
        path.write_bytes(profile(original,content))
        run,out=container(row,e,'synthetic-credentials',maven(row['build_root'],[GOAL],['-Pbbg-audit']),timeout=90)
        report=report_text(out) or ''
        return dict(scenario='synthetic-credentials',run=run,synthetic_only=True,native_log_contains_sentinel='audit-sentinel-password' in out,guard_report_contains_sentinel='audit-sentinel-password' in report,verified=run['exit']==0 and 'UNKNOWN' in report and 'audit-sentinel-password' not in report)
    finally:path.write_bytes(original)


def reactors():
    for num,leaf in [(51,'spring-petclinic-customers-service'),(77,'spring-boot-admin-client')]:
        inv,e=load(num);row=json.loads((e/'result.json').read_text());runs=[]
        for mode,goals,flags in [('native',[TREE],[]),('warning',[GOAL],[]),('strict',[GOAL],['-DbootBomGuard.failOnDrift=true'])]:
            command=maven('pom.xml',goals,flags);command.remove('-N');command+=['-pl',leaf,'-am','-T','2']
            run,out=container(row,e,'reactor-'+mode,command,timeout=180);runs.append(run)
        result=dict(scenario='reactor-pl-am-T2',runs=runs,verified=all(r['exit']==0 for r in runs))
        (e/'reactor.json').write_text(json.dumps(result,indent=2))
        print(num,'reactor',result['verified'],flush=True)


if __name__=='__main__':
    incomplete_controls()
    result=[]
    alternate=next(x['alternate'] for x in json.loads((HERE/'evidence/002/mutations.json').read_text()) if x['scenario']=='direct')
    result.append(extra(2,'property-override',f'<properties><slf4j.version>{alternate}</slf4j.version></properties>'))
    result.append(extra(2,'type-boundary',f'<dependencies><dependency><groupId>org.slf4j</groupId><artifactId>slf4j-api</artifactId><type>pom</type><version>{alternate}</version></dependency></dependencies>'))
    (HERE/'evidence/002/extras.json').write_text(json.dumps(result,indent=2))
    result=extra(26,'import-precedence','<dependencyManagement><dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-dependencies</artifactId><version>4.0.1</version><type>pom</type><scope>import</scope></dependency></dependencies></dependencyManagement>')
    (HERE/'evidence/026/extras.json').write_text(json.dumps([result],indent=2))
    result=security_control();(HERE/'evidence/002/security.json').write_text(json.dumps(result,indent=2))
    reactors()
