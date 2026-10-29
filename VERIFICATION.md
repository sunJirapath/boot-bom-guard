# Verification

## Performance and further stress coverage, 2026-10-29

Shared-core optimizations reuse coordinate validation patterns, index expected versions by hash, sort only drift findings, and avoid formatter allocations during report escaping. Public records, exact-version equality, distinct-resolution counting, ordering, exceptions and strict policy retain their previous behavior. [PERFORMANCE.md](PERFORMANCE.md) records reproducible baseline/working-source timing and allocation measurements; native resolution/startup and peak heap are outside that benchmark.

The suite now contains **95 distinct tests**: 16 shared core, 3 Maven adapter, 31 native Maven integration and 45 Gradle TestKit. Six additional regressions cover seeded differential policy checks, every UTF-16 code unit, coordinate grammar, colliding hashes, a dense native conflict graph, and separate configurations with different BOMs. Earlier corpus replays below belong to `78ec45c`; that corpus was not replayed for this core-only change.

Fresh Windows/JDK 21.0.11 checks pass: source install/unit suites and all 31 native integrations separately on Maven **3.9.16 / 3.10.0 / 4.0.0-rc-7**, plus forced full `check` and plugin validation on Gradle **8.14.3 / 9.8.2**. All current suites have zero failures/errors/skips. Local logs are under ignored `build/performance/`; the fresh-cache Maven 3.9.16 install also runs all 16 core and 3 adapter unit tests. Hosted results must be checked against the actual PR head, using the [PR checks](https://github.com/sunJirapath/boot-bom-guard/pull/8/checks).

## Earlier coverage-gap closure (78ec45c), 2026-10-29

This follow-up fixes five additional reproduced defects: Maven adapter stack overflow and shared-node origin, Gradle local-file false passes, fully erased BOM-constraint false passes, and exact preferred-only constraints incorrectly reported as unsupported. Incoming Gradle graph edges are indexed once. See [ADVERSARIAL-AUDIT.md](ADVERSARIAL-AUDIT.md) for before/fix/regression evidence and explicit remaining contracts.

Fresh Windows/JDK 21.0.11 verification: **89 distinct tests** (12 core, 3 Maven adapter, 31 native Maven integration, 43 Gradle TestKit). Full Maven install/unit/integration suites pass separately with **3.9.16, 3.10.0 and 4.0.0-rc-7**; Maven 4 is preview compatibility for that exact release candidate. Gradle **8.14.3 and 9.8.2** each pass full forced `check` reruns, including plugin validation. Tests have zero failures/errors/skips in final runs. New regressions account for 13 tests beyond the previous 76-test pass.

Bounded probes now cover native Gradle resolution of 2,048 managed modules (2,050 components, a 128-module chain, broad fan-out and a diamond), native Maven four-module parallel execution with `-T2 --fail-at-end`, loopback Basic Auth / Maven settings mirrors, library metadata and init-script rules, and safe configuration-cache discard with strict enforcement. The separate Maven depth test constructs 20,000 real Resolver nodes and invokes only the adapter traversal; it is not a native Resolver load claim. Synthetic repository fixtures publish checksums rather than disabling Maven 4 checksum validation.

Clean-cache installation with external Maven, Groovy and Kotlin consumers passes 15 checked commands using Maven 3.9.16 and both Gradle versions. Source/plugin/JUnit artifacts are consumed from fresh caches; the external Gradle consumers use composite builds, not TestKit injection. Evidence is retained under ignored `build/adversarial/` and `build/install-smoke-*`.

The five pinned Spring Cloud consumers, minimal Boot starter and stable Spring guide were replayed using the current plugin in a new copied Docker volume `bbg-gaps-m2-20261029`. Native graphs match historical trees, source SHAs/tracked files are unchanged, and native-tree/BOM oracles match warning/strict/repeat reports. All 202 historical false findings remain absent across the five Cloud projects' 792 comparable coordinates, while all three real Gateway drifts remain. The starter checks 21 coordinates and the guide 75. Raw scripts/results are in ignored `build/gaps-replay/`. The full 100-candidate campaign and every enterprise reactor were not rerun.

CI now has five jobs per event: Ubuntu Maven 3.9.16 with Gradle 8.14.3/9.8.2, macOS 15 with Maven 3.9.16/Gradle 8.14.3 (all including clean-cache consumers), plus separate Ubuntu Maven 3.10.0 and 4.0.0-rc-7 source-install/integration jobs. Actions and distributions are pinned, checksums verified, permissions read-only. Persisted [PR checks](https://github.com/sunJirapath/boot-bom-guard/pull/8/checks) determine hosted status for the actual head; workflow configuration alone is not success evidence.

Remaining boundaries are deliberate and documented: shared project/settings BOM metadata rules can partially rewrite the baseline; configuration-cache reuse/Gradle 10, non-JVM platform targets and arbitrary local binaries are unsupported; native Basic Auth/mirrors do not establish corporate TLS/SSO/proxy compatibility; no unlimited scale or runtime/security compatibility guarantee follows from version equality. The source-install snapshot remains unpublished.

## Earlier adversarial pass (067166c), 2026-10-29

The [adversarial audit](ADVERSARIAL-AUDIT.md) records four reproduced false-pass defects, their fixes and the remaining coverage boundaries. It adds native Maven relocation/type/classifier/system/range probes and Gradle composite, incomplete-baseline, rich-constraint, selection-rule, project-substitution and transitive-platform probes.

Fresh Windows/JDK 21.0.11/Maven 3.9.16 checks passed: Maven offline install (12 core tests), **29 Maven integration tests**, and full Gradle forced-task reruns using `check --rerun-tasks -PtestOffline=true` on **8.14.3 and 9.8.2** (12 shared core + **35 TestKit tests** and plugin validation on each). That is **76 distinct tests**, zero failures/skips, with the shared core counted once. Fifteen tests are new in this audit. The previous P1-P2 and campaign sections below remain revision-specific historical evidence.

Fresh empty-cache source-install/external-consumer verification passed **15 commands** across Maven and both Gradle versions, including Groovy and Kotlin DSL. Evidence is in ignored `build/adversarial/` and `build/install-smoke-fbjy_j6u/`. The final commit is submitted to the same hosted CI matrix; its persisted check status is authoritative. The earlier real-project replays were not repeated for this change.

## Historical P1-P2 readiness follow-up, 2026-10-29

This follow-up builds on PR #6 at `4ba376a1212f0305ec8fa6fd19f9a6272fe4ae47`. The changes below were freshly checked on Windows with JDK 21.0.11 and Maven 3.9.16. Earlier campaign/online results in the following sections remain historical unless explicitly rerun here.

- Maven now uses native **version metadata resolution**, including extension/classifier, for expected and effective managed snapshot identities. It does not fetch an additional expected snapshot JAR just to compare versions. Resolver's fallback alias with no metadata repository is incomplete analysis (`UNKNOWN`), rather than evidence of drift or alignment. Strict mode rejects that result.
- Three additional native file-repository regressions cover separate classifier timestamps, metadata absence in warning/strict modes, and non-unique snapshot aliases. Existing regressions retain explicit current/older timestamps, managed snapshot overrides and mixed genuine release drift. All **24 Maven integration tests** passed, alongside **12 core tests**.
- Full Gradle `check --rerun-tasks` passed separately on **8.14.3 and 9.8.2**: 12 repeated core tests, **25 TestKit tests**, and plugin validation on each. There are **61 distinct tests**, counting the shared core once; zero failures/skips.
- `scripts/verify_install.py` starts with empty Maven and Gradle caches and places consumers outside this checkout. A run with both Gradle executables passed **15 commands**: source install, four Maven policies, four Groovy policies per Gradle version, and a Kotlin strict allowed exception per version. An additional external Maven aligned check explicitly passed strict mode. No published guard artifact or TestKit plugin injection is used by this smoke test: Maven consumes the source-installed plugin and Gradle consumes a local composite build.
- Both supported Gradle versions now have Ubuntu/JDK 21 CI matrix jobs. Each runs the Maven/core/TestKit suites and repeats the clean-cache external-consumer smoke check. Hosted CI status belongs to the actual pull-request commit, not this local test record.

Reproduction (after Maven installation):

```sh
mvn -B -ntp --offline install
python scripts/verify_maven.py --offline
/path/to/gradle-8.14.3/bin/gradle --no-daemon --console=plain check --rerun-tasks
/path/to/gradle-9.8.2/bin/gradle --no-daemon --console=plain check --rerun-tasks
python scripts/verify_install.py --gradle /path/to/gradle-8.14.3/bin/gradle --gradle /path/to/gradle-9.8.2/bin/gradle
```

Local logs live in the follow-up worktree's ignored `build/p1-p2/`; the cold-cache run is `build/install-smoke-72e4cjge/`. The installer retains both evidence and caches and prints the external consumer directory. It requires network access for an empty cache. One initial smoke invocation used a nonexistent local Gradle path; after correcting that invocation, all checks passed. The script now validates supplied executable paths before starting installation.

The five pinned Spring Cloud consumers listed in the BBG-001 table below and the minimal Boot-starter reproduction were freshly replayed with the new metadata resolver. The Docker image, SHAs, read-only source mounts, resource bounds, offline network mode and native-tree oracle were preserved. A **separate copied cache** (`bbg-p1p2-m2-20261029`) received the freshly built plugin; original evidence/cache were unchanged. All 202 historical false findings remain absent across 792 comparable coordinates, all three genuine Gateway drifts remain, and repeated reports match. The minimal starter passes strict mode with 21 comparable coordinates. Raw replay scripts, logs, native trees and oracle results are retained in `build/p1-p2/`. The stable `spring-guides/gs-spring-boot` consumer at `cc0ca7c0c89513c75902de8a9afd1fc2718acf3b` (`complete/pom.xml`) also passed native-tree/oracle verification and warning/strict/repeat checks: 75 comparable coordinates, no drift/unknown, unchanged native graph and source checkout.

Readiness remains limited to the documented source-install MVP: Spring Boot 4, JDK 21, Maven 3.9.16 and Gradle 8.14.3/9.8.2 native platforms. These checks establish dependency-policy behavior, not application/runtime compatibility. Gradle configuration cache/10, Maven 4, macOS, third-party dependency-management-only builds and unrestricted reactor/graph scale remain unverified or unsupported as documented. Publishing to Maven Central/Plugin Portal is outside P1-P2.

## Campaign follow-up, 2026-10-29

The 100-candidate campaign results, scenario coverage and native oracle evidence are retained locally and excluded from Git. Fresh offline product checks on `51aa970678a1b892a81da82f65b891584bae57ae` passed 58 distinct tests (12 core, 21 Maven, 25 Gradle), zero failures/skips. Historical online results below were not rerun online in this follow-up. Unsupported/blocked candidates are not successful integrations.

## Historical verification — 2026-10-25

Executed on Windows 11 with Temurin JDK 21.0.11, Maven 3.9.16, Gradle 8.14.3 and Gradle 9.8.2. Unless noted, commands below ran from `E:/boot-bom-guard`; the isolated CI installer ran in its ignored `build` directory.

## BBG-001: Maven snapshot identity regression

The follow-up fix starts from `0c5888db559e174ee8f70d99969730ba1e6bcef0`. The pristine BOM contains logical versions such as `4.2.0-SNAPSHOT`, while Maven's selected artifact graph exposes versions such as `4.2.0-20261023.172449-288`. Comparing those strings produced false drift and strict CI failures. Resolver now supplies the expected and effective managed artifact identities; explicit older timestamps still differ. Core equality and the Gradle adapter are unchanged.

Six new integration tests use a generated, immutable file repository with two physical builds of `1.0-SNAPSHOT` and one build of `2.0-SNAPSHOT`. Native `maven-dependency-plugin:3.10.0:resolve` first verifies the actual artifacts. The assertions cover aligned direct/transitive aliases, an explicit current timestamp, explicit and managed older timestamps, another managed snapshot alias, and a mixed graph containing genuine release drift. Warning/strict exits and managed classification are asserted. All six failed against the original plugin; all pass with the fix. These are additional synthetic snapshot fixtures, not claims about public Boot snapshots. Their native file-repository bootstrap uses online Resolver mode even under the script's `--offline` flag; the subsequent guard checks honor that flag.

```powershell
mvn -B -ntp --offline install
python scripts/verify_maven.py --offline
# Focused portable reproduction, after installing the plugin:
python scripts/verify_maven.py --offline MavenSnapshotIntegrationTest
.\gradlew.bat --no-daemon --console=plain check --rerun-tasks
.\gradlew.bat --offline --console=plain check -PtestOffline=true --rerun-tasks
```

Local verification on Windows/JDK 21.0.11/Maven 3.9.16: Maven install passed 12 core tests; the Python suite passed 21 tests online and offline; Gradle 8.14.3 passed 12 core plus 25 TestKit tests and plugin validation, online and then offline. That is **58 distinct tests**, counting the shared core once. No failures or skips remain. The first offline Gradle attempt in the new worktree failed because its TestKit dependency cache was cold; the online run populated it before the passing offline rerun. Gradle 9 and Maven 4 were not rerun for this fix.

The five affected campaign repositories were rerun at the exact commits below in offline containers using Maven 3.9.16/Temurin 21.0.12.1 and a separate copy of the preserved campaign cache. The pinned container image is `maven@sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320`. Each run used `--network none`, two CPUs and 3 GiB memory. Source mounts were read-only. Native effective POM, dependency tree and artifact resolution succeeded; each new tree exactly matched its original JSON graph. The independent oracle compared the native tree with the pristine Boot BOM effective management. Warning, strict and repeated guard reports were then checked, with zero unknowns and identical repeated reports.

| Repository / pinned commit | Selected POM | Comparable coordinates | False findings before → after | Genuine findings retained | Warning / strict exit |
| --- | --- | ---: | ---: | ---: | --- |
| [spring-cloud-gateway](https://github.com/spring-cloud/spring-cloud-gateway/tree/a6e4b522dbd2cc48e1040f030556c00ea6dcda04) | `spring-cloud-gateway-server-webflux/pom.xml` | 223 | 54 → 0 | 3 | 0 / 1 |
| [spring-cloud-stream](https://github.com/spring-cloud/spring-cloud-stream/tree/930fd07da6417a30b8a1203b0bd18b1d9cae3242) | `binders/rabbit-binder/spring-cloud-stream-binder-rabbit/pom.xml` | 161 | 40 → 0 | 0 | 0 / 0 |
| [spring-cloud-kubernetes](https://github.com/spring-cloud/spring-cloud-kubernetes/tree/5d653390555abbef31abeb2c0e3d36d955dc2e6f) | `spring-cloud-kubernetes-examples/kubernetes-leader-election-example/pom.xml` | 103 | 25 → 0 | 0 | 0 / 0 |
| [spring-cloud-netflix](https://github.com/spring-cloud/spring-cloud-netflix/tree/fd54279c3357d280344ff5bde42c8a0474eeb430) | `spring-cloud-netflix-eureka-client/pom.xml` | 166 | 41 → 0 | 0 | 0 / 0 |
| [spring-cloud-commons](https://github.com/spring-cloud/spring-cloud-commons/tree/31ecfe5589fc20bdf263705904c2b202f66aaeba) | `spring-cloud-commons/pom.xml` | 139 | 42 → 0 | 0 | 0 / 0 |

All **202 false findings** disappeared across 792 comparable coordinate checks. Gateway's `grpc-netty`, `grpc-protobuf` and `grpc-stub` still report expected `1.84.1`, resolved `1.85.1`. The original minimal Boot-starter reproduction also changed from four false findings / strict exit 1 to `PASS checked=21 drift=0 unknown=0` / strict exit 0. All five clone SHAs and tracked-file states remained unchanged.

Raw rerun logs, commands, graph/oracle JSON and the local rerun script are retained under the fix worktree's ignored `build/bbg-001/`; the earlier campaign evidence remains separate and unchanged. These selected-leaf fix checks do not certify complete reactors. The subsequent 100-candidate follow-up revisited all 26 historical blockers: final outcomes are 30 aligned, 12 genuine drift, 57 expected unsupported and one external GeoServer artifact blocker, refreshed on 2026-10-29. It also records three complete default-reactor oracle checks and one matched reactor performance measurement; no single graph above 1,500 nodes was tested. Resolving expected snapshot identities can require additional artifacts/cache entries; a missing expected artifact produces incomplete analysis instead of an assumed match.

## Baseline and scope

The testing pass started from clean commit `19f4ccb`. Repository, documentation, production sources, all tests/fixtures and both build definitions were read before edits. The core contains no build-tool APIs; each adapter owns BOM selection, baseline resolution and native selection evidence. Entry points are `mvn boot-bom-guard:check` and `./gradlew bootBomGuard`.

The reproducible baseline passed: `mvn -B -ntp --offline install` ran 4 core tests; `python scripts/verify_maven.py --offline` ran 13 Maven integration tests; `./gradlew --offline check -PtestOffline=true --rerun-tasks` ran 4 core and 18 TestKit tests. All exited 0, with no failed or skipped tests. Maven has no wrapper; Gradle's wrapper pins 8.14.3.

There was no CI workflow, JaCoCo/equivalent coverage configuration, external coverage service, or license file. Line/branch coverage is therefore **N/A**, both before and after; no percentage or coverage/license badge is claimed.

## Test-gap decisions

Existing P0 native-resolution coverage was retained. The following gaps were addressed using the existing JUnit, TestKit, Python unittest and fixture infrastructure. No test dependency was added.

| Priority / scenario | Expected behavior | Level / fixture | Previous coverage → action | Relevant production source |
| --- | --- | --- | --- | --- |
| P0: aligned and direct/managed/transitive drift | Exact expected/resolved versions and native classifications | Unit + Maven/Gradle fixtures | Already covered; retained | `Guard`, `CheckMojo`, `BootBomGuardTask` |
| P0: warnings and opt-in CI failure | Warning exits successfully; unaccepted drift/incomplete analysis fails CI | Both integrations | Existing drift/BOM cases; added real unresolved dependency cases | Both adapters |
| P0: exception text may contain credentials | Sanitized `UNKNOWN`, still fails optional CI policy | TestKit `resolution-error` | Added a synthetic secret marker to a native resolution callback; assert it never appears | `BootBomGuardTask.check` |
| P1: malformed coordinates and missing values | Reject invalid tokens, blank versions/evidence/reasons, null required values | Core unit | Expanded validation assertions | `Coordinates`, `Guard.Resolved`, `Guard.compare` |
| P1: exact version identity | Qualifiers, snapshots and `1.0`/`1.0.0` differences remain drift | Core unit | Added | `Guard.compare` |
| P1: comparison boundaries | Ignore unmanaged/unused entries, preserve classifiers, deduplicate identical facts | Core unit | Extended | `Guard.compare` |
| P1: reasoned exceptions | Match exact coordinates; reject normalized aliases; never hide diagnostics | Core + Maven `duplicate-exception` | Extended | `Guard.exceptions`, both adapters' configuration |
| P1: deterministic and safe reports | Stable ordering, immutable comparison results, escape controls and Unicode separators | Core unit | Extended; exposed and fixed an origin-order tie | `Guard.compare`, `Guard.safe` |
| P1: custom Gradle configurations | Missing/non-resolvable warns and fails CI; empty list is invalid; duplicate names checked once | TestKit scenarios | Added | `BootBomGuardTask.check/inspect` |
| P1: per-project Gradle application | Plugin can be applied only to a JVM subproject and invoked from the root | TestKit temporary `:app` | Added | `BootBomGuardPlugin.apply` |
| P1: Boot parent/profile/import/native platform semantics | Pristine baseline; selected BOM and platform category preserved | Existing real fixtures | Retained | Both adapters |
| P2: exhaustive cosmetic permutations / extra compatibility versions | No new support claims | None | Deferred: lower value than policy/resolution paths | — |

The unresolved Maven case first warms its aligned baseline, then requests an absent fixture coordinate in offline mode. Gradle confines its absent coordinate to an empty local repository with an exclusive content filter. Neither negative case depends on a network outage. Temporary Gradle projects use JUnit `@TempDir`; no sleeps, graph mocks or machine-specific fixture paths were added.

### Confirmed defect and review

The new core ordering regression first failed (11 tests, 1 failure, exit 1): records differing only in `Origin` retained caller order because the comparator omitted that record field. The only production change adds `Origin` as the final sort key. Afterward, the expanded core suite passed all 12 tests. Public APIs, comparison policy and native resolution remain unchanged.

Three bounded smaller-model agents handled repository exploration, test-gap analysis/core tests, and CI review/implementation. The main agent owned adapter tests, fixtures, the production fix, integration and final verification. The repository explorer independently reviewed the combined change; its suggested subproject regression was added. No custom harness or agent framework was introduced.

## Final results

| Check | Result |
| --- | --- |
| Core unit tests | 12 passed under Maven and both Gradle versions |
| Maven real-resolution integration tests | 15 passed online and offline |
| Gradle TestKit integration tests | 25 passed on 8.14.3 and on 9.8.2; includes real dependency resolution |
| Gradle plugin validation | Passed on both tested Gradle versions |
| Cached/offline Maven and Gradle integration suites | Passed, no skipped tests; exact run scope recorded below |
| Hosted Ubuntu 24.04 CI | Passed for both push and PR events on `8564065`; Java 21, Maven 3.9.16 and Gradle 8.14.3 |

The matrix uses the real published Spring Boot 4.0.0 BOM, its imported BOMs and resolved library metadata/artifacts. BOM-selection cases also use Boot 4.0.1 and 4.1.0. These historical integration rows use native resolution. The later traversal-only adapter unit tests are identified separately above.

| Required case | Maven | Gradle |
| --- | --- | --- |
| Aligned Boot BOM | PASS | PASS |
| Explicit dependency override | Detected: 2.0.17 → 2.0.18 | Detected: 2.0.17 → 2.0.18 |
| Managed-version override | Effective dependencyManagement detected | Root constraint detected |
| Transitive drift | Transitive slf4j selected through logback; changed root management detected | Transitive slf4j request from slf4j-simple detected |
| Intentional exception with reason | PASS in CI mode | PASS in CI mode |
| Missing/ambiguous BOM | Missing and mixed effective BOM sources explained | Missing and conflicting strict BOM constraints explained |
| CI failure mode | Expected nonzero exit asserted | Expected task failure asserted |
| Warning mode | Warning with successful build | Warning with successful build |

Additional regressions cover Maven Boot parent property overrides, active profile BOM selection, verbose conflict losers, Gradle enforced platforms, multiple requested BOMs with one native winner, imported BOM versions, unmanaged modules, unknown force origin, substitutions, blank exception reasons, Kotlin DSL and lazy task registration.

There are 52 distinct tests, up from 35. Shared core tests run under both build systems; they are counted once here. JUnit XML and Python unittest summaries confirm zero failures/errors/skips in the final runs.

## Commands executed

```powershell
mvn -B -ntp --offline install
python scripts/verify_maven.py
python scripts/verify_maven.py --offline
.\gradlew.bat --offline --console=plain check -PtestOffline=true --rerun-tasks
.\gradlew.bat --no-daemon check --rerun-tasks
# Use the installed Gradle 9.8.2 executable for the second compatibility run:
gradle --offline check -PtestOffline=true --rerun-tasks
```

| Executed check | Exit | Passed / failed / skipped | Evidence |
| --- | --- | --- | --- |
| Maven `--offline install` | 0 | 12 / 0 / 0 | Production/test compilation, plugin descriptor and artifacts installed |
| Python Maven suite, online | 0 | 15 / 0 / 0 | `Ran 15 tests in 36.592s`, `OK` |
| Python Maven suite, offline | 0 | 15 / 0 / 0 | `Ran 15 tests in 38.135s`, `OK` |
| Gradle 8.14.3 `--no-daemon check --rerun-tasks` | 0 | 37 / 0 / 0 | 12 core + 25 TestKit; `BUILD SUCCESSFUL in 26s`; plugin validation included |
| Gradle 9.8.2 `--offline check -PtestOffline=true --rerun-tasks` | 0 | 37 / 0 / 0 | 12 core + 25 TestKit; `BUILD SUCCESSFUL in 29s`; plugin validation included |
| Focused Maven new tests | 0 | 2 / 0 / 0 | `python scripts/verify_maven.py --offline MavenIntegrationTest.test_unresolved_dependency_warns_and_fails_ci MavenIntegrationTest.test_duplicate_normalized_exception_is_rejected` |
| Focused Gradle new tests | 0 | 7 / 0 / 0 across focused runs | `:gradle-plugin:test --tests '*<test method>'`; configuration cases contribute two invocations |
| Final expanded core focused suite | 0 | 12 / 0 / 0 | `mvn -B -ntp --offline -pl core test` |
| Workflow YAML / command assertions | 0 | N/A | PyYAML BaseLoader; triggers, read-only permissions and exact suite commands checked |
| CI Maven installer syntax and isolated execution | 0 | N/A | Git Bash `-n`, then downloaded/extracted Maven 3.9.16 into ignored `build/ci-tools`; SHA-512 verified |
| Diff whitespace | 0 | N/A | `git diff --check` |

The Gradle 8 offline run before the final subproject addition passed 12 core + 24 TestKit tests. During test authoring, an incorrect Groovy repository closure caused one focused test to fail; its fixture syntax was corrected. A full run then exposed a Windows access denial while moving a fixture file. Copying directly to the subproject removed that unnecessary operation, after which the complete suites above passed. No product behavior was changed to hide either fixture problem.

Git Bash initially could not start inside the Windows sandbox (exit `-1073741502`); the installer syntax and isolated execution succeeded outside that sandbox. Maven's launcher also emitted `Access is denied.` before successful Maven execution in the sandbox. These are environment warnings, separate from test outcomes. Existing Maven API/Plexus deprecation warnings remain; no static-analysis framework is configured. Gradle's native plugin validation ran on both tested versions.

Earlier MVP standalone consumer checks are retained below for context; they were not rerun in this testing pass:

Standalone consumer commands were also executed:

```powershell
# Warning, exit 0, expected=2.0.17 resolved=2.0.18
mvn -B -ntp --offline -f fixtures/maven/aligned/pom.xml boot-bom-guard:check -Pdirect
.\gradlew.bat --console=plain -p fixtures/gradle/groovy -PguardBuild=E:/boot-bom-guard bootBomGuard -Pscenario=direct --offline

# Expected policy failure, exit 1
.\gradlew.bat --console=plain -p fixtures/gradle/groovy -PguardBuild=E:/boot-bom-guard bootBomGuard -Pscenario=direct -PfailOnDrift=true --offline

# Kotlin DSL intentional exception, exit 0, ALLOWED/PASS
.\gradlew.bat --console=plain -p fixtures/gradle/kotlin -PguardBuild=E:/boot-bom-guard bootBomGuard --offline --warning-mode=all
```

The Maven integration suite separately asserts Maven's nonzero CI exit. Both integrations report the same expected/resolved versions and common classification vocabulary while retaining native evidence.

## Inspect or reproduce

- [Maven integration assertions](scripts/verify_maven.py)
- [Gradle integration assertions](gradle-plugin/src/test/java/io/github/bootbomguard/gradle/BootBomGuardIntegrationTest.java)
- [Core assertions](core/src/test/java/io/github/bootbomguard/core/GuardTest.java)
- [Latest local Gradle test report](gradle-plugin/build/reports/tests/test/index.html)
- [Latest local Maven core test report](core/target/surefire-reports/io.github.bootbomguard.core.GuardTest.txt)

The last two links point to generated, ignored local artifacts and are recreated by the verification commands.

## Historical PR #3 limits and unverified cases

The following limits describe the PR #3 revision, not the current head. Reactor, cold-cache, additional Maven and CI coverage have since expanded as recorded above.

### CI and badges

The new [CI workflow](.github/workflows/ci.yml) has one Ubuntu 24.04 job, Java 21, explicitly provisioned Maven 3.9.16, the Gradle 8.14.3 wrapper, read-only repository permissions and a 30-minute timeout. It executes Maven install, all Python Maven integration tests, and Gradle check. Official action revisions are pinned; the Maven distribution checksum is verified. YAML, shell syntax and the installer were checked locally.

Hosted verification for [PR #3](https://github.com/sunJirapath/boot-bom-guard/pull/3) passed for both the [push run](https://github.com/sunJirapath/boot-bom-guard/actions/runs/40192541270) and [PR run](https://github.com/sunJirapath/boot-bom-guard/actions/runs/40192615991) on commit `8564065`. Maven ran 12 core tests and installed the plugin; the Python suite passed all 15 tests; Gradle ran the core and TestKit suites and plugin validation. These used fresh hosted Ubuntu runners without repository cache restoration. This verifies Linux execution, but does not establish that every preinstalled runner cache was empty.

All four existing compatibility badge images returned HTTP 200 with SVG content. After publication, the README CI badge (`actions/workflows/ci.yml/badge.svg?branch=main`) returned HTTP 200 with SVG text `CI - no status`, and the workflow page returned HTTP 200. The badge follows `main` and will show its result after merge and a run there. The PR is open; no merge, release or remote settings change was performed.

Coverage was not measured because no coverage tooling exists. No static percentage, external coverage service, license badge or additional compatibility claim was added. Maven reactor aggregation, macOS execution and a controlled empty-cache build remain unverified; the supported Gradle subproject application path is now tested. Local online/offline suites use previously warmed real build-tool caches; the unresolved Maven negative case warms its baseline explicitly before its offline failure check.

Configuration cache and Gradle 10 are unsupported. Gradle 8 emits the documented execution-time `Task.project` deprecation (removal in Gradle 10); both tested Gradle versions execute successfully. Maven emits native Maven 3 API/Plexus injection deprecation warnings. Maven 4, other Gradle versions, macOS and arbitrary third-party metadata-rewriting plugins were not tested. Spring's separate dependency-management DSL requires a native Boot platform for identification.

No plugin was published externally. No application runtime compatibility guarantee is inferred from a passing drift check. The guard does not inspect build-plugin dependency classpaths, vulnerabilities or unused BOM entries. Exceptions intentionally apply across versions at the named coordinate; users must review them after BOM upgrades.
