"""One controlled Maven profile at a time, always restoring original bytes."""
import argparse
import difflib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat
from campaign import HERE, strip_ns, write_results
from run_builds import GOAL, HELP, TREE, container, flatten_tree, load, maven
from oracle import compare, findings, management


def profile(source, content):
    assert b'<id>bbg-audit</id>' not in source
    stack, positions = [], {}
    parser = expat.ParserCreate()
    def start(name, attrs):
        stack.append(name.split(':')[-1])
    def end(name):
        if stack == ['project', 'profiles']:
            positions['profiles'] = parser.CurrentByteIndex
        elif stack == ['project']:
            positions['project'] = parser.CurrentByteIndex
        stack.pop()
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.Parse(source, True)
    added = '\n<profile><id>bbg-audit</id>' + content + '</profile>\n'
    if 'profiles' in positions:
        index = positions['profiles']
    else:
        index = positions['project']
        added = '\n<profiles>' + added + '</profiles>\n'
    result = source[:index] + added.encode() + source[index:]
    ET.fromstring(result)
    return result


def report_text(log):
    match = re.search(r'boot-bom-guard BOM=.*?\n(?:PASS|WARN) checked=\d+ drift=\d+ unknown=\d+', log, re.S)
    return match.group(0) if match else None


def mutate(num, offline_all=False, refresh_results=True):
    inv, evidence = load(num)
    row = json.loads((evidence / 'result.json').read_text())
    assert row.get('oracle_status') == 'MATCHED_NATIVE_TREE_AND_PRISTINE_MODEL', 'Run the baseline oracle first'
    pom, root = row['build_root'], Path(row['clone_path'])
    path = root / pom
    original = path.read_bytes()
    expected = management((evidence / 'pristine.xml').read_bytes())
    actual = json.loads((evidence / 'tree.json').read_text())
    coord = 'org.slf4j:slf4j-api'
    assert coord in expected and any(n['groupId'] + ':' + n['artifactId'] == coord for n in flatten_tree(actual)[1:]), 'Mutation coordinate must be managed and present'
    if offline_all:
        metadata = (HERE/'evidence/002/alternate-metadata.log').read_text()
    else:
        run, metadata = container(row, evidence, 'alternate-metadata', ['curl', '-fsS', 'https://repo.maven.apache.org/maven2/org/slf4j/slf4j-api/maven-metadata.xml'])
        assert run['exit'] == 0
    versions = [n.text for n in ET.fromstring(metadata).findall('./versioning/versions/version') if re.fullmatch(r'\d+\.\d+\.\d+', n.text or '')]
    version_key = lambda x: tuple(map(int, x.split('.')))
    higher = [v for v in versions if version_key(v) > version_key(expected[coord])]
    alternate = min(higher, key=version_key) if higher else max((v for v in versions if v != expected[coord]), key=version_key)
    if offline_all:
        cached = set(re.findall(r'/slf4j-api/([^/]+)/slf4j-api-[^/]+\.jar', (HERE/'evidence/002/cached-alternates.log').read_text()))
        available = [v for v in versions if v in cached and v != expected[coord] and v.split('.')[:2] == expected[coord].split('.')[:2]]
        assert available, 'A different same-line version must exist in captured metadata and the artifact cache'
        higher = [v for v in available if version_key(v) > version_key(expected[coord])]
        alternate = min(higher,key=version_key) if higher else max(available,key=version_key)
    dep = f'<dependency><groupId>org.slf4j</groupId><artifactId>slf4j-api</artifactId><version>{alternate}</version></dependency>'
    allowed = '<build><plugins><plugin><groupId>io.github.bootbomguard</groupId><artifactId>boot-bom-guard-maven-plugin</artifactId><version>0.1.0-SNAPSHOT</version><configuration><exceptions><exception><dependency>org.slf4j:slf4j-api</dependency><reason>Campaign intentional exception</reason></exception></exceptions></configuration></plugin></plugins></build>'
    scenarios = [
        ('direct', '<dependencies>' + dep + '</dependencies>', 'DIRECT_OVERRIDE'),
        ('managed', '<dependencyManagement><dependencies>' + dep + '</dependencies></dependencyManagement>', 'MANAGED_OVERRIDE'),
        ('allowed', '<dependencies>' + dep + '</dependencies>' + allowed, 'DIRECT_OVERRIDE'),
        ('incomplete', '<dependencies><dependency><groupId>guard.audit</groupId><artifactId>deliberately-missing</artifactId><version>1</version></dependency></dependencies>', None),
    ]
    results = []
    for name, contents, classification in scenarios:
        mutated = profile(original, contents)
        (evidence / f'{name}.patch').write_text(''.join(difflib.unified_diff(original.decode().splitlines(True), mutated.decode().splitlines(True), fromfile=pom, tofile=pom)))
        try:
            path.write_bytes(mutated)
            flags = ['-Pbbg-audit']
            if name == 'incomplete' or offline_all:
                flags += ['--offline']
            native_goals = [TREE.replace(':tree', ':resolve')] if name == 'incomplete' else [TREE]
            native, native_log = container(row, evidence, name + '-native', maven(pom, native_goals, flags + ['-DoutputType=json', f'-DoutputFile=/work/.bbg/{name}-tree.json']), network=name != 'incomplete' and not offline_all)
            runs, logs = [], []
            for mode, mode_flags in [('warning', []), ('strict', ['-DbootBomGuard.failOnDrift=true'])]:
                run, out = container(row, evidence, name + '-' + mode, maven(pom, [GOAL], flags + mode_flags), network=name != 'incomplete' and not offline_all)
                runs.append(run)
                logs.append(out)
            result = dict(scenario=name, coordinate=coord, expected=expected[coord], alternate=alternate, native=native, runs=runs)
            if name == 'incomplete':
                result['verified'] = native['exit'] != 0 and runs[0]['exit'] == 0 and runs[1]['exit'] != 0 and 'UNKNOWN Maven model/dependency resolution failed' in logs[0]
            elif native['exit'] == 0:
                data = (root / '.bbg' / f'{name}-tree.json').read_bytes()
                (evidence / f'{name}-tree.json').write_bytes(data)
                oracle = compare(json.loads(data), expected, logs[0])
                result['oracle'] = oracle
                finding = findings(logs[0]).get(coord, {})
                remaining = set(oracle['expected_drift']) - ({coord} if name == 'allowed' else set())
                result['verified'] = not oracle['mismatches'] and finding.get('resolved') == alternate and finding.get('classification') == classification and runs[0]['exit'] == 0 and bool(runs[1]['exit']) == bool(remaining)
                if name == 'allowed':
                    result['verified'] &= f'ALLOWED {coord} ' in logs[0]
            else:
                result['verified'] = False
                result['blocked'] = 'Native mutated graph did not resolve'
            results.append(result)
            print(f'{num:03d} {name} verified={result["verified"]}', flush=True)
        finally:
            path.write_bytes(original)
        (evidence / 'mutations.json').write_text(json.dumps(results, indent=2))
    original_report = report_text((evidence / 'original-warning.log').read_text())
    for label, flags, network in [('determinism', ['--offline'] if offline_all else [], not offline_all), ('offline', ['--offline'], False)]:
        run, log = container(row, evidence, label, maven(pom, [GOAL], flags), network=network)
        results.append(dict(scenario=label, run=run, verified=run['exit'] == 0 and original_report == report_text(log)))
    (evidence / 'mutations.json').write_text(json.dumps(results, indent=2))
    row['scenario'] += ';' + ';'.join(x['scenario'] + ('=verified' if x['verified'] else '=unverified') for x in results)
    if offline_all:row['mutation_guard_sha']='0c5888db559e174ee8f70d99969730ba1e6bcef0'
    (evidence / 'result.json').write_text(json.dumps(row, indent=2))
    if refresh_results:write_results()


def self_check():
    for source in [b'<project><modelVersion>4.0.0</modelVersion></project>', b'<project><profiles><profile><id>other</id></profile></profiles></project>']:
        result = strip_ns(ET.fromstring(profile(source, '<properties><x>y</x></properties>')))
        assert result.findtext('./profiles/profile[id="bbg-audit"]/properties/x') == 'y'
        assert len(result.findall('./profiles')) == 1
    assert report_text('[WARNING] boot-bom-guard BOM=x\nDRIFT x:a expected=1 resolved=2\nWARN checked=1 drift=1 unknown=0\n[INFO] BUILD SUCCESS')
    print('mutation self-check: existing/new profile insertion, parseability and stable report extraction passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='*', type=int, default=[2, 26, 51, 77])
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check()
    else:
        for num in args.ids:
            mutate(num)
