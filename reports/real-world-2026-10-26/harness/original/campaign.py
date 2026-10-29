"""Evidence-only campaign tooling. Never executes a target build on the host."""
import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
WORK = Path(r'E:\tmp\bbg-campaign-137b0026')
CLONES = WORK / 'clones'
PILOT = {1, 2, 3, 9, 26, 27, 40, 41, 51, 57, 62, 68, 76, 77, 92, 95}
FIELDS = 'tier_proposed,tier_measured,repo,sha,build_root,build_tool,module_count,boot_version,bom_mechanism,jdk,baseline_status,scenario,guard_warn_exit,guard_strict_exit,drift_count,unknown_count,elapsed_s,peak_rss_mb,outcome,issue_id,evidence_path'.split(',')


def catalog():
    rows = []
    for line in (HERE / 'test-plan.md').read_text(encoding='utf-8').splitlines():
        match = re.match(r'\| (\d+) \| \[([^]]+)\]\(https://github.com/[^)]+\) \| ([^|]+) \|', line)
        if match:
            num, repo, tool = match.groups()
            num = int(num)
            rows.append(dict(id=num, repo=repo, tier_proposed=['Small', 'Medium', 'Large', 'Huge'][(num-1)//25], catalog_tool=tool.strip(), pilot=num in PILOT))
    assert len(rows) == 100 and len({r['repo'].lower() for r in rows}) == 100
    assert all(sum(r['tier_proposed'] == tier for r in rows) == 25 for tier in ['Small', 'Medium', 'Large', 'Huge'])
    return rows


def redact(value):
    value = re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@', r'\1[REDACTED]@', value)
    return re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b', '[REDACTED]', value)


def execute(args, cwd, evidence, timeout=240, env=None):
    evidence.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        p = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        output, code = p.stdout.decode('utf-8', errors='replace'), p.returncode
    except subprocess.TimeoutExpired as e:
        output, code = (e.stdout or b'').decode('utf-8', errors='replace') + '\nCAMPAIGN_TIMEOUT\n', 124
    duration = round(time.monotonic() - start, 3)
    evidence.write_text(redact(output), encoding='utf-8')
    evidence.with_suffix('.command.json').write_text(json.dumps(dict(command=args, cwd=str(cwd), exit=code, elapsed_s=duration, timeout_s=timeout), indent=2), encoding='utf-8')
    return code, duration, output


def strip_ns(tree):
    for element in tree.iter():
        element.tag = element.tag.split('}')[-1]
    return tree


def inspect_checkout(path):
    tracked = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '-z', 'HEAD'], cwd=path).decode('utf-8').split('\0')
    files = [path / p for p in tracked if Path(p).name in {'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts'} and (path / p).is_file()]
    info = []
    for file in files:
        text = file.read_text(encoding='utf-8', errors='replace')
        entry = dict(path=file.relative_to(path).as_posix(), tool='Maven' if file.name == 'pom.xml' else 'Gradle', boot=[], jdk=[], native_platform=False)
        if file.name == 'pom.xml':
            try:
                tree = strip_ns(ET.fromstring(text))
                entry['parent'] = {x.tag: x.text for x in tree.findall('./parent/*')}
                entry['properties'] = {x.tag: x.text for x in tree.findall('./properties/*')}
                entry['modules'] = [x.text for x in tree.findall('.//modules/module')]
                entry['plugins'] = [((p.findtext('groupId') or 'org.apache.maven.plugins') + ':' + str(p.findtext('artifactId'))) for p in tree.findall('.//plugins/plugin')]
                for d in tree.findall('.//dependency') + tree.findall('./parent'):
                    if d.findtext('groupId') == 'org.springframework.boot' and d.findtext('artifactId') in {'spring-boot-starter-parent', 'spring-boot-dependencies'}:
                        entry['boot'].append(d.findtext('version'))
                entry['jdk'] = [v for k, v in entry['properties'].items() if k in {'java.version', 'maven.compiler.release', 'maven.compiler.source', 'jdk.version'}]
            except ET.ParseError:
                entry['parse_error'] = True
        else:
            entry['boot'] = re.findall(r'(?:id\s*\(?\s*[\'"]org.springframework.boot[\'"]\s*\)?\s*version\s*[\'"]([^\'"]+)|spring-boot-dependencies:([^\'"\s)]+))', text)
            entry['native_platform'] = bool(re.search(r'(?:enforcedPlatform|platform)\s*\(?\s*[\'"]org.springframework.boot:spring-boot-dependencies', text))
            entry['jdk'] = re.findall(r'(?:JavaLanguageVersion.of\(|jvmToolchain\(|VERSION_)(\d+)', text)
            entry['dependency_management_dsl'] = 'io.spring.dependency-management' in text
        info.append(entry)
    return dict(build_file_count=len(files), builds=info, extensions=[p for p in tracked if p.endswith('extensions.xml')])


def clone(row):
    root = CLONES / (f"{row['id']:03d}-" + row['repo'].replace('/', '--'))
    evidence = HERE / 'evidence' / f"{row['id']:03d}"
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_LFS_SKIP_SMUDGE='1')
    if not (root / '.git').exists():
        code, duration, output = execute(['git', '-c', 'credential.helper=', '-c', 'core.hooksPath=NUL', '-c', 'core.longpaths=true', 'clone', '--depth=1', '--no-tags', 'https://github.com/' + row['repo'] + '.git', str(root)], HERE, evidence / 'clone.log', timeout=300, env=env)
        if code:
            row.update(outcome='ENV_BLOCKED', baseline_status='NOT_RUN', clone_exit=code, elapsed_s=duration)
            (evidence / 'inventory.json').write_text(json.dumps(row, indent=2), encoding='utf-8')
            return row
    old = evidence / 'inventory.json'
    if old.exists() and (json.loads(old.read_text()).get('clone_exit') == 128 or json.loads(old.read_text()).get('build_file_count') == 0):
        assert root.resolve().is_relative_to(CLONES.resolve())
        code, _, _ = execute(['git', '-c', 'core.longpaths=true', '-c', 'core.hooksPath=NUL', 'restore', '--source=HEAD', '--staged', '--worktree', '.'], root, evidence / 'checkout-retry.log')
        if code:
            return row
    code, duration, sha = execute(['git', 'rev-parse', 'HEAD'], root, evidence / 'sha.log')
    row.update(sha=sha.strip(), clone_path=str(root), **inspect_checkout(root), outcome='NOT_RUN', baseline_status='NOT_RUN')
    (evidence / 'inventory.json').write_text(json.dumps(row, indent=2), encoding='utf-8')
    print(f"{row['id']:03d} {row['repo']} {row['sha'][:12]} builds={row['build_file_count']}", flush=True)
    return row


def write_results():
    with (HERE / 'results.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, FIELDS)
        writer.writeheader()
        for entry in catalog():
            evidence = HERE / 'evidence' / f"{entry['id']:03d}"
            path = evidence / 'result.json'
            if not path.exists():
                path = evidence / 'inventory.json'
            data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else entry
            result = {field: data.get(field, '') for field in FIELDS}
            result.update(outcome=data.get('outcome', 'NOT_RUN'), baseline_status=data.get('baseline_status', 'NOT_RUN'), evidence_path=evidence.relative_to(HERE).as_posix() if evidence.exists() else '')
            writer.writerow(result)


def self_check():
    rows = catalog()
    assert sum(r['pilot'] for r in rows) == 16
    assert redact('https://user:secret@example.org/repo') == 'https://[REDACTED]@example.org/repo'
    assert strip_ns(ET.fromstring('<p xmlns="x"><v>4</v></p>')).findtext('v') == '4'
    print('self-check: catalog quotas, unique identities, pilot quotas, redaction, XML namespaces passed')


def prepare_guard():
    source = HERE.parents[1]
    target = WORK / 'guard'
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=source).decode().split('\0')
    for name in filter(None, files):
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, dest)
    print(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['self-check', 'clone-pilot', 'clone-rest', 'results', 'prepare-guard'])
    args = parser.parse_args()
    if args.action == 'self-check':
        self_check()
    elif args.action == 'prepare-guard':
        prepare_guard()
    elif args.action.startswith('clone'):
        CLONES.mkdir(parents=True, exist_ok=True)
        selected = [r for r in catalog() if r['pilot'] == (args.action == 'clone-pilot')]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(clone, selected))
        write_results()
    else:
        write_results()
