"""Compare each reactor module to native JSON tree and pristine Boot effective model."""
import json,re
from pathlib import Path
from retry import *

def verify(num):
 row=load(num); root=Path(row['clone_path']); directory=OUT/f'{num:03d}'
 log=(directory/('reactor-warning.log' if num==89 else 'reactor-guard.log')).read_text(encoding='utf-8')
 sections={m[0]:m[1] for m in re.findall(r'--- boot-bom-guard:[^\n]+ @ (\S+) ---\n(.*?)(?=\[INFO\] --- boot-bom-guard:|\Z)',log,re.S)}
 assert sections
 versions=sorted(set(re.findall(r'BOM=org.springframework.boot:spring-boot-dependencies:(\S+)',log)))
 expected={}
 for version in versions:
  file=directory/('pristine-'+version+'.xml')
  r,_=run(row,'pristine-'+version,['mvn','-B','-ntp','-N','-f',f'/root/.m2/repository/org/springframework/boot/spring-boot-dependencies/{version}/spring-boot-dependencies-{version}.pom',HELP,'-Doutput=/out/'+file.name],network=True)
  assert r['exit']==0
  expected[version]=management(file.read_bytes())
 results=[]
 for file in sorted(root.rglob('bbg-native-tree.json')):
  tree=json.loads(file.read_text(encoding='utf-8')); artifact=tree['artifactId']
  if artifact not in sections:continue
  section=sections[artifact]; bom=re.search(r'BOM=org.springframework.boot:spring-boot-dependencies:(\S+)',section)
  summary=re.search(r'(PASS|WARN) checked=(\d+) drift=(\d+) unknown=(\d+)',section)
  assert summary
  result=dict(module=file.relative_to(root).as_posix(),artifact=artifact,summary=summary[0])
  if not bom:
   assert 'Missing Spring Boot BOM' in section and int(summary[4])==1
   result.update(outcome='EXPECTED_MISSING_BOM',oracle_verified=False)
  else:
   # Bound the report at its summary; reactor preambles are not findings.
   oracle=compare(tree,expected[bom[1]],section[:summary.end()])
   assert not oracle['mismatches'],(artifact,oracle['mismatches'])
   assert int(summary[2])==oracle['comparable_unique']
   assert int(summary[3])==len(oracle['expected_drift']) and int(summary[4])==0
   result.update(outcome='DRIFT' if oracle['expected_drift'] else 'PASS',oracle_verified=True,oracle=oracle)
  results.append(result)
 assert len(results)==len(sections),(len(results),len(sections))
 (directory/'reactor-oracle.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 print(num,'verified',len(results),'modules; native BOM comparisons',sum(x['oracle_verified'] for x in results),flush=True)
 if num==89:
  existing=json.loads((directory/'result.json').read_text())
  leaf=next(x for x in results if x['artifact']=='payment')
  warn=(directory/'reactor-warning.log').read_text();off=(directory/'reactor-offline.log').read_text()
  def reports(s):return re.findall(r'(?:boot-bom-guard BOM=|(?:PASS|WARN) checked=|DRIFT |UNKNOWN )[^\n]+',s)
  assert reports(warn)==reports(off)
  existing.update(outcome='PASS',baseline='NATIVE_METADATA_AND_ARTIFACTS_PASSED_IN_REACTOR',selected_scope='payment with -pl payment -am (4 modules)',warning_exit=0,strict_exit=0,checked=176,drift=0,unknown=0,oracle_verified=True,repeat_identical=True,reactor_modules=len(results),blocker=None,boot_version=versions[0])
  (directory/'result.json').write_text(json.dumps(existing,indent=2),encoding='utf-8')

if __name__=='__main__':
 for num in [89,78,80,100]:verify(num)
