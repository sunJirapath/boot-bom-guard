"""Record the fast-forward and install its unchanged Java implementation."""
import json
from pathlib import Path
import subprocess
from campaign import HERE, WORK, execute
from run_builds import container

OLD='137b0026e3fd24952a0aa5eccc8a89b448196e16'
def main():
    source=HERE.parent.parent
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source).decode().strip()
    paths=['core','maven-plugin','gradle-plugin','pom.xml','build.gradle.kts','settings.gradle.kts','scripts','gradle','gradlew','gradlew.bat']
    diff=subprocess.check_output(['git','diff','--name-only',OLD,sha,'--']+paths,cwd=source).decode()
    assert not diff, 'Implementation/build changed: prior evidence cannot be reused'
    dest=WORK/'guard-latest';dest.mkdir(exist_ok=True)
    files=subprocess.check_output(['git','ls-tree','-r','--name-only',sha],cwd=source).decode().splitlines()
    for f in files:
        target=dest/f;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(subprocess.check_output(['git','show',sha+':'+f],cwd=source))
    e=HERE/'evidence/update';e.mkdir(exist_ok=True)
    record=dict(original_guard_sha=OLD,updated_guard_sha=sha,implementation_and_build_diff=diff,changed_files=subprocess.check_output(['git','diff','--name-only',OLD,sha],cwd=source).decode().splitlines())
    (e/'source-equivalence.json').write_text(json.dumps(record,indent=2))
    run,out=container(dict(id='latest-install',clone_path=str(dest)),e,'install',['mvn','-B','-ntp','install'],timeout=240)
    record['install']=run;(e/'source-equivalence.json').write_text(json.dumps(record,indent=2))
    assert run['exit']==0
    print('Installed updated guard',sha,flush=True)
if __name__=='__main__':main()
