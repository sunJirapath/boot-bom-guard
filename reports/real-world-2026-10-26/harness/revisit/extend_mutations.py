"""Reuse the original six-scenario Maven suite against the fixed guard cache."""
import json,shutil,sys
from pathlib import Path
import retry as retry_run
from retry import *
import mutate_maven as suite

def mutate(num):
 directory=OUT/f'{num:03d}';new=json.loads((directory/'result.json').read_text());row=load(num)
 assert new.get('oracle_verified') and new['outcome'] in ['PASS','DRIFT']
 row.update(new);row.update(clone_path=load(num)['clone_path'],oracle_status='MATCHED_NATIVE_TREE_AND_PRISTINE_MODEL',scenario='fixed-guard-original-warning-strict')
 (directory/'result.json').write_text(json.dumps(row,indent=2))
 shutil.copyfile(directory/'warning.log',directory/'original-warning.log')
 (Path(row['clone_path'])/'.bbg').mkdir(exist_ok=True)
 suite.load=lambda n:(row,directory)
 def container(r,evidence,label,args,network=True,**kwargs):
  return retry_run.run(r,'mutation-'+label,args,network=network,timeout=240)
 suite.container=container
 suite.mutate(num,offline_all=True,refresh_results=False)
 result=json.loads((directory/'result.json').read_text())
 result['mutation_guard_sha']='f961d07815c68afea08d63aada9baf754b771b65'
 cases=json.loads((directory/'mutations.json').read_text())
 assert len(cases)==6 and all(x['verified'] for x in cases),cases
 result['six_scenario_suite_verified']=True
 (directory/'result.json').write_text(json.dumps(result,indent=2))
 assert not git(Path(row['clone_path']),'status','--porcelain=v1','--untracked-files=no')
 print(num,'all six scenarios passed',flush=True)

if __name__=='__main__':
 for n in [18,44,81,85,87]:mutate(n)
