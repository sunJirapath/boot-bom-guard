# Adversarial dependency-resolution audit — 2026-10-29

Nine reproduced defects have been fixed across this audit and its follow-up: four original false passes, two further false passes, a stack overflow, an incorrect origin, and a false incomplete-analysis result. No runtime dependency or public API was added.

This audit targets unusual build semantics beyond a repository corpus. It does not claim that arbitrary build plugins or application libraries are compatible. The previous campaign's **202** figure counts false findings, not 202 independently verified repositories; historical campaign results remain separate in [VERIFICATION.md](VERIFICATION.md).

## Confirmed defects, in priority order

ADV-001 through ADV-004 are **P1** for a guard used as a strict dependency-policy gate. The conditions are specific; these are not claims that ordinary aligned builds fail.

| ID | Trigger and root cause | Before fix | Fix and regression |
| --- | --- | --- | --- |
| ADV-001 | Maven relocates a BOM-managed old coordinate to a different artifact. The adapter compared only the relocated coordinate, which could be unmanaged, silently dropping the old coordinate. | Native Maven warns `legacy:jar:2.0` relocated to `relocated:jar:2.0`; guard reports `PASS checked=3 drift=0 unknown=0`, although the BOM manages `legacy` at `1.0`. | Inspect Resolver's relocation chain. Report `UNKNOWN Unsupported Maven dependency relocation`; strict mode fails. `test_relocation_cannot_silently_drop_a_managed_coordinate`. |
| ADV-002 | An included Gradle build publishes the Boot BOM's group/name. Source configurations disable global composite substitution, but the detached baseline inherited Gradle's default substitution behavior. | The source graph uses the external Boot 4.0.0 BOM and SLF4J 2.0.18; the baseline substitutes an empty local platform. All four classpaths report `PASS checked=0`. | Disable global composite substitutions on the baseline. Report the actual `expected=2.0.17 resolved=2.0.18` drift; strict mode fails. `compositeBuildCannotReplaceThePristineBaselinePlatform`. |
| ADV-003 | A build callback changes repository availability after source resolution; the selected Boot platform cannot resolve in the baseline. Unresolved non-constraint root edges were ignored. | Native source graph contains Boot 4.0.0 and SLF4J 2.0.18, but guard reports `PASS checked=0`. | Require the exact selected external Boot platform to resolve in the baseline. Otherwise report `UNKNOWN Could not resolve selected Spring Boot BOM in isolated baseline`; strict mode fails. `missingBaselinePlatformCannotPassAnOtherwiseResolvedGraph`. |
| ADV-004 | Gradle Module Metadata expresses a platform dependency on another BOM. That nested BOM becomes unavailable to the baseline, while the root Boot platform still resolves. Only unresolved constraint edges were checked. | Native source graph includes the nested BOM and SLF4J 2.0.18; incomplete baseline reports `PASS checked=0`. | Diagnose unresolved non-root platform dependencies as `UNKNOWN Could not resolve an imported Boot BOM in isolated baseline`; strict mode fails. Preserve legitimate unresolved root requests for unmanaged modules. `missingImportedBaselineCannotPassAnOtherwiseResolvedGraph`. |

ADV-001/002/003 regressions failed before their production fixes. ADV-004 was reproduced after those three fixes and failed independently, proving that checking only the root platform was insufficient. Before-fix Maven output and Gradle JUnit XML are retained locally under ignored `build/adversarial/`.

ADV-003/004 use deterministic `afterResolve` callbacks to switch repository views, not a timed network outage. ADV-004 uses a generated frozen Boot-shaped `4.0.0-audit` platform with native Gradle Module Metadata; it is not a claim about the metadata currently published for an official Spring Boot release. The same baseline logic handles that native platform representation.

Maven relocation remains explicitly unsupported for a trustworthy comparison. The fix prevents a false pass; it does not guess a version mapping between renamed artifacts. Even an aligned relocation is incomplete analysis, and an exception cannot suppress that diagnostic.

## Follow-up fixes and closed coverage gaps

The follow-up adds **13 distinct tests** using the existing JUnit/TestKit/Python infrastructure. JUnit is now also a test-scoped dependency of the Maven adapter; runtime dependencies are unchanged.

| ID / priority | Root cause and before-fix evidence | Smallest fix / regression |
| --- | --- | --- |
| ADV-005 / P1 | Maven's recursive graph walk throws `StackOverflowError` on a 20,000-node chain of real Resolver `DefaultDependencyNode` objects. | Iterative breadth-first traversal. `CheckMojoTest.deepNativeGraphDoesNotOverflowTheJavaStack`; this tests the adapter, not native publication/resolution of 20,000 artifacts. |
| ADV-006 / P2 | Depth-first visited-node handling labels a shared direct dependency as transitive when first reached through a bridge. | The same breadth-first traversal retains the shortest root path. `sharedDirectNodeKeepsItsShortestRootPath`; cycle/conflict-loser control also passes. |
| ADV-007 / P1 | Gradle ignores a local unversioned JAR and reports `PASS checked=1` for the remaining aligned module. | Detect file dependencies declared/inherited by the selected configuration; report `UNKNOWN`, fail strict mode. `localFilesCannotBeClaimedAsFullyChecked`. No guessed module identity or local file-content scan. |
| ADV-008 / P1 | A component metadata rule removes all Boot BOM constraints. Native platform resolution succeeds but the guard reports `PASS checked=0`. | Require baseline managed constraints; report `UNKNOWN`, fail strict mode. `emptiedBomMetadataCannotProduceAnAlignedPass`. Partial BOM rewrites remain outside the baseline contract below. |
| ADV-009 / P2 | An exact published `prefers`-only constraint selects a valid expected version, but empty `required`/`strict` fields trigger a spurious `UNKNOWN`. | Fall back to native `preferredVersion` when both stronger fields are empty. Exact `1` versus actual `2` is drift with `unknown=0`; non-exact constraints remain unsupported. `exactPreferredOnlyPublishedConstraintIsComparable`. |

Gradle now indexes incoming edges and library components once, replacing per-component full-edge scans. The collection/indexing stage is linear in graph size; native resolution and sorting still have their own costs. The separate [performance follow-up](PERFORMANCE.md) measures shared-core changes only; it does not benchmark this indexing change or native resolution.

| Previously documented gap | Fresh bounded evidence |
| --- | --- |
| Large/deep/shared graphs | Native Gradle resolution of **2,048 managed modules / 2,050 components**, a 128-module chain plus broad fan-out and a shared diamond leaf; exactly one override remains drift and strict mode fails. Maven adapter separately handles 20,000 nodes, cycles and shortest paths. These are tested sizes, not universal ceilings. |
| Parallel reactors | Native Maven `-T2 --fail-at-end` root + three child modules: aligned, genuine drift and an allowed override. Native trees, all four warning reports, per-module strict policy and the allowed child are asserted. This is per-module execution, not a new aggregate-report feature. |
| Init scripts / library metadata | An init-script version rule remains drift without changing the baseline. A library metadata rule injecting a higher transitive request also remains real drift. No claim of support for every third-party plugin. |
| Authenticated repositories / Maven mirrors | Loopback HTTP Basic Auth with dummy credentials: native Maven settings mirror and Gradle repository resolve real frozen metadata; warning/strict policies hold. Gradle denied access after cache refresh is `UNKNOWN` and strict failure. These tests do not exercise corporate proxy/TLS/SSO stacks. |
| Configuration cache | Both tested Gradle versions safely discard the incompatible configuration-cache entry, execute the check and enforce strict mode. Cache reuse is unsupported. |
| Additional Maven versions | Complete source install/unit/integration suites run with **3.9.16, 3.10.0 and 4.0.0-rc-7**. The Maven 4 result is preview compatibility for this exact release candidate, not a stable Maven 4 guarantee. Frozen repositories provide checksums; checksum validation was not disabled. |
| macOS | Hosted CI now includes the complete Maven/Gradle 8.14.3 suites and empty-cache external consumers on `macos-15`; use persisted PR checks for its result. Ubuntu retains both Gradle versions and adds the two Maven compatibility jobs. |

The auth test deliberately permits HTTP only on loopback. Maven snapshot/file repositories bootstrap through native online Resolver mode even with `--offline`; guard invocations then honor offline mode. Gradle's loopback transport test deliberately runs online even with `-PtestOffline=true`. Tool dependencies must already be cached for other offline checks.

## Performance follow-up coverage

Six further regressions bring the suite to **95 distinct tests**. Four core tests compare 100 seeded shuffled mixed graphs against the previous policy, preserve all 65,536 UTF-16 code units and supplementary/unpaired surrogates during sanitization, retain the exact coordinate token grammar, and keep 256 colliding coordinate hashes distinct. Two native TestKit tests resolve a dense 128-module graph with competing transitive versions and verify separate configurations selecting different Boot BOMs, including duplicate configuration-name suppression and strict failure when only one configuration drifts. See [PERFORMANCE.md](PERFORMANCE.md) for reproducible baseline/working-tree measurements and their limits.

## Additional coverage

The first pass added **15 distinct tests**: five Maven tests and ten Gradle tests. The follow-up above adds another 13. The four defect regressions are included in that count.

| Case | Verified behavior |
| --- | --- |
| Maven `java-source` / implicit `sources` classifier | Aligned version passes; override reports the exact logical type/classifier and fails strict mode. |
| Maven `ejb-client` / implicit `client` classifier | Same behavior; native type registry semantics are preserved. |
| Maven POM dependency and custom `zip` extension | Both participate in comparison; no assumption that every artifact is a JAR. |
| Maven `system` scope with an absolute native artifact path | Declared selected version is compared; a genuine override remains drift. |
| Maven dependency range `[1.0,2.0]` against exact BOM `1.0` | Frozen native metadata selects `2.0`; guard detects drift and fails strict mode. |
| Gradle `strictly('2.0.18')` | Native selection remains `2.0.18`; drift is retained. |
| Gradle bounded range with a compatible exact BOM recommendation | Native Gradle selects `2.0.17`; strict guard passes. A range is not independently treated as a request for the highest published version. |
| Gradle range rejecting the only recommended exact version | Native graph is unresolved; warning mode reports `UNKNOWN` and strict mode fails. |
| Conflicting Gradle strict requirements | Incomplete source graph never passes. |
| Gradle `eachDependency` version-selection rule | Actual override remains drift with `UNKNOWN_ORIGIN`; the source rule does not alter the baseline. |
| Gradle module-to-project substitution | Explicitly unsupported, reported as `UNKNOWN`; strict mode fails. |
| Boot platform brought in through another project's `java-platform` | Native transitive platform is recognized; aligned strict build passes. |
| Unmanaged external Gradle module (existing control) | An unresolved versionless root baseline request is still ignored legitimately; no false `UNKNOWN`. |

The Maven file repository is first verified by native `maven-dependency-plugin:resolve`. Type artifacts, relocation, system scope and version metadata are real files, not mocked graphs. Gradle fixtures use TestKit and native resolution; bounded-range metadata is frozen in a local file repository. Native selected/unresolved graph markers are asserted for the rich-constraint and incomplete-baseline probes.

An initial range probe depended on mutable/cached repository metadata. It was replaced with frozen metadata, and its expectations were checked against Gradle's actual selection rather than assuming Maven range semantics. That fixture failure was not counted as a product defect.

## Verification

Fresh local verification on Windows and JDK 21.0.11:

| Check | Result |
| --- | --- |
| Maven 3.9.16 / 3.10.0 / 4.0.0-rc-7 install | 16 core + 3 adapter tests on each |
| Native Maven integration suite | 31 tests on each Maven version |
| Gradle 8.14.3 and 9.8.2 full forced reruns | 16 shared core + 45 TestKit tests and plugin validation on each |
| Distinct tests, shared core counted once | **95**, zero failures/skips in final runs |
| Clean-cache source install / external Maven, Groovy, Kotlin consumers | 15 checked commands across Maven 3.9.16 and both Gradle versions |
| Earlier pinned real-project replays (`78ec45c`) | Five Spring Cloud consumers, minimal Boot starter and stable Spring guide: native graph/oracle equality, warning/strict/repeat checks; not replayed for the core performance follow-up |

The five Spring Cloud replays retain **792 comparable coordinates**, remove all **202 historical false findings**, and preserve all three genuine Gateway drifts. The minimal starter checks another 21 coordinates; the stable guide checks 75. This is seven selected consumers, not a rerun of all 100 historical candidates or every reactor module. A separate copied Docker cache receives the current plugin; historical evidence, original caches and source checkouts are unchanged. Scripts, native trees, oracle results and logs are retained under ignored `build/gaps-replay/`.

```sh
mvn -B -ntp --offline install
python scripts/verify_maven.py --offline
/path/to/gradle-8.14.3/bin/gradle --no-daemon --offline check --rerun-tasks -PtestOffline=true
/path/to/gradle-9.8.2/bin/gradle --no-daemon --offline check --rerun-tasks -PtestOffline=true
python scripts/verify_install.py --gradle /path/to/gradle-8.14.3/bin/gradle --gradle /path/to/gradle-9.8.2/bin/gradle
```

Repeat the Maven commands with each pinned Maven on `PATH`. Empty-cache installation requires network access. Local evidence lives under ignored `build/adversarial/` and `build/install-smoke-*`; hosted results belong to the exact head shown in the [PR checks](https://github.com/sunJirapath/boot-bom-guard/pull/8/checks). No hosted success is inferred merely from configuring a workflow.

Before-fix regressions were retained before production edits. Two fixture problems were corrected without relaxing production policy: a single-line generated POM exceeded Gradle's native parser mark limit, and Maven 4 rejected synthetic repository files without checksums. The POM is now formatted and fixtures publish checksums. A concurrent local Maven source-build collision was rerun serially; CI jobs already have separate checkouts.

## Remaining contract boundaries

| Boundary | Current contract / practical consequence |
| --- | --- |
| Project/settings-wide rewrites of the Boot BOM or imported BOM metadata | A detached configuration shares the project's metadata rules. Total constraint erasure is detected; partial rewrites can change the baseline. Trust native published BOM metadata and do not rewrite it when using this policy gate. Library metadata rules and init-script selection rules have bounded coverage above. Isolating arbitrary BOM rewrites would require a separate resolution environment, not another detached configuration. |
| Graph/reactor scale | Tested sizes above are regression cases, not unlimited memory/depth guarantees. Maven's own resolver has separate limits; the 20,000-node test covers only the adapter's walk. Reactor results are per module. |
| Corporate repository infrastructure | Native mirrors/Basic Auth and failure policy are tested; proxies, custom transports, TLS/SSO and concurrently changing remote metadata are not exhaustively covered. |
| Gradle configuration-cache reuse / Gradle 10 | Safe fallback is tested on 8.14.3/9.8.2. Execution-time native Project access remains incompatible with reuse and is deprecated for removal in Gradle 10. No Gradle 10 support claim. |
| Android / Kotlin Multiplatform / native targets | Selected external JVM-module comparison only. File dependencies declared/inherited on the selected configuration produce incomplete analysis; arbitrary local binaries cannot be mapped to BOM coordinates. Apply checks per JVM project; this does not audit every transitive project's local files or platform-specific artifact. |
| Application/runtime compatibility / malicious build logic | Outside version-policy checking. Matching versions does not prove bytecode compatibility, security or application behavior. Running a build executes its own plugins; this guard is not a sandbox. |
| Publication | Source-install snapshot only; no Maven Central or Plugin Portal release has been made. |

These explicit limits are not unverified defects claimed to be fixed. The confirmed stack overflow, origin error and policy-report defects are fixed with regressions.

## Native API references

- [Gradle composite builds: disabling global substitution](https://docs.gradle.org/current/userguide/composite_builds.html)
- [Gradle ResolutionStrategy API](https://docs.gradle.org/current/dsl/org.gradle.api.artifacts.ResolutionStrategy.html)
- [Maven Resolver DependencyNode relocation API](https://maven.apache.org/resolver-archives/resolver-1.9.25/maven-resolver-api/apidocs/org/eclipse/aether/graph/DependencyNode.html)
