"""Retain wrapper and static structure evidence without executing target scripts."""
import json
from pathlib import Path
import re
from campaign import HERE, catalog

for c in catalog():
    e=HERE/'evidence'/f"{c['id']:03}";r=json.loads((e/'result.json').read_text());root=Path(r['clone_path'])
    build=root/r['build_root'];ancestors=[build.parent]+[p for p in build.parent.parents if p==root or root in p.parents]
    wrappers=[]
    for parent in dict.fromkeys(ancestors):
        for relative in ['gradle/wrapper/gradle-wrapper.properties','.mvn/wrapper/maven-wrapper.properties']:
            p=parent/relative
            if p.exists():wrappers.append(dict(path=p.relative_to(root).as_posix(),distribution=[line for line in p.read_text(errors='replace').splitlines() if line.startswith('distributionUrl=')]))
    inspection=dict(repo=r['repo'],sha=r['sha'],selected_build=r['build_root'],wrappers=wrappers,declared_build_files=len(r['builds']),maven_pom_files=sum(b['tool']=='Maven' for b in r['builds']),gradle_build_scripts=sum(Path(b['path']).name.startswith('build.gradle') for b in r['builds']),selected_scope_project_count=1,scope_note='Inventory includes independent examples, BOMs, buildSrc and aggregation projects; this is not a resolved whole-repository project count.',structure=r['builds'])
    (e/'inspection.json').write_text(json.dumps(inspection,indent=2))
assert len(list((HERE/'evidence').glob('[0-9][0-9][0-9]/inspection.json')))==100
print('100 wrapper/structure inspections retained')
