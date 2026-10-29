"""Independently distinguish Maven's metadata tree from actual artifact availability."""
import json
from campaign import HERE
from run_builds import container, maven

for f in sorted((HERE/'evidence').glob('[0-9][0-9][0-9]/result.json')):
    row=json.loads(f.read_text());e=f.parent
    if row.get('build_tool')!='Maven' or row.get('outcome')!='ENV_BLOCKED' or not (e/'tree.json').exists():continue
    r,out=container(row,e,'native-artifact-control',maven(row['build_root'],['org.apache.maven.plugins:maven-dependency-plugin:3.10.0:resolve'],['--offline']),network=False,timeout=120)
    (e/'artifact-control.json').write_text(json.dumps(dict(run=r,native_artifacts_available=r['exit']==0),indent=2));print(row['id'],r['exit'],flush=True)
