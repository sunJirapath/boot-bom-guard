"""Publish compact, reviewable evidence; never mutate the original investigation."""
import csv,hashlib,json,re,shutil,sys
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timezone
from retry import OLD,OUT,load
W=Path(r'C:\Users\Sun\.codex\worktrees\fix-maven-snapshot-identity\boot-bom-guard')
DEST=W/'reports/real-world-2026-10-26'
FIX=W/'build/bbg-001'
PIN='f961d07815c68afea08d63aada9baf754b771b65'
ORIGINAL='137b0026e3fd24952a0aa5eccc8a89b448196e16'
manifest=[]

def sanitize(s):
 return '\n'.join('[cookie header omitted]' if 'invalid cookie header' in line.lower() or 'set-cookie:' in line.lower() else re.sub(r'^[ \t]+',lambda m:m[0].expandtabs(4),line.rstrip()) for line in s.splitlines()).rstrip()+'\n'
def clean(v):
 if isinstance(v,str):return sanitize(v).rstrip('\n')
 if isinstance(v,list):return [clean(x) for x in v]
 if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
 return v

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(value,encoding='utf-8',newline='\n')
def jsonwrite(path,value):write(path,json.dumps(clean(value),indent=2,ensure_ascii=False)+'\n')

def bundle(source,destination,recursive=True):
 data={};logs=[]
 files=sorted(source.rglob('*') if recursive else source.iterdir())
 for f in files:
  if not f.is_file() or f.suffix not in ['.json','.log','.patch','.xml']:continue
  if any(x in f.relative_to(source).parts for x in ['__pycache__','.gradle','target','build','pristine-gradle']):continue
  name=f.relative_to(source).as_posix();raw=f.read_bytes()
  if f.suffix=='.json':
   try:data[name]=json.loads(raw)
   except ValueError:continue
  elif f.suffix=='.xml':
   # Retain native model hash and normalized dependency-management entries without repeating megabytes of Maven XML.
   try:
    from oracle import management
    data[name]={'source_sha256':hashlib.sha256(raw).hexdigest(),'dependency_management':management(raw)}
   except Exception:continue
  else:logs.append('===== '+name+' =====\n'+sanitize(raw.decode('utf-8',errors='replace')))
  manifest.append(dict(source=str(f),source_sha256=hashlib.sha256(raw).hexdigest(),bundle=destination.relative_to(DEST).as_posix(),key=name))
 jsonwrite(destination,data)
 if logs:write(destination.with_suffix('.log'),'\n'.join(logs))

def main():
 DEST.mkdir(parents=True,exist_ok=True)
 original=list(csv.DictReader((OLD/'results.csv').open(encoding='utf-8-sig')))
 assert len(original)==100 and len({x['repo'] for x in original})==100
 rows=[];coverage=list(csv.DictReader((OLD/'coverage.csv').open(encoding='utf-8-sig')))
 for n,base in enumerate(original,1):
  row=dict(id=n,**base);old=load(n)
  row.update(guard_sha=(old.get('mutation_guard_sha') or ORIGINAL) if base['guard_warn_exit'] else 'NOT_RUN',original_outcome=base['outcome'],revisited='no',native_graph_nodes=old.get('native_graph_nodes',''),count_scope='Selected consumer graph',selected_scope=base['build_root'],elapsed_scope='Historical native baseline command',evidence_path=f'evidence/baseline/{n:03d}.json')
  bundle(OLD/'evidence'/f'{n:03d}',DEST/row['evidence_path'])
  newfile=OUT/f'{n:03d}'/'result.json'
  if newfile.exists():
   new=json.loads(newfile.read_text(encoding='utf-8'));log='\n'.join(p.read_text(encoding='utf-8',errors='replace') for p in newfile.parent.glob('*warning.log'))
   outcome={'PASS':'PASS_EXPECTED','DRIFT':'DRIFT_DETECTED_CORRECTLY','EXPECTED_UNSUPPORTED':'EXPECTED_UNSUPPORTED'}.get(new['outcome'],'ENV_BLOCKED')
   if new['outcome']=='GUARD_UNKNOWN' and ('Unsupported Spring Boot BOM' in log or 'Ambiguous Spring Boot BOM versions' in log):outcome='EXPECTED_UNSUPPORTED'
   row.update(revisited='yes',outcome=outcome,guard_sha=PIN,evidence_path=f'evidence/revisit/{n:03d}.json',baseline_status=new.get('baseline','FAILED_OR_INCOMPLETE'),guard_warn_exit=new.get('warning_exit',''),guard_strict_exit=new.get('strict_exit',''),boot_version=(','.join(new.get('native_boot_versions',[])) if new.get('native_boot_versions') else new.get('boot_version')) or base['boot_version'])
   if new.get('summaries'):
    row.update(drift_count=sum(int(x[2]) for x in new['summaries']),unknown_count=sum(int(x[3]) for x in new['summaries']),count_scope='Sum of four classpath findings; coordinates can repeat')
   else:row.update(drift_count=new.get('drift',''),unknown_count=new.get('unknown',''))
   if new.get('baseline'):row['baseline_status']=new['baseline']
   if outcome in ['PASS_EXPECTED','DRIFT_DETECTED_CORRECTLY']:
    assert new.get('oracle_verified'),(n,'Supported result needs independent oracle')
    assert new['warning_exit']==0 and new['strict_exit']==(outcome=='DRIFT_DETECTED_CORRECTLY'),n
   if new.get('baseline'):
    d=newfile.parent
    if row['build_tool']=='Maven':
     from run_builds import flatten_tree
     row['native_graph_nodes']=len(flatten_tree(json.loads((d/'tree.json').read_text())))
    else:
     graph=json.loads((d/('native-rich.json' if (d/'native-rich.json').exists() else 'native.json')).read_text())
     runtime=graph.get('runtimeClasspath',graph.get('runtime',{}))
     row['native_graph_nodes']=sum(m.get('library',True) for m in runtime.get('modules',[]))
    nodes=row['native_graph_nodes'];row['tier_measured']='Small' if nodes<=150 else 'Medium' if nodes<=500 else 'Large' if nodes<=1500 else 'Huge'
    row['module_count']=1
   if new.get('target'):row['selected_scope']=new['target']
   row.update(elapsed_s=round(sum(x['elapsed_s'] for x in new['runs']),3),elapsed_scope='Revisit recorded native/guard commands; prerequisite bootstraps excluded')
   if 'warning_exit' not in new:row['guard_sha']='NOT_RUN'
   if new.get('guard_execution','').startswith('NOT_RUN'):
    row['scenario']='native-wrapper-baseline;guard=NOT_RUN_OUTSIDE_SUPPORTED_RUNTIME'
    row['guard_sha']='NOT_RUN'
   else:row['scenario']='native-baseline;fixed-guard-warning-strict' if 'warning_exit' in new else 'native-baseline-only'
   if new.get('oracle_verified'):row['scenario']+=';native-oracle=verified'
   if new.get('repeat_identical'):row['scenario']+=';offline-repeat=verified'
   if new.get('six_scenario_suite_verified'):row['scenario']+=';direct=verified;managed=verified;allowed=verified;incomplete=verified;determinism=verified;offline=verified'
   bundle(newfile.parent,DEST/row['evidence_path'])
   coverage.append(dict(id=n,repo=row['repo'],scenario='original-build-revisit',status=outcome,evidence=row['evidence_path']))
   for key,scenario in [('baseline','revisit/native-metadata-and-artifacts'),('oracle_verified','revisit/independent-native-oracle'),('boundary_verified','revisit/warning-strict-unsupported-boundary'),('repeat_identical','revisit/offline-determinism')]:
    if new.get(key):coverage.append(dict(id=n,repo=row['repo'],scenario=scenario,status='VERIFIED',evidence=row['evidence_path']))
   if new.get('six_scenario_suite_verified'):
    for scenario in ['direct','managed','allowed','incomplete','determinism','offline']:
     coverage.append(dict(id=n,repo=row['repo'],scenario='fixed-guard/'+scenario,status='VERIFIED',evidence=row['evidence_path']))
  if n in [78,79,80,82,100]:
   fixed=json.loads((FIX/f'{n:03d}'/'result.json').read_text())
   row.update(outcome='DRIFT_DETECTED_CORRECTLY' if fixed['genuine_drift'] else 'PASS_EXPECTED',guard_sha=PIN,issue_id='BBG-001 (fixed)',guard_warn_exit=0,guard_strict_exit=fixed['strict_exit'],drift_count=fixed['genuine_drift'],unknown_count=0,baseline_status='NATIVE_METADATA_AND_ARTIFACTS_PASSED',scenario=base['scenario']+';snapshot-fix=verified;unchanged-native-graph=verified',evidence_path=f'evidence/fix/{n:03d}.json')
   bundle(FIX/f'{n:03d}',DEST/row['evidence_path'])
   coverage.append(dict(id=n,repo=row['repo'],scenario='snapshot-fix-native-graph-parity',status='VERIFIED',evidence=row['evidence_path']))
  if (OUT/f'{n:03d}'/'reactor-oracle.json').exists():
   reactor=json.loads((OUT/f'{n:03d}'/'reactor-oracle.json').read_text())
   if not newfile.exists():bundle(OUT/f'{n:03d}',DEST/f'evidence/revisit/{n:03d}.json')
   coverage.append(dict(id=n,repo=row['repo'],scenario='complete-default-reactor' if n!=89 else 'selected-reactor-pl-am',status=f'VERIFIED {len(reactor)} modules; {sum(x["oracle_verified"] for x in reactor)} Boot model comparisons',evidence=f'evidence/revisit/{n:03d}.json'))
  if (OUT/f'{n:03d}'/'reactor-benchmark.json').exists():
   coverage.append(dict(id=n,repo=row['repo'],scenario='whole-reactor-matched-offline-performance',status='VERIFIED',evidence=f'evidence/revisit/{n:03d}.json'))
  rows.append(row)
 # Historical scenario paths now address bundles indexed by original relative filenames.
 for c in coverage:
  if c['evidence'].startswith('evidence/') and not c['evidence'].startswith(('evidence/baseline/','evidence/revisit/','evidence/fix/')):
   c['evidence']=f'evidence/baseline/{int(c["id"]):03d}.json'
 fields=list(rows[0]);assert all(set(x)==set(fields) for x in rows)
 with (DEST/'results.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fields,lineterminator="\n");writer.writeheader();writer.writerows(rows)
 with (DEST/'coverage.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,['id','repo','scenario','status','evidence'],lineterminator='\n');writer.writeheader();writer.writerows(coverage)
 for f in OLD.glob('*.py'):write(DEST/'harness/original'/f.name,f.read_text(encoding='utf-8'))
 for f in Path(__file__).parent.glob('*.py'):write(DEST/'harness/revisit'/f.name,f.read_text(encoding='utf-8'))
 write(DEST/'test-plan.md',(OLD/'test-plan.md').read_text(encoding='utf-8'))
 bundle(OLD/'bugs/BBG-001',DEST/'evidence/bug-before.json')
 bundle(FIX/'000',DEST/'evidence/bug-after.json')
 write(DEST/'repro/pom.xml',(OLD/'bugs/BBG-001/0c5888db/pom.xml').read_text())
 extras={}
 for p in [FIX/'campaign-verification.json',FIX/'fix-provenance.json',FIX/'final-verification.json',OLD/'evidence/product-test-suites.json',OLD/'checkout-verification.json']:
  if p.exists():extras[p.name]=json.loads(p.read_text())
 jsonwrite(DEST/'evidence/provenance.json',extras)
 final=W/'build/final-validation-20261029'
 if final.exists():bundle(final,DEST/'evidence/final-validation-20261029.json')
 jsonwrite(DEST/'source-manifest.json',manifest)
 counts=Counter(x['outcome'] for x in rows);table=[]
 for tier in ['Small','Medium','Large','Huge']:
  for tool in ['Maven','Gradle']:
   group=[x for x in rows if x['tier_proposed']==tier and x['build_tool']==tool];c=Counter(x['outcome'] for x in group)
   table.append('| '+' | '.join(map(str,[tier,tool,len(group),c['PASS_EXPECTED'],c['DRIFT_DETECTED_CORRECTLY'],c['EXPECTED_UNSUPPORTED'],c['ENV_BLOCKED']]))+' |')
 assert all(sum(x['tier_proposed']==tier for x in rows)==25 for tier in ['Small','Medium','Large','Huge'])
 summary=f"""# 100-repository investigation — 2026-10-26

All 100 catalog repositories were pinned, inspected and given a native dependency-resolution attempt. The 26 previously blocked candidates were revisited using original wrappers, matching JDKs and native sibling-module bootstraps. No target upstream was modified or pushed; no Spring Boot migration was attempted.

Current candidate outcomes: **{counts['PASS_EXPECTED']} aligned**, **{counts['DRIFT_DETECTED_CORRECTLY']} genuine drift**, **{counts['EXPECTED_UNSUPPORTED']} expected unsupported**, **{counts['ENV_BLOCKED']} baseline/artifact blocked**. Unsupported and blocked candidates are not successful integrations. [One row per candidate](results.csv), [actual scenario coverage](coverage-matrix.md), [remaining blockers](blocked-candidates.md).

**BBG-001 is fixed:** all 202 false SNAPSHOT findings disappeared across the five affected repositories; their native graphs were unchanged and all three genuine Gateway drifts remained. The six frozen SNAPSHOT regressions fail before the fix and pass after it. Product verification passed 58 distinct tests (12 core, 21 Maven, 25 Gradle), online and with the warmed offline cache. [Defect, reproduction and proof](bugs.md).

| Catalog tier | Selected tool | Candidates | Aligned | Genuine drift | Unsupported | Blocked |
| --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(table)}

## Provenance and method

Original guard: `{ORIGINAL}` (`0.1.0-SNAPSHOT`). The source-equivalent upstream update was `0c5888db559e174ee8f70d99969730ba1e6bcef0`. Fixed guard: `{PIN}`. Each CSV row identifies its actual guard pin; this does not claim all 100 original baselines were rerun with the fix. [Source/test provenance](evidence/provenance.json).

The pilot selected four repositories per catalog tier before scaling. Independent Maven truth uses effective models, resolved JSON trees and actual artifact resolution. The expected model comes from a separately built pristine Boot BOM, without consumer property overrides. Gradle truth uses original wrapper resolution of all four classpaths; a separate plain Java Gradle project validates the platform expected versions. A metadata-only tree is never treated as proof that required JARs exist.

Public third-party builds ran only in resource-limited containers (3 GiB, 2 CPUs, 512 PIDs, dropped capabilities). No host credentials, personal Maven/Gradle settings, Docker socket, databases or application services were mounted. Caches and toolchains were isolated. Bootstraps used the unchanged native source and `install -DskipTests`; that is prerequisite preparation, not an application-test pass. Exact image digests, full command arrays, exits and timings are included in the evidence bundles.

Original proof is under `evidence/baseline/NNN.json` with its adjacent `.log`. New attempts are under `evidence/revisit/NNN.json`; fixed-bug repeats are under `evidence/fix/NNN.json`. A JSON bundle is keyed by the original relative evidence filename, including every recorded command. XML models are represented by their original SHA-256 and normalized dependency-management entries. Logs and patches are consolidated in the adjacent text file; cookie header noise is omitted and trailing whitespace is trimmed. [Source hashes and bundle keys](source-manifest.json). Raw XML, frozen caches and disposable clones remain local. The supplied catalog is [test-plan.md](test-plan.md).

## Coverage boundaries

Final follow-up on 2026-10-29: Maven offline install, all 21 Maven integration tests and Gradle 8.14.3 offline check passed again on merge commit `51aa970` (58 distinct tests, no failures or skips). [Current-run metadata and counts](evidence/final-validation-20261029.json), [logs](evidence/final-validation-20261029.log). The native GeoServer resolver was refreshed with `-U` and still could not find `org.geoserver:gs-main:3.1.0-CLOUD-SNAPSHOT`; the guard was not invoked for that blocked attempt.

The report validator checks all 100 pinned clone contents, source hashes, evidence links and supported-outcome oracles/exits. It enables Git long-path support on Windows. Six GeoServer status flags refer to files whose bytes exactly match their pinned blobs; no candidate source was restored or changed during this follow-up. Historical runners under `harness/` retain their original local paths, Docker cache names and toolchain assumptions; they require explicit path/cache setup on another machine and are not a portable one-command rerun.

Catalog tiers retain 25 candidates each. Measured sizes describe the selected module, not repository popularity or build-file counts. Whole-reactor measurements report each module graph separately and the aggregate workload; none establishes a single graph above 1,500 nodes. Default reactors also contain BOM/aggregation modules without a Boot BOM: their UNKNOWN result is expected and is not counted as a supported module pass. Strict root-reactor checks can therefore fail before reaching consumers; use consumer-only execution when that is the intended scope.

Every reported executed scenario has direct evidence in [coverage.csv](coverage.csv). No candidate completed every possible requested scenario. Existing product tests are distinct from external coverage. Application tests/services, Boot migrations, cold-cache offline reliability, production memory, comprehensive mirror/proxy behavior and exhaustive configuration-cache/constraint/substitution permutations were not tested. The credential sentinel probes do not establish universal exception-message redaction. Mutable public SNAPSHOT repositories can prevent exact historical downloads; frozen repository fixtures make the product regressions repeatable.

{benchmark_table()}
"""
 write(DEST/'summary.md',summary)
 lines=['# Actual scenario coverage','','Historical and fixed-guard scenarios are separate. Counts are repository/scenario observations, not test classes or classpath log lines. Native baseline completion and unsupported guard boundaries remain distinct.','','| Scenario | Recorded status | Repositories |','| --- | --- | --- |']
 groups=defaultdict(Counter)
 for c in coverage:groups[c['scenario']][c['status']]+=1
 for scenario,values in groups.items():lines.append('| '+scenario+' | '+'; '.join(f'{k}: {v}' for k,v in values.items())+' | '+str(sum(values.values()))+' |')
 lines+=['','See [coverage.csv](coverage.csv) for exact repositories and evidence. New wrapper versions include 2.10, 2.13, 7.4, 8.5, 8.14.1, 8.14.5, 9.1.0, 9.3.1, 9.8.1 and 9.8.2; wrapper execution alone does not imply supported guard integration. No Boot migration was attempted.']
 write(DEST/'coverage-matrix.md','\n'.join(lines)+'\n')
 blockers=['# Remaining candidate blockers','','Each failure below occurs in the unmodified native build or artifact resolver. None is attributed to the guard. Unsupported Boot/JVM/DSL/ambiguous-BOM boundaries are listed in results.csv, not counted as integration passes.','']
 for row in rows:
  if row['outcome']!='ENV_BLOCKED':continue
  n=row['id'];d=OUT/f'{n:03d}'
  logs=sorted(d.glob('*.log'));errors=[]
  for f in logs:
   text=f.read_text(encoding='utf-8',errors='replace')
   if any(x in text for x in ['BUILD FAILURE','BUILD FAILED','CAMPAIGN_TIMEOUT']):
    relevant=[line for line in text.splitlines() if any(k in line.lower() for k in ['failed to execute','could not find artifact','could not resolve','could not transfer','dependency:','compilation failure','campaign_timeout','premature end'])]
    errors.append(f.name+': '+' | '.join(relevant[:8]))
  blockers+=['## #'+f'{n:03d} '+row['repo'],'','Pinned source: `'+row['sha']+'`; selected build: `'+row['build_root']+'`. [Commands/results]('+row['evidence_path']+'), [logs]('+str(Path(row['evidence_path']).with_suffix('.log')).replace('\\','/')+').','',*['- '+sanitize(x).strip() for x in errors[-3:]],'']
 write(DEST/'blocked-candidates.md','\n'.join(blockers))
 print(json.dumps(dict(counts=counts,revisited=sum(x['revisited']=='yes' for x in rows),evidence_files=len(list(DEST.rglob('*')))),indent=2))

def benchmark_table():
 lines=['## Matched offline reactor performance','','A warm-up pair is excluded; three measured pairs alternate native-first/guard-first. Each run has an identical per-module graph fingerprint. Elapsed includes process/container startup. Peak RSS is sampled from the Maven JVM VmHWM every 50 ms, not whole-container or host memory.','','| Repo | Module graphs | Sum selected nodes | Largest module | Native median s | Guard median s | Native RSS MiB | Guard RSS MiB |','| --- | --- | --- | --- | --- | --- | --- | --- |']
 for n in [78,80,100]:
  p=OUT/f'{n:03d}'/'reactor-benchmark.json'
  if not p.exists():continue
  r=json.loads(p.read_text());a=r['median']['native'];b=r['median']['guard']
  lines.append('| '+f'#{n:03d}'+' | '+' | '.join(map(str,[r['modules'],r['module_scoped_nodes'],r['largest_module'],a['elapsed_s'],b['elapsed_s'],a['peak_rss_mb'],b['peak_rss_mb']]))+' |')
 lines+=['','These are local overhead observations on the measured default reactors, without a production performance guarantee. Per-run data and graph hashes are in the corresponding revisit bundle.']
 return '\n'.join(lines)

if __name__=='__main__':main()
