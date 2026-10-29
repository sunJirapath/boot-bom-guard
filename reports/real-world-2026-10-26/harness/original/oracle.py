"""Independent Maven effective-model/tree oracle; no guard implementation imported."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from campaign import HERE, strip_ns, write_results
from run_builds import HELP, container, flatten_tree, load, maven


def key(group, artifact, kind='jar', classifier=''):
    kind, classifier = kind or 'jar', classifier or ''
    return f'{group}:{artifact}' + ('' if kind == 'jar' and not classifier else f':{kind}:{classifier}')


def management(xml):
    root = strip_ns(ET.fromstring(xml))
    result = {}
    for d in root.findall('./dependencyManagement/dependencies/dependency'):
        kind = d.findtext('type', 'jar')
        classifier = d.findtext('classifier', 'tests' if kind == 'test-jar' else '')
        result[key(d.findtext('groupId'), d.findtext('artifactId'), kind, classifier)] = d.findtext('version')
    return result


def findings(log):
    return {m[0]: dict(expected=m[1], resolved=m[2], classification=m[3]) for m in re.findall(r'^(?:DRIFT|ALLOWED) (\S+) expected=(\S+) resolved=(\S+) classification=(\S+)', log, re.M)}


def compare(tree, expected, log):
    nodes = flatten_tree(tree)[1:]
    actual = {key(n['groupId'], n['artifactId'], n.get('type'), n.get('classifier')): n['version'] for n in nodes}
    compared = {k: v for k, v in actual.items() if k in expected}
    drift = {k: dict(expected=expected[k], resolved=v) for k, v in compared.items() if expected[k] != v}
    reported = findings(log)
    mismatches = []
    if drift.keys() != reported.keys():
        mismatches.append(dict(missing=sorted(drift.keys() - reported.keys()), extra=sorted(reported.keys() - drift.keys())))
    for k in drift.keys() & reported.keys():
        if any(drift[k][field] != reported[k][field] for field in ('expected', 'resolved')):
            mismatches.append(dict(coordinate=k, native=drift[k], guard=reported[k]))
    return dict(native_nodes=len(nodes), native_unique=len(actual), comparable_unique=len(compared), expected_drift=drift, guard_findings=reported, mismatches=mismatches)


def run(num):
    inventory, evidence = load(num)
    result_path = evidence / 'result.json'
    if not result_path.exists():
        return
    row = json.loads(result_path.read_text())
    if row.get('build_tool') != 'Maven' or row.get('oracle_status') != 'PENDING_PRISTINE_BOM_COMPARISON':
        return
    version = row['boot_version']
    assert re.fullmatch(r'4\.[A-Za-z0-9_.-]+', version)
    pom = f'/root/.m2/repository/org/springframework/boot/spring-boot-dependencies/{version}/spring-boot-dependencies-{version}.pom'
    run, out = container(row, evidence, 'pristine-bom', ['mvn', '-B', '-ntp', '-N', '-f', pom, HELP, '-Doutput=/work/.bbg/pristine.xml'])
    source = Path(row['clone_path']) / '.bbg/pristine.xml'
    if run['exit'] or not source.exists():
        row.update(outcome='ENV_BLOCKED', oracle_status='PRISTINE_MODEL_BLOCKED')
    else:
        data = source.read_bytes()
        (evidence / 'pristine.xml').write_bytes(data)
        oracle = compare(json.loads((evidence / 'tree.json').read_text()), management(data), (evidence / 'original-warning.log').read_text())
        (evidence / 'oracle.json').write_text(json.dumps(oracle, indent=2))
        row['oracle_status'] = 'MISMATCH_REQUIRES_REPRODUCTION' if oracle['mismatches'] else 'MATCHED_NATIVE_TREE_AND_PRISTINE_MODEL'
        row['outcome'] = 'SUSPECTED_LIB_BUG' if oracle['mismatches'] else ('DRIFT_DETECTED_CORRECTLY' if oracle['expected_drift'] else 'PASS_EXPECTED')
        if row['guard_warn_exit'] != 0 or row['guard_strict_exit'] != bool(oracle['expected_drift']):
            row.update(outcome='SUSPECTED_LIB_BUG', policy_mismatch=True)
        row['native_comparable_unique'] = oracle['comparable_unique']
    (evidence / 'pristine-run.json').write_text(json.dumps(run, indent=2))
    result_path.write_text(json.dumps(row, indent=2))
    print(f'{num:03d} oracle {row["oracle_status"]} {row["outcome"]}', flush=True)


def self_check():
    xml = '<project><dependencyManagement><dependencies><dependency><groupId>x</groupId><artifactId>a</artifactId><version>1</version></dependency></dependencies></dependencyManagement></project>'
    assert management(xml) == {'x:a': '1'}
    tree = dict(groupId='x', artifactId='root', version='1', children=[dict(groupId='x', artifactId='a', version='2')])
    assert not compare(tree, management(xml), 'DRIFT x:a expected=1 resolved=2 classification=DIRECT_OVERRIDE')['mismatches']
    assert compare(tree, management(xml), 'PASS')['mismatches'][0]['missing'] == ['x:a']
    print('oracle self-check: exact type/classifier keys, native drift, omitted finding detection passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='*', type=int)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check()
    else:
        for num in args.ids or [int(p.parent.name) for p in (HERE / 'evidence').glob('*/result.json')]:
            run(num)
        write_results()
