"""Measure complete pinned reactors with identical offline graph fingerprints."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
sys.dont_write_bytecode=True
from retry import OUT, OLD, load, run, TREE, GOAL
sys.path.insert(0,str(OLD))
from benchmark import sample
from run_builds import flatten_tree

def fingerprint(root):
    graphs={}
    union=set()
    for file in sorted(root.rglob('bbg-native-tree.json')):
        tree=json.loads(file.read_text(encoding='utf-8'))
        selected=sorted({(n['groupId'],n['artifactId'],n.get('type','jar'),n.get('classifier',''),n['version'],n.get('scope','')) for n in flatten_tree(tree)[1:]})
        graphs[file.relative_to(root).as_posix()]=selected
        union.update(selected)
    assert graphs
    return hashlib.sha256(json.dumps(graphs,sort_keys=True).encode()).hexdigest(),graphs,len(union)

def benchmark(num):
    row=load(num);root=Path(row['clone_path']);directory=OUT/f'{num:03d}'
    runs=[];reference=None
    for repeat in range(4):
        for mode in (['native','guard'] if repeat%2==0 else ['guard','native']):
            args=['mvn','-B','-ntp','--offline','-f','/work/pom.xml',TREE]
            if mode=='guard':args+=[GOAL]
            args+=['-DoutputType=json','-DoutputFile=target/bbg-native-tree.json']
            result,output=run(row,f'reactor-benchmark-{repeat}-{mode}',sample(args),timeout=300,network=False)
            assert result['exit']==0,output[-5000:]
            digest,graphs,unique=fingerprint(root)
            if reference is None:reference=digest
            assert reference==digest,'Native reactor graphs changed'
            rss=re.search(r'BBG_PEAK_RSS_KB=(\d+)',output)
            assert rss and int(rss[1])>0
            runs.append(dict(**result,repeat=repeat,mode=mode,graph_sha256=digest,peak_rss_mb=round(int(rss[1])/1024,2)))
    measured=[r for r in runs if r['repeat']>0]
    medians={m:dict(elapsed_s=statistics.median(r['elapsed_s'] for r in measured if r['mode']==m),peak_rss_mb=statistics.median(r['peak_rss_mb'] for r in measured if r['mode']==m)) for m in ['native','guard']}
    result=dict(repo=row['repo'],sha=row['sha'],scope='Complete default Maven reactor; not a single combined graph',modules=len(graphs),module_scoped_nodes=sum(map(len,graphs.values())),union_coordinate_version_scope_count=unique,largest_module=max(map(len,graphs.values())),graph_sha256=reference,runs=runs,median=medians)
    (directory/'reactor-benchmark.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (directory/'reactor-graphs.json').write_text(json.dumps(graphs,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='runs'},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ids',nargs='+',type=int,default=[100]);args=p.parse_args()
    for num in args.ids:benchmark(num)
