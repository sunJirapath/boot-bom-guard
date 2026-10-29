"""Render reports only from retained command results and independent resolver evidence."""
import collections
import csv
import datetime
import json
from pathlib import Path
import re
from campaign import HERE, catalog, write_results

TIERS=['Small','Medium','Large','Huge']
OUTCOMES=['PASS_EXPECTED','DRIFT_DETECTED_CORRECTLY','EXPECTED_UNSUPPORTED','ENV_BLOCKED','BASELINE_BROKEN','CONFIRMED_LIB_BUG','SUSPECTED_LIB_BUG','NOT_RUN']
def read(path,default=None):return json.loads(path.read_text()) if path.exists() else default
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(map(str,headers))+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in rows])+'\n'
def link(n,name='result.json'):return f'[#{n:03}](evidence/{n:03}/{name})'

def main():
    rows=[];coverage=[]
    for entry in catalog():
        e=HERE/'evidence'/f"{entry['id']:03}"
        r=read(e/'result.json');assert r and r.get('outcome') not in ['NOT_RUN','SUSPECTED_LIB_BUG'],entry['id']
        assert re.fullmatch('[a-f0-9]{40}',r['sha'])
        r['selected_scope']='One selected consumer project; additional reactors/controlled projects are separate experiments'
        r.setdefault('declared_module_count',r.get('module_count'))
        r['module_count']=1
        if r.get('build_tool')=='Gradle':
            build=next((b for b in r['builds'] if b['path']==r['build_root']),{})
            r['jdk']=','.join(build.get('jdk',[])) or 'declared via conventions; runtime 21'
            declared=[v for pair in build.get('boot',[]) for v in pair if v]
            r['boot_version']='native BOM unknown'+(' (declared '+','.join(declared)+')' if declared else '')
            r['module_count']=1
            native=read(e/'gradle-native-original.json')
            if native:r['native_graph_nodes']=len([n for n in native.get('runtimeClasspath',{}).get('modules',[]) if n['library']])
        if r.get('native_graph_nodes'):
            # Explicitly size the selected consumer graph, never infer a whole monorepo size.
            r['tier_measured']='Small' if r['native_graph_nodes']<=150 else 'Medium' if r['native_graph_nodes']<=500 else 'Large' if r['native_graph_nodes']<=1500 else 'Huge'
        coverage.append(dict(id=r['id'],repo=r['repo'],scenario='native-resolution-baseline',status='METADATA_ONLY' if (e/'artifact-control.json').exists() else 'RESOLUTION_COMPLETED' if r.get('baseline_status')=='RESOLUTION_PASSED' else 'BLOCKED',evidence=f"evidence/{r['id']:03}/baseline.log"))
        mutations=read(e/'mutations.json',[])
        experiments=mutations+read(e/'extras.json',[])
        for file,prefix in [('gradle-audit.json','native-platform/'),('gradle-boundaries.json','controlled-subproject/')]:
            a=read(e/file,[])
            if isinstance(a,list):
                for x in a:experiments.append(dict(x,scenario=prefix+x['scenario']))
        for file in ['security.json','reactor.json']:
            a=read(e/file)
            if a:experiments.append(a)
        if r['id']==77:
            a=next(x for x in experiments if x['scenario']=='reactor-pl-am-T2')
            a['interpretation']='Expected UNKNOWN in non-consumer aggregation projects; strict stops before consumer. Not a guard bug.'
            a['policy_verified']=a['runs'][0]['exit']==0 and a['runs'][1]['exit']==0 and a['runs'][2]['exit']!=0
            (e/'reactor.json').write_text(json.dumps(a,indent=2))
        for x in experiments:
            coverage.append(dict(id=r['id'],repo=r['repo'],scenario=x['scenario'],status='VERIFIED' if x.get('verified') else 'EXPECTED_BOUNDARY' if x.get('policy_verified') else 'BLOCKED' if x.get('blocked') else 'NOT_VERIFIED',evidence=f"evidence/{r['id']:03}"))
        if 'guard_warn_exit' in r:
            coverage.append(dict(id=r['id'],repo=r['repo'],scenario='original-warning-strict',status='BUG_CONFIRMED' if r['outcome']=='CONFIRMED_LIB_BUG' else 'VERIFIED' if r['outcome'] in ['PASS_EXPECTED','DRIFT_DETECTED_CORRECTLY','EXPECTED_UNSUPPORTED'] else 'INCOMPLETE',evidence=f"evidence/{r['id']:03}"))
            out=(e/'original-warning.log').read_text()
            if r['outcome']=='EXPECTED_UNSUPPORTED':
                name='missing-native-BOM' if 'Missing Spring Boot BOM' in out else 'unsupported-Boot-major'
                coverage.append(dict(id=r['id'],repo=r['repo'],scenario=name,status='VERIFIED',evidence=f"evidence/{r['id']:03}/original-warning.log"))
        r['scenario']=';'.join(dict.fromkeys(r.get('scenario','').split(';')+[x['scenario']+'='+('verified' if x.get('verified') else 'expected-boundary' if x.get('policy_verified') else 'blocked') for x in experiments if x not in mutations]))
        bench=read(e/'benchmark.json')
        if bench:coverage.append(dict(id=r['id'],repo=r['repo'],scenario='matched-offline-performance',status='VERIFIED',evidence=f"evidence/{r['id']:03}/benchmark.json"))
        (e/'result.json').write_text(json.dumps(r,indent=2));rows.append(r)
    write_results()
    with (HERE/'coverage.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,['id','repo','scenario','status','evidence']);w.writeheader();w.writerows(coverage)
    grouped=[]
    for tier in TIERS:
        for tool in ['Maven','Gradle']:
            subset=[r for r in rows if r['tier_proposed']==tier and r['build_tool']==tool]
            if subset:grouped.append([tier,tool,len(subset)]+[sum(r['outcome']==o for r in subset) for o in OUTCOMES if any(x['outcome']==o for x in rows)])
    active=[o for o in OUTCOMES if any(r['outcome']==o for r in rows)]
    counts=collections.Counter(r['outcome'] for r in rows)
    baseline_guard=sum('guard_warn_exit' in r for r in rows)
    comparable=[r for r in rows if r.get('oracle_status') in ['MATCHED_NATIVE_TREE_AND_PRISTINE_MODEL','MISMATCH_REQUIRES_REPRODUCTION']]
    boot4=[r for r in rows if str(r.get('boot_version','')).startswith('4.')]
    benches=[(r,read(HERE/'evidence'/f"{r['id']:03}/benchmark.json")) for r in rows if (HERE/'evidence'/f"{r['id']:03}/benchmark.json").exists()]
    pilot=[r for r in rows if r['pilot']]
    measured=collections.Counter(r['tier_measured'] for r in rows)
    core_suites=sum(len(read(HERE/'evidence'/f"{r['id']:03}/mutations.json",[]))==6 and all(x['verified'] for x in read(HERE/'evidence'/f"{r['id']:03}/mutations.json",[])) for r in rows)
    summary=f'''# Real-world investigation — 100 catalog candidates

Generated {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}. No guard fixes, target upstream pushes, Boot migrations, application deployments, or external services.

All **100 repositories were cloned, pinned, inspected, and given an unmodified native-resolution baseline attempt**. **{baseline_guard} received original-project warning/strict guard runs**. Outcomes: '''+', '.join(f'**{v} {k}**' for k,v in counts.items())+f'''. These are candidate outcomes, not 100 successful integrations.

**One confirmed defect, BBG-001:** timestamped Maven SNAPSHOT artifacts are incorrectly compared to the BOM's `-SNAPSHOT` alias, producing **202 false findings across five repositories** and strict-mode failures. No separate false-negative, crash, nondeterminism, or credential-leak defect was confirmed in the exercised cases.

## Pin and environment

- Original guard: `137b0026e3fd24952a0aa5eccc8a89b448196e16`, `0.1.0-SNAPSHOT`.
- User-requested fetch/fast-forward: `0c5888db559e174ee8f70d99969730ba1e6bcef0`. [Source-equivalence and fresh install](evidence/update/source-equivalence.json) prove Java sources, adapters, build files, fixtures and tests unchanged. Original catalog baselines belong to the original pin; 21 expanded Maven mutation suites use the updated pin. The minimized defect was rerun twice in warning mode and once strict on **both** pins. This is not a claim that all 100 baselines were rerun after the merge.
- Guard installed locally on the host and into a dedicated container Maven cache; updated commit installation passed. Existing product tests: **12 core + 15 Maven integration + 25 Gradle tests = 52 distinct tests**, separate from external coverage. [Named XML test summaries](evidence/product-test-suites.json), [Maven suite](evidence/maven-suite-offline.log), [Gradle suite](evidence/gradle-suite-offline.log), [updated install](evidence/update/install.log). The latest install repeated the 12 core tests; adapter sources and tests are unchanged from the original full run.
- Container Maven **3.9.16**, Temurin JDK **21.0.12.1**; Gradle **8.14.3** running JDK 21, with isolated JDK 17/25 toolchains where requested. Exact image digests and limits are in `run_builds.py` and every `.command.json`. Host JDK 21.0.11 was used for initial product checks.
- Clones: `E:\\tmp\\bbg-campaign-137b0026\\clones`. The plan supplied in `E:\\tmp` is preserved as [test-plan.md](test-plan.md). Every selected module and exact Git SHA is in [results.csv](results.csv).
- Public builds ran inside containers with 3 GiB / 2 CPUs / 512 PID limits, dropped capabilities, no Docker socket, host credentials or user Maven/Gradle configuration mounted. Only disposable source, guard source, dedicated caches and public toolchains were mounted. Gradle commands use the controlled 8.14.3 runtime rather than each historical wrapper; incompatible builds are blocked, not guard defects.

## Outcomes by proposed tier and selected build tool

'''+table(['Tier','Tool','Candidates']+active,grouped)+f'''
The original catalog retains **25 candidates per tier**. “Build tool” is the tested consumer path; dual-build repositories are not counted twice. There are **{len(boot4)} Maven baselines with an identified Boot 4 BOM**, of which **{len(comparable)}** completed independent tree/pristine-BOM comparison. Two additional Gradle pilots (#{3:03}, #{40:03}) exercised a native-platform integration on the same original Boot version; their original DSL-only configurations remain expected unsupported.

Attempted: 100. Not attempted/skipped without a baseline attempt: 0. Baseline-broken: {counts['BASELINE_BROKEN']}. Environment/integration-blocked: {counts['ENV_BLOCKED']}. Expected unsupported: {counts['EXPECTED_UNSUPPORTED']}. Confirmed affected candidates: {counts['CONFIRMED_LIB_BUG']}; distinct confirmed defects: 1; unresolved suspected defects: 0. **Fully exercised against every requested scenario per repository: 0**. **{core_suites} Maven consumers completed the six-case core mutation/determinism/offline suite**; further scenarios are selective. Per-scenario execution is explicit in [coverage.csv](coverage.csv) and [coverage-matrix.md](coverage-matrix.md).

No catalog-wide false-positive/negative rate is reported: selected leaf modules, unsupported builds, controlled experiments and blocked artifacts do not share a defensible denominator. The five affected modules establish reproducibility, not a population estimate.

## Pilot and process validation

Four candidates per tier were attempted before scaling: '''+', '.join(link(r['id']) for r in pilot)+'''. The pilot found and corrected harness problems: Windows long paths, mismatched Gradle/JDK toolchains, cross-container Gradle cache-lock contention, duplicate Kotlin `pluginManagement` injection, and the assumption that a successful Maven dependency tree guarantees JAR availability. Initial failed attempts are retained where applicable; none is called a product defect.

Maven native truth uses pinned `maven-help-plugin:3.5.1:effective-pom`, `maven-dependency-plugin:3.10.0:tree`, an independently built pristine BOM model without consumer properties, and artifact-resolution controls. Gradle truth uses `ResolutionResult`, module/variant identity, selection reasons and constraint edges across the four default classpaths, plus a separate plain Java project for pristine platform selection. No defect is inferred merely from a declared version. Direct/managed/transitive Gradle origin checks also run in isolated added subprojects to avoid the original Spring DSL's selection rules.

Maven override versions were selected from captured public metadata. The four original suites used the next available stable version. The 21 expanded suites used a different same-major/minor version present in both captured metadata and the warmed artifact cache: the next higher cached version where available, otherwise the highest different cached version. Later Gradle/property experiments used the latest captured 2.0.x. Native trees/results were checked after every mutation. The expanded suites run entirely offline with networking disabled; their determinism checks compare repeated warmed results, not online versus offline transport. Original tracked source bytes were restored after each experiment. [Final checkout verification](checkout-verification.json) records tracked changes; `.bbg` and build caches remain disposable local outputs.

## Size and performance

`tier_measured` describes **only the selected consumer scope**, not the whole repository: Small <=150 selected graph nodes, Medium 151–500, Large 501–1500, Huge >1500. Selected Maven runs use `-N` (one module); two reactor experiments are separate. Gradle graph counts use native runtime libraries where a machine-readable graph was captured. Missing graph measurements remain `UNMEASURED`. Counts: '''+', '.join(f'{k}={v}' for k,v in measured.items())+'''. Static POM/build-script counts in each inventory include independent samples and BOM projects and are not presented as resolved reactor module counts. Wrapper, toolchain, build inventory and module declarations are preserved in `inventory.json` / `inspection.json` per repository.

The Huge catalog group therefore does **not** establish whole-monorepo or >1500-node coverage. The broadest selected original Maven graph has '''+str(max(r.get('native_graph_nodes',0) for r in rows))+''' nodes. Representative leaves are permitted by the supplied plan, but they limit scalability conclusions.

Performance pairs run serially, offline, with networking disabled, identical image/cache/limits and verified selected-graph hashes. A warm-up pair is excluded; three measured pairs alternate native-first/guard-first. Native runs execute `dependency:tree`; guard runs execute the same goal plus the check. Elapsed includes container/process startup. RSS samples `/proc/<Maven-JVM>/status` `VmHWM` every 50 ms; it is a process high-water estimate, not whole-host memory. CSV `elapsed_s` remains the original baseline wall time; CSV `peak_rss_mb` is the median guard-pair RSS where measured.

'''+table(['Repo','Selected unique','Native median s','With guard median s','Delta s','Native RSS MiB','With guard RSS MiB','Delta MiB'],[[link(r['id'],'benchmark.json'),b['selected_unique'],b['median']['native']['elapsed_s'],b['median']['guard']['elapsed_s'],b['elapsed_delta_s'],b['median']['native']['peak_rss_mb'],b['median']['guard']['peak_rss_mb'],b['rss_delta_mb']] for r,b in benches])+'''
These small/medium leaf graphs support only local overhead observations; there is no whole-Huge graph scaling or production-memory conclusion. Warning mode is used where existing drift or BBG-001 would otherwise stop the measurement.

## Limitations and reproducibility

See [blocked-candidates.md](blocked-candidates.md) for baseline failures and exact logs. Common blockers are historical Gradle build incompatibility, missing sibling SNAPSHOT artifacts, repository HTTP 429 responses, timeouts, unavailable parent/BOM artifacts and toolchain vendor requirements. Maven tree success with absent local JARs is reported as incomplete artifact resolution; native offline `dependency:resolve` independently confirmed all retained Maven artifact-blocked cases.

The Spring Boot 2/3 and DSL-only negative controls were not upgraded. Native-platform additions and synthetic subprojects are explicit experiments, not relabelled original-project successes. Application tests, databases, configuration cache, Gradle 9.8.2/10, mirror/proxy behavior, comprehensive exception-validation permutations and full enterprise graphs were not run in this external campaign. The synthetic credential probe exposed no sentinel in either native or guard output; it does not establish redaction of an exception containing credentials. Warm-cache offline checks do not prove cold-cache reliability. SNAPSHOT coordinates can change remotely: retained metadata, pinned source SHAs, logs and the dedicated local cache identify the exact captured resolution.

External campaign command/exit/time records are next to logs as `*.command.json`; use the scripts only against disposable workspaces. Rerunning mutations needs the preserved cache/toolchains or equivalent public downloads. The final deliverables contain no claim that an expected unsupported result passed integration. No library implementation was changed.
'''
    (HERE/'summary.md').write_text(summary,encoding='utf-8')
    blocked=[]
    for r in rows:
        if r['outcome'] not in ['ENV_BLOCKED','BASELINE_BROKEN']:continue
        e=HERE/'evidence'/f"{r['id']:03}";logs='\n'.join(p.read_text(errors='replace') for p in [e/'baseline.log',e/'original-warning.log'] if p.exists())
        reason='See retained native/guard diagnostics'
        for pattern,label in [('429','HTTP 429 repository rate limiting'),('CAMPAIGN_TIMEOUT','Resolution timeout'),('Could not find method','Historical Gradle DSL incompatibility'),('Non-resolvable parent','Unresolvable parent POM'),('org.gradle.jvm.toolchain','Toolchain requirements'),('Maven model/dependency resolution failed','Incomplete Maven artifact/model resolution')]:
            if pattern in logs:reason=label;break
        blocked.append([link(r['id'],'baseline.log'),r['repo'],r['outcome'],r.get('build_root',''),reason])
    (HERE/'blocked-candidates.md').write_text('# Blocked and broken candidates\n\nThese are not attributed to the guard. Exact commands and diagnostics are retained next to the linked baseline.\n\n'+table(['Evidence','Repository','Outcome','Selected build','Reason'],blocked),encoding='utf-8')
    coverage_doc(coverage)
    bugs_doc(rows)
    print('Reports rendered:',dict(counts),flush=True)

def coverage_doc(coverage):
    grouped=collections.defaultdict(list)
    for c in coverage:grouped[c['scenario']].append(c)
    data=[]
    for name,items in grouped.items():
        ids=sorted({x['id'] for x in items})
        references=', '.join(link(n) for n in ids) if len(ids)<=8 else f'{len(ids)} candidates; see [coverage.csv](coverage.csv)'
        data.append([name,', '.join(f'{k}: {v}' for k,v in collections.Counter(x['status'] for x in items).items()),references])
    text='# Actual scenario coverage\n\nOne entry is one repository/scenario, not one classpath or one log line. `VERIFIED` means native versions/conditions and applicable exits were checked. The expected unsupported baseline entries verify warning/strict behavior only.\n\n'+table(['Scenario','Observed execution','Repositories'],data)+'''
Separate experiments: `native-platform/` adds the same Boot BOM to the original DSL build; `controlled-subproject/` adds disposable JVM projects to a real root without changing its original dependencies. Constraint/force requests that the Spring DSL overrules are aligned native graphs, not successful injected-drift cases; the controlled subprojects independently exercise the changed-version cases. Four default classpaths are compared per Gradle experiment.

Not exercised externally: dynamic/strictly/reject constraint permutations; substitution; selection-rule permutations beyond existing Spring DSL; custom unresolvable configuration permutations; duplicate/blank exceptions; proxy/mirror transport; Gradle configuration cache/9.8.2/10; all modules in the largest reactors. Existing product tests do not count as external coverage. No Boot migration was attempted.
'''
    (HERE/'coverage-matrix.md').write_text(text,encoding='utf-8')

def bugs_doc(rows):
    affected=[r for r in rows if r.get('issue_id')=='BBG-001']
    p=HERE/'bugs/BBG-001/0c5888db';result=read(p/'result.json');assert result['confirmed'] and result['repeat_identical']
    report=(p/'warning.log').read_text();sample=next(x for x in report.splitlines() if x.startswith('DRIFT org.springframework.boot:spring-boot '))
    text='''# Confirmed defects

## P1 — BBG-001: aligned Maven SNAPSHOT artifacts are reported as dependency drift

**Impact:** valid Boot 4 SNAPSHOT consumers fail strict CI; the report also falsely assigns direct/transitive override classifications. One defect was confirmed. No production/library fix was made.

**Versions:** guard `0.1.0-SNAPSHOT` at both `137b0026e3fd24952a0aa5eccc8a89b448196e16` and latest `0c5888db559e174ee8f70d99969730ba1e6bcef0`; Maven 3.9.16, Temurin JDK 21.0.12.1, Boot BOM 4.2.0-SNAPSHOT. Captured Spring snapshot metadata maps the alias to `4.2.0-20261023.172449-288` (some real-project cached test artifacts use build 284). Boot 4.x SNAPSHOTs are not excluded by the checked supported-major contract.

**Minimal change:** a clean Maven consumer imports the Boot BOM and requests a versionless `spring-boot-starter`; there is no version override, property change, parent trick, reactor dependency, exception or custom plugin rule. [Exact minimal POM](bugs/BBG-001/0c5888db/pom.xml).

**Expected:** native selected dependencies align with the selected BOM, `PASS checked=21 drift=0 unknown=0`; warning and strict return 0. Resolving a `-SNAPSHOT` constraint to its timestamped repository artifact is normal Maven resolution and is not an override.

**Actual:** native tree/effective POM and actual artifact resolution all succeed, but the guard emits `WARN checked=21 drift=4 unknown=0`; warning returns 0, strict returns 1. The same four findings repeat offline with networking disabled on both guard pins.

```text
'''+sample+'''
WARN checked=21 drift=4 unknown=0
```

**Independent resolver evidence:** [native tree](bugs/BBG-001/0c5888db/tree.json), [effective POM](bugs/BBG-001/0c5888db/effective.xml), [native artifact-resolution success](bugs/BBG-001/0c5888db/native-artifacts.log), [repository alias/timestamp metadata](bugs/BBG-001/0c5888db/snapshot-metadata.log), [comparison and exits](bugs/BBG-001/0c5888db/result.json), [first-pin reproduction](bugs/BBG-001/137b0026/result.json). The pristine BOM comparison used the independently built [4.2.0-SNAPSHOT model](evidence/078/pristine.xml); consumer overrides are absent. Neither application compilation nor a Boot migration is involved.

**Reproduction on a machine with the captured public dependencies/cache:** install the guard at the pinned SHA, then use the supplied POM. The commands below are the Maven portions of the recorded resource-limited Docker calls; every exact image, mount, flag, exit and wall time is in the adjacent `.command.json` files.

```powershell
mvn -B -ntp install
$repro = 'reports/real-world-2026-10-25/bugs/BBG-001/0c5888db/pom.xml'
mvn -B -ntp -N -f $repro org.apache.maven.plugins:maven-help-plugin:3.5.1:effective-pom org.apache.maven.plugins:maven-dependency-plugin:3.10.0:tree
mvn -B -ntp -N -f $repro org.apache.maven.plugins:maven-dependency-plugin:3.10.0:resolve
mvn -B -ntp -N -f $repro io.github.bootbomguard:boot-bom-guard-maven-plugin:0.1.0-SNAPSHOT:check
mvn -B -ntp -N -f $repro io.github.bootbomguard:boot-bom-guard-maven-plugin:0.1.0-SNAPSHOT:check -DbootBomGuard.failOnDrift=true
```

For the exact retained Windows/Docker campaign setup: `python reports/real-world-2026-10-25/snapshot_repro.py 0c5888db-repeat`. It uses the dedicated warmed cache and `--network none`, so does not depend on remote metadata remaining unchanged. Keep that cache to reproduce this exact historical snapshot; the public snapshot repository is mutable. The harness stores the minimized POM, both warning runs, strict run, native resolver outputs and metadata separately.

**Likely root cause:** [CheckMojo.java](../../maven-plugin/src/main/java/io/github/bootbomguard/maven/CheckMojo.java) `collect()` line 162 reads `Artifact.getVersion()`, which is timestamped after artifact resolution. `management()` line 139 supplies the BOM's model version, `4.2.0-SNAPSHOT`. Core `Guard.compare()` compares those strings literally. The native tree represents the selected base constraint, whereas the artifact object exposes its resolved timestamp. Thus equivalent Maven identities compare unequal. The unconditional depth-based origin branches then give the false findings plausible but incorrect override labels.

**Recommended correction, not implemented:** compare expected and actual identities consistently through native snapshot resolution. Preserve the ability to detect an explicitly pinned older timestamp; blindly stripping every timestamp to `-SNAPSHOT` could create a false negative. If an identity cannot be established, report incomplete analysis instead of invented drift.

**Real-project corroboration:**

'''+table(['Repository','Target SHA','False findings','Genuine drift findings','Evidence'],[[r['repo'],r['sha'],r['false_positive_findings'],r['drift_count']-r['false_positive_findings'],link(r['id'],'oracle.json')] for r in affected])+'''
Total: **202 false findings**. Gateway also has three independently confirmed gRPC drifts (1.85.1 selected vs 1.84.1 expected); those three are not counted as false positives. The other four affected native graphs have no drift against their independently built BOM model.

## Rejected product-bug attributions

- Kotlin duplicate `pluginManagement`: test-harness wiring error, fixed and rerun successfully.
- Root aggregation projects without a Boot BOM: expected `UNKNOWN`; Spring Boot Admin strict `-pl/-am` stops at the root, while the Boot-managed leaf passes. [Reactor logs](evidence/077/reactor.json).
- Missing sibling SNAPSHOT JARs despite successful Maven dependency trees: native artifact resolution also fails; environment/prerequisite issue.
- Spring Boot 2/3 or Gradle Spring dependency-management DSL without a native platform: documented unsupported boundary; never counted as successful integration.
- Historical Gradle DSL/toolchain failures and repository HTTP 429: baseline/environment blockers.

No unresolved mismatch was promoted to a confirmed defect without a minimized control and native resolver evidence.
'''
    (HERE/'bugs.md').write_text(text,encoding='utf-8')

if __name__=='__main__':main()
