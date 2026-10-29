"""Run after mutations: verify pinned clean targets and scan retained text evidence."""
import datetime
import json
import re
import subprocess
from campaign import HERE, CLONES, catalog


def main():
    modifications=[]
    records=[]
    for entry in catalog():
        row=json.loads((HERE/'evidence'/format(entry['id'],'03')/'result.json').read_text())
        root=CLONES/(format(entry['id'],'03')+'-'+entry['repo'].replace('/','--'))
        assert root.resolve().is_relative_to(CLONES.resolve()) and str(root)==row['clone_path']
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        # Match the long-path checkout setting; otherwise Git falsely reports missing Windows paths.
        status=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain=v1','--untracked-files=no'],cwd=root,text=True)
        assert sha==row['sha'],(entry['repo'],'pin changed')
        records.append(dict(id=entry['id'],repo=entry['repo'],sha=sha))
        if status:modifications.append(dict(repo=entry['repo'],tracked_status=status))
    (HERE/'checkout-verification.json').write_text(json.dumps(dict(inspected=len(records),verified_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),commands=['git rev-parse HEAD','git -c core.longpaths=true status --porcelain=v1 --untracked-files=no'],modifications=modifications,pins=records),indent=2))
    patterns={
        'URL userinfo':re.compile(r'https?://[^\s/@\[\]<>\"\']+:[^\s/@\[\]<>\"\']+@'),
        'GitHub token':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b'),
        'Private key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    }
    findings=[];scanned=0
    for path in HERE.rglob('*'):
        if not path.is_file() or path.suffix not in {'.log','.json','.xml','.md','.csv','.patch','.txt','.gradle','.kts'}:continue
        scanned+=1
        for number,line in enumerate(path.read_text(encoding='utf-8',errors='replace').splitlines(),1):
            # These exact fake credentials are deliberate test inputs, never host secrets.
            clean=line.replace('audit-user:audit-sentinel-password','SYNTHETIC').replace('user:secret','SYNTHETIC')
            for name,pattern in patterns.items():
                if pattern.search(clean):findings.append(dict(path=path.relative_to(HERE).as_posix(),line=number,pattern=name))
    (HERE/'sanitizer-verification.json').write_text(json.dumps(dict(scanned_text_files=scanned,synthetic_exclusions=['audit-user:audit-sentinel-password','user:secret'],findings=findings),indent=2))
    assert len(records)==100 and not modifications,modifications
    assert not findings,findings
    print('Pinned clean targets:',len(records),'scanned text files:',scanned,'unexpected sensitive-pattern locations:',len(findings))


if __name__=='__main__':main()
