"""Native Gradle oracle for a real platform consumer, no guard implementation imported."""
import sys,json
from pathlib import Path
from retry import *
from audit_gradle import INIT,check

def verify(num):
 d=OUT/f'{num:03d}'; row=load(num)
 args=json.loads((d/'wrapper-native.command.json').read_text())['command']
 args=[x.replace('source=bbg-revisit-gradle-20261026','source=bbg-revisit-gradle-oracle-20261026') for x in args]
 # The original wrapper/runtime/toolchains are retained verbatim.
 idx=args.index('--name');args[idx+1]=f'bbg-revisit-{num}-rich-native'
 init=INIT.replace("allprojects {", "allprojects { p ->\n  if (p.path != System.getProperty('bbg.target')) return")
 init=init.replace("file('.bbg/gradle-native.json')","new File('/out/native-rich.json')")
 (d/'native-rich.init.gradle').write_text(init,encoding='utf-8')
 args[args.index('/out/native.init.gradle')]='/out/native-rich.init.gradle'
 result=json.loads((d/'result.json').read_text())
 args[-1]=result['target'].rstrip(':')+':bbgNativeOracle'
 code,_,log=execute(args,OUT,d/'rich-native.log',timeout=600);assert code==0,log[-5000:]
 native=json.loads((d/'native-rich.json').read_text());keys=sorted({m['key'] for g in native.values() for m in g['modules'] if m['library']})
 versions={m['version'] for g in native.values() for m in g['modules'] if m['key']=='org.springframework.boot:spring-boot-dependencies'}
 assert len(versions)==1,versions
 version=versions.pop()
 clean=d/'pristine-gradle';clean.mkdir(exist_ok=True)
 (clean/'settings.gradle').write_text("rootProject.name='bbg-pristine'\n")
 requests='\n'.join(f' implementation("{k}") {{ transitive = false }}' for k in keys)
 (clean/'build.gradle').write_text("plugins { id 'java' }\nrepositories { mavenCentral() }\ndependencies {\n implementation(platform('org.springframework.boot:spring-boot-dependencies:"+version+"'))\n"+requests+'\n}\n')
 (d/'pristine.init.gradle').write_text(INIT.replace("file('.bbg/gradle-native.json')","new File('/out/pristine-native.json')"))
 image=args.index('gradle@sha256:21bd311ed01360c189b8870c6b6e988199ff10f72d445d02fb39d3cff9da91d7')
 command=args[:image+1]+['gradle','--no-daemon','--no-scan','--console=plain','--max-workers=2','-Dorg.gradle.jvmargs=-Xmx1536m','-I','/out/pristine.init.gradle','-p','/out/pristine-gradle','bbgNativeOracle']
 command[command.index('--name')+1]=f'bbg-revisit-{num}-pristine'
 code,_,log=execute(command,OUT,d/'pristine-gradle.log',timeout=600);assert code==0,log[-5000:]
 pristine=json.loads((d/'pristine-native.json').read_text())
 result=check(native,pristine,(d/'guard-warning.log').read_text())
 assert len(result)==4 and not any(x['mismatch'] for x in result.values()),result
 r=json.loads((d/'result.json').read_text());assert r['warning_exit']==0 and r['strict_exit']==1 and r['repeat_identical']
 r.update(oracle_verified=True,outcome='DRIFT',oracle=result)
 (d/'result.json').write_text(json.dumps(r,indent=2))
 print(num,'four classpaths independently verified',flush=True)

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--ids',type=int,nargs='+',default=[49]);a=p.parse_args()
 for num in a.ids:verify(num)
