"""Warm, offline, matched graph pairs; sample the Maven process's Linux RSS high-water mark."""
import hashlib
import json
import re
import shlex
import statistics
from pathlib import Path
from campaign import HERE
from run_builds import load, container, maven, TREE, GOAL, flatten_tree

def graph_hash(path):
    graph=json.loads(path.read_text())
    selected=sorted({(n['groupId'],n['artifactId'],n.get('type','jar'),n.get('classifier',''),n['version'],n.get('scope','')) for n in flatten_tree(graph)[1:]})
    return hashlib.sha256(json.dumps(selected).encode()).hexdigest(),len(selected)

def sample(command):
    # Maven's Unix launcher execs Java, so $! identifies the measured JVM.
    return ['sh','-c',shlex.join(command)+''' & measured=$!; peak=0
while kill -0 "$measured" 2>/dev/null; do
 value=$(awk '/^VmHWM:/ {print $2}' /proc/$measured/status 2>/dev/null)
 if [ "${value:-0}" -gt "$peak" ]; then peak=$value; fi
 sleep 0.05
done
wait "$measured"; status=$?
printf '\\nBBG_PEAK_RSS_KB=%s\\n' "$peak"
exit "$status"
''']

def run(num):
    inv,e=load(num);row=json.loads((e/'result.json').read_text());runs=[]
    scratch=Path(row['clone_path'])/'.bbg';path=scratch/'benchmark-tree.json'
    reference=None
    for repeat in range(4):
        # First pair warms identical commands and is excluded from statistics.
        modes=['native','guard'] if repeat%2==0 else ['guard','native']
        for mode in modes:
            goals=[TREE]+([GOAL] if mode=='guard' else [])
            command=maven(row['build_root'],goals,['--offline','-DoutputType=json','-DoutputFile=/work/.bbg/benchmark-tree.json'])
            r,out=container(row,e,f'benchmark-{repeat}-{mode}',sample(command),timeout=180,network=False)
            assert r['exit']==0,(num,r)
            digest,count=graph_hash(path)
            if reference is None:reference=digest
            assert digest==reference,'Native selected graph changed across measurement pair'
            rss=re.search(r'BBG_PEAK_RSS_KB=(\d+)',out)
            assert rss and int(rss[1])>0,'No process RSS sample'
            runs.append(dict(**r,repeat=repeat,mode=mode,graph_sha256=digest,selected_unique=count,peak_rss_mb=round(int(rss[1])/1024,2)))
            print(num,repeat,mode,r['elapsed_s'],runs[-1]['peak_rss_mb'],flush=True)
    measured=[r for r in runs if r['repeat']>0]
    stats={mode:dict(elapsed_s=round(statistics.median(r['elapsed_s'] for r in measured if r['mode']==mode),3),peak_rss_mb=round(statistics.median(r['peak_rss_mb'] for r in measured if r['mode']==mode),2)) for mode in ['native','guard']}
    result=dict(repo=row['repo'],build_root=row['build_root'],runs=runs,median=stats,elapsed_delta_s=round(stats['guard']['elapsed_s']-stats['native']['elapsed_s'],3),rss_delta_mb=round(stats['guard']['peak_rss_mb']-stats['native']['peak_rss_mb'],2),graph_sha256=reference,selected_unique=count)
    (e/'benchmark.json').write_text(json.dumps(result,indent=2))
    row['peak_rss_mb']=stats['guard']['peak_rss_mb'];row['scenario']+=';performance=3-matched-pairs';(e/'result.json').write_text(json.dumps(row,indent=2))

if __name__=='__main__':
    assert 'VmHWM' in sample(['mvn','--offline'])[2]
    for num in [77,78,94]:run(num)
