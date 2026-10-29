"""Assert report accounting, native comparisons, measured pairs and local evidence links."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import xml.etree.ElementTree as ET
from campaign import HERE

def read(p):return json.loads(p.read_text())
rows=list(csv.DictReader((HERE/'results.csv').open(encoding='utf-8')))
assert len(rows)==100 and len({r['repo'] for r in rows})==100
assert collections.Counter(r['tier_proposed'] for r in rows)==dict(Small=25,Medium=25,Large=25,Huge=25)
assert collections.Counter(r['outcome'] for r in rows)==dict(PASS_EXPECTED=21,DRIFT_DETECTED_CORRECTLY=4,EXPECTED_UNSUPPORTED=44,ENV_BLOCKED=26,CONFIRMED_LIB_BUG=5)
false_findings=0;oracles=0;benchmarks=0;core_suites=0
expanded=set(read(HERE/'expanded-mutation-ids.json'))
metadata_versions={n.text for n in ET.fromstring((HERE/'evidence/002/alternate-metadata.log').read_text()).findall('./versioning/versions/version')}
cached_versions=set(re.findall(r'/slf4j-api/([^/]+)/slf4j-api-[^/]+\.jar',(HERE/'evidence/002/cached-alternates.log').read_text()))
for r in rows:
    e=HERE/r['evidence_path'];data=read(e/'result.json');baseline=read(e/'baseline.command.json')
    assert data['repo']==r['repo'] and data['sha']==r['sha'] and data['outcome']==r['outcome']
    assert re.fullmatch('[a-f0-9]{40}',r['sha']) and r['build_root']
    assert (e/'inventory.json').is_file() and (e/'inspection.json').is_file()
    if data['outcome']=='EXPECTED_UNSUPPORTED':
        assert data['guard_warn_exit']==0 and data['guard_strict_exit']==1 and data['unknown_count']>0
    if data.get('oracle_status') in ['MATCHED_NATIVE_TREE_AND_PRISTINE_MODEL','MISMATCH_REQUIRES_REPRODUCTION']:
        o=read(e/'oracle.json');oracles+=1
        assert data['checked']==o['comparable_unique'],(r['repo'],'checked count')
        if data['outcome']=='CONFIRMED_LIB_BUG':
            assert len(o['mismatches'])==1 and not o['mismatches'][0]['missing']
            assert len(o['mismatches'][0]['extra'])==data['false_positive_findings']
            false_findings+=data['false_positive_findings']
        else:
            assert not o['mismatches']
            assert data['guard_warn_exit']==0 and data['guard_strict_exit']==int(bool(o['expected_drift']))
    for f in ['mutations.json','extras.json','gradle-audit.json','gradle-boundaries.json']:
        if (e/f).exists():assert all(x.get('verified') for x in read(e/f)),(r['repo'],f)
    if (e/'mutations.json').exists():
        cases=read(e/'mutations.json');core_suites+=1
        assert {x['scenario'] for x in cases}=={'direct','managed','allowed','incomplete','determinism','offline'} and len(cases)==6
        for x in cases:
            if 'runs' not in x:continue
            assert x['runs'][0]['exit']==0 and x['runs'][1]['exit'] in [0,1]
            if int(data['id']) in expanded:
                assert data['mutation_guard_sha']=='0c5888db559e174ee8f70d99969730ba1e6bcef0'
                available=[v for v in metadata_versions & cached_versions if re.fullmatch(r'\d+\.\d+\.\d+',v) and v!=x['expected'] and v.split('.')[:2]==x['expected'].split('.')[:2]]
                key=lambda v:tuple(map(int,v.split('.')))
                higher=[v for v in available if key(v)>key(x['expected'])]
                assert x['alternate']==(min(higher,key=key) if higher else max(available,key=key)),(r['repo'],x['scenario'],'metadata/cache selection')
    if (e/'benchmark.json').exists():
        b=read(e/'benchmark.json');benchmarks+=1
        assert len(b['runs'])==8 and len({x['graph_sha256'] for x in b['runs']})==1
        for mode in ['native','guard']:
            measured=[x for x in b['runs'] if x['mode']==mode and x['repeat']>0]
            assert len(measured)==3 and all(x['exit']==0 and x['peak_rss_mb']>0 for x in measured)
            assert round(statistics.median(x['elapsed_s'] for x in measured),3)==b['median'][mode]['elapsed_s']
    if (e/'artifact-control.json').exists():assert not read(e/'artifact-control.json')['native_artifacts_available']
assert oracles==30 and false_findings==202 and benchmarks==3 and core_suites==25
for pin in ['137b0026','0c5888db']:
    b=read(HERE/'bugs/BBG-001'/pin/'result.json')
    assert b['confirmed'] and b['repeat_identical'] and not b['oracle']['expected_drift']
    assert [x['exit'] for x in b['runs']]==[0,0,0,0,1]
missing=[]
for path in HERE.glob('*.md'):
    if path.name=='test-plan.md':continue
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):continue
        if not (path.parent/target.split('#')[0]).exists():missing.append((path.name,target))
assert not missing,missing
assert not read(HERE/'checkout-verification.json')['modifications']
assert not read(HERE/'sanitizer-verification.json')['findings']
assert read(HERE/'evidence/update/source-equivalence.json')['implementation_and_build_diff']==''
result=dict(candidates=100,quotas='25 each',native_model_comparisons=oracles,core_mutation_suites=core_suites,confirmed_defects=1,affected_repos=5,false_findings=false_findings,benchmark_graphs=benchmarks,local_markdown_links='all exist',tracked_target_changes=0,unexpected_sensitive_pattern_locations=0)
(HERE/'report-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
