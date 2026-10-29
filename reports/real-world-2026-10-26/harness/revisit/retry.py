"""Retry frozen public consumers in isolated containers; preserve the first audit."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import shutil
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
OLD = Path(r'E:\boot-bom-guard\reports\real-world-2026-10-25')
sys.path.insert(0, str(OLD))
from campaign import execute
from run_builds import MAVEN_IMAGE, GOAL, TREE, HELP, maven
from oracle import compare, management

OUT = Path(r'E:\tmp\bbg-revisit-20261026')
CACHE = 'bbg-revisit-m2-20261026'
RESOLVE = 'org.apache.maven.plugins:maven-dependency-plugin:3.10.0:resolve'
IDS = [18, 44, 85, 86, 89, 81, 84, 88, 90, 91, 98, 83, 87, 93]

def git(root, *args):
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', *args], cwd=root, text=True).strip()

def load(num):
    return json.loads((OLD / 'evidence' / f'{num:03d}' / 'result.json').read_text(encoding='utf-8'))

def run(row, label, args, timeout=480, network=True, jdk=None):
    directory = OUT / f"{row['id']:03d}"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"bbg-revisit-{row['id']}-{label}"[:100]
    command = ['docker', 'run', '--rm', '--name', name, '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--memory', '3g', '--cpus', '2', '--pids-limit', '512',
               '--mount', f"type=bind,source={row['clone_path']},target=/work",
               '--mount', f'type=bind,source={directory},target=/out',
               '--mount', f'type=volume,source={CACHE},target=/root/.m2',
               '-w', '/work', '-e', 'CI=true', '-e', 'MAVEN_OPTS=-Xmx2g']
    if not network:
        command += ['--network', 'none']
    if jdk:
        command += ['--mount', 'type=volume,source=bbg-revisit-toolchains-20261026,target=/toolchains,readonly', '-e', f'JAVA_HOME=/toolchains/{jdk}']
    code, duration, output = execute(command + [MAVEN_IMAGE] + args, OUT, directory / (label + '.log'), timeout=timeout)
    if code == 124:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=30)
    result = dict(label=label, exit=code, elapsed_s=duration)
    print(f"{row['id']:03d} {label}: exit={code} seconds={duration}", flush=True)
    return result, output

def retry(num):
    row = load(num)
    root = Path(row['clone_path'])
    assert git(root, 'rev-parse', 'HEAD') == row['sha']
    assert not git(root, 'status', '--porcelain=v1', '--untracked-files=no')
    result = {k: row.get(k) for k in ['id','repo','sha','build_root','build_tool','tier_proposed','boot_version']}
    result.update(previous_outcome=row['outcome'], runs=[], outcome='BASELINE_BLOCKED')
    directory = OUT / f'{num:03d}'
    directory.mkdir(parents=True, exist_ok=True)
    if (directory/'result.json').exists():
        history=directory/'history'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        history.mkdir(parents=True)
        for file in directory.iterdir():
            if file.is_file():shutil.copyfile(file,history/file.name)
    def invoke(label, goals, flags=(), **kwargs):
        r, log = run(row, label, maven(row['build_root'], goals, flags), **kwargs)
        result['runs'].append(r)
        (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return r['exit'], log
    try:
        code, output = invoke('native-online', [HELP, TREE], ['-Doutput=/out/effective.xml', '-DoutputFile=/out/tree.json', '-DoutputType=json'])
        if code:
            result['blocker'] = output[-10000:]
            return
        code, output = invoke('artifacts-online', [RESOLVE])
        if code:
            result.update(outcome='ARTIFACTS_BLOCKED', blocker=output[-10000:])
            return
        result['baseline'] = 'NATIVE_METADATA_AND_ARTIFACTS_PASSED'
        code, output = invoke('warning', [GOAL])
        result['warning_exit'] = code
        counts = re.search(r'(PASS|WARN) checked=(\d+) drift=(\d+) unknown=(\d+)', output)
        if counts:
            result.update(checked=int(counts[2]), drift=int(counts[3]), unknown=int(counts[4]), summary=counts[0])
        code, strict = invoke('strict', [GOAL], ['-DbootBomGuard.failOnDrift=true'])
        result['strict_exit'] = code
        result['outcome'] = 'GUARD_UNKNOWN' if result.get('unknown', 1) else ('DRIFT' if result['drift'] else 'PASS')
        if not result.get('unknown', 1):
            bom = re.search(r'boot-bom-guard BOM=org.springframework.boot:spring-boot-dependencies:([^\s]+)', output)
            if bom:
                version = bom[1]
                result['boot_version'] = version
                command = ['mvn','-B','-ntp','-N','-f',f'/root/.m2/repository/org/springframework/boot/spring-boot-dependencies/{version}/spring-boot-dependencies-{version}.pom', HELP, '-Doutput=/out/pristine.xml']
                r, _ = run(row, 'pristine', command)
                result['runs'].append(r)
                if not r['exit']:
                    oracle = compare(json.loads((directory/'tree.json').read_text()), management((directory/'pristine.xml').read_bytes()), output)
                    result['oracle'] = oracle
                    result['oracle_verified'] = not oracle['mismatches']
            code, repeated = invoke('repeat-offline', [GOAL], ['--offline'], network=False)
            def report(log):
                start = log.find('boot-bom-guard BOM=')
                end = re.search(r'(PASS|WARN) checked=\d+ drift=\d+ unknown=\d+', log)
                return log[start:end.end()] if start >= 0 and end else None
            result['repeat_identical'] = code == 0 and report(output) == report(repeated)
    finally:
        assert git(root, 'rev-parse', 'HEAD') == row['sha']
        assert not git(root, 'status', '--porcelain=v1', '--untracked-files=no')
        (directory/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='+', type=int, default=IDS)
    args=parser.parse_args()
    assert len(IDS) == len(set(IDS)) and len(IDS) == 14
    for num in args.ids:
        retry(num)
