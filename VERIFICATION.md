# Verification — 2026-10-25

Executed on Windows 11 with Temurin JDK 21.0.11, Maven 3.9.16, Gradle 8.14.3 and Gradle 9.8.2. Unless noted, commands below ran from `E:/boot-bom-guard`; the isolated CI installer ran in its ignored `build` directory.

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

The matrix uses the real published Spring Boot 4.0.0 BOM, its imported BOMs and resolved library metadata/artifacts. BOM-selection cases also use Boot 4.0.1 and 4.1.0. No mocked dependency graphs satisfy any matrix row.

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

## Limits and unverified cases

### CI and badges

The new [CI workflow](.github/workflows/ci.yml) has one Ubuntu 24.04 job, Java 21, explicitly provisioned Maven 3.9.16, the Gradle 8.14.3 wrapper, read-only repository permissions and a 30-minute timeout. It executes Maven install, all Python Maven integration tests, and Gradle check. Official action revisions are pinned; the Maven distribution checksum is verified. YAML, shell syntax and the installer were checked locally; a hosted Ubuntu execution is **unverified**.

All four existing compatibility badge images returned HTTP 200 with SVG content. At the end of the initial local verification, the README CI badge (`actions/workflows/ci.yml/badge.svg?branch=main`) and workflow page returned HTTP 404; GitHub's workflow API reported zero workflows because the new file was still local. The follow-up request authorizes publishing a branch and opening a PR. PR checks verify the workflow before merge; the README badge follows `main` and requires a run there. No release or remote settings change is needed.

Coverage was not measured because no coverage tooling exists. No static percentage, external coverage service, license badge or additional compatibility claim was added. Maven reactor aggregation, Linux/macOS execution and a cold empty-cache hosted build remain unverified; the supported Gradle subproject application path is now tested. The negative resolver tests and ordinary online/offline suites use previously warmed real build-tool caches.

Configuration cache and Gradle 10 are unsupported. Gradle 8 emits the documented execution-time `Task.project` deprecation (removal in Gradle 10); both tested Gradle versions execute successfully. Maven emits native Maven 3 API/Plexus injection deprecation warnings. Maven 4, other Gradle versions, Linux/macOS and arbitrary third-party metadata-rewriting plugins were not tested. Spring's separate dependency-management DSL requires a native Boot platform for identification.

No plugin was published externally. No application runtime compatibility guarantee is inferred from a passing drift check. The guard does not inspect build-plugin dependency classpaths, vulnerabilities or unused BOM entries. Exceptions intentionally apply across versions at the named coordinate; users must review them after BOM upgrades.
