"""Assert report provenance, outcome boundaries, links and untouched pinned sources."""
import ast
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from package_report import DEST, OLD, OUT, FIX

def main():
 rows=list(csv.DictReader((DEST/'results.csv').open(encoding='utf-8')))
 coverage=list(csv.DictReader((DEST/'coverage.csv').open(encoding='utf-8')))
 assert len(rows)==100 and len({r['repo'] for r in rows})==100
 assert Counter(r['tier_proposed'] for r in rows)==dict.fromkeys(['Small','Medium','Large','Huge'],25)
 assert sum(r['revisited']=='yes' for r in rows)==26
 for row in rows:
  n=int(row['id']);assert re.fullmatch('[0-9a-f]{40}',row['sha'])
  evidence=json.loads((DEST/row['evidence_path']).read_text(encoding='utf-8'))
  result=evidence['result.json'];assert result['sha']==row['sha'] and result['repo']==row['repo']
  if row['outcome'] in ['PASS_EXPECTED','DRIFT_DETECTED_CORRECTLY']:
   assert int(row['unknown_count'])==0 and int(row['guard_warn_exit'])==0
   assert int(row['guard_strict_exit'])==(row['outcome']=='DRIFT_DETECTED_CORRECTLY')
   assert result.get('oracle_verified') or result.get('oracle_status')=='MATCHED_NATIVE_TREE_AND_PRISTINE_MODEL' or result.get('native_graph_unchanged'),n
  if row['guard_sha']=='NOT_RUN':assert not row['guard_warn_exit'] and not row['guard_strict_exit'],n
 for c in coverage:assert (DEST/c['evidence']).is_file(),c
 parsed={}
 for path in DEST.rglob('*'):
  if not path.is_file():continue
  data=path.read_bytes();assert b'\r\n' not in data,path
  if path.suffix=='.json':parsed[path.relative_to(DEST).as_posix()]=json.loads(data)
  if path.suffix=='.py':ast.parse(data.decode('utf-8'),str(path))
  if path.suffix in ['.json','.log']:assert 'set-cookie:' not in data.decode('utf-8').lower(),path
  if path.suffix=='.md':
   for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)',data.decode('utf-8')):
    if link.startswith(('https:','http:','#')):continue
    target=link.split('#',1)[0];assert (path.parent/target).is_file(),(path,link)
 manifest=parsed['source-manifest.json']
 for item in manifest:
  source=Path(item['source']);assert hashlib.sha256(source.read_bytes()).hexdigest()==item['source_sha256'],source
  bundle=parsed[item['bundle']]
  if item['key'] not in bundle:
   log=(DEST/item['bundle']).with_suffix('.log').read_text(encoding='utf-8')
   assert '===== '+item['key']+' =====' in log,item
 def untouched(n):
  r=json.loads((OLD/'evidence'/f'{n:03d}'/'result.json').read_text(encoding='utf-8'));root=Path(r['clone_path'])
  command=['git','-c','core.longpaths=true']
  head=subprocess.check_output(command+['rev-parse','HEAD'],cwd=root,text=True).strip()
  dirty=subprocess.check_output(command+['status','--porcelain=v1','--untracked-files=no','-z'],cwd=root).decode('utf-8')
  assert head==r['sha'],(n,head)
  # Windows can retain stale stat/newline flags even for byte-identical files.
  for entry in dirty.split('\0'):
   if not entry:continue
   assert entry.startswith(' M '),(n,entry)
   name=entry[3:]
   assert (root/name).read_bytes()==subprocess.check_output(command+['show','HEAD:'+name],cwd=root),(n,name)
  return dict(id=n,byte_identical_status_flags=[entry[3:] for entry in dirty.split('\0') if entry])
 with ThreadPoolExecutor(max_workers=8) as pool:clones=list(pool.map(untouched,range(1,101)))
 result=dict(rows=100,tiers=Counter(r['tier_proposed'] for r in rows),outcomes=Counter(r['outcome'] for r in rows),revisited=26,source_files_hashed=len(manifest),coverage_observations=len(coverage),pinned_clone_contents_verified=100,byte_identical_status_flags=[c for c in clones if c['byte_identical_status_flags']],json_files_parsed=len(parsed),local_markdown_links='PASS',supported_outcome_oracles_and_exits='PASS',cookie_headers='SANITIZED')
 print(json.dumps(result,indent=2))
 (DEST/'report-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
