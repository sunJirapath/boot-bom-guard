# Adversarial dependency-resolution audit — 2026-10-29

Four reproduced defects could report `PASS` after losing part of the comparison. Each now either detects the real drift or reports incomplete analysis (`UNKNOWN`); strict mode fails. No new runtime dependency or public API was added.

This audit targets unusual build semantics beyond a repository corpus. It does not claim that arbitrary build plugins or application libraries are compatible. The previous campaign's **202** figure counts false findings, not 202 independently verified repositories; historical campaign results remain separate in [VERIFICATION.md](VERIFICATION.md).

## Confirmed defects, in priority order

All four are **P1** for a guard used as a strict dependency-policy gate. The conditions are specific; these are not claims that ordinary aligned builds fail.

| ID | Trigger and root cause | Before fix | Fix and regression |
| --- | --- | --- | --- |
| ADV-001 | Maven relocates a BOM-managed old coordinate to a different artifact. The adapter compared only the relocated coordinate, which could be unmanaged, silently dropping the old coordinate. | Native Maven warns `legacy:jar:2.0` relocated to `relocated:jar:2.0`; guard reports `PASS checked=3 drift=0 unknown=0`, although the BOM manages `legacy` at `1.0`. | Inspect Resolver's relocation chain. Report `UNKNOWN Unsupported Maven dependency relocation`; strict mode fails. `test_relocation_cannot_silently_drop_a_managed_coordinate`. |
| ADV-002 | An included Gradle build publishes the Boot BOM's group/name. Source configurations disable global composite substitution, but the detached baseline inherited Gradle's default substitution behavior. | The source graph uses the external Boot 4.0.0 BOM and SLF4J 2.0.18; the baseline substitutes an empty local platform. All four classpaths report `PASS checked=0`. | Disable global composite substitutions on the baseline. Report the actual `expected=2.0.17 resolved=2.0.18` drift; strict mode fails. `compositeBuildCannotReplaceThePristineBaselinePlatform`. |
| ADV-003 | A build callback changes repository availability after source resolution; the selected Boot platform cannot resolve in the baseline. Unresolved non-constraint root edges were ignored. | Native source graph contains Boot 4.0.0 and SLF4J 2.0.18, but guard reports `PASS checked=0`. | Require the exact selected external Boot platform to resolve in the baseline. Otherwise report `UNKNOWN Could not resolve selected Spring Boot BOM in isolated baseline`; strict mode fails. `missingBaselinePlatformCannotPassAnOtherwiseResolvedGraph`. |
| ADV-004 | Gradle Module Metadata expresses a platform dependency on another BOM. That nested BOM becomes unavailable to the baseline, while the root Boot platform still resolves. Only unresolved constraint edges were checked. | Native source graph includes the nested BOM and SLF4J 2.0.18; incomplete baseline reports `PASS checked=0`. | Diagnose unresolved non-root platform dependencies as `UNKNOWN Could not resolve an imported Boot BOM in isolated baseline`; strict mode fails. Preserve legitimate unresolved root requests for unmanaged modules. `missingImportedBaselineCannotPassAnOtherwiseResolvedGraph`. |

ADV-001/002/003 regressions failed before their production fixes. ADV-004 was reproduced after those three fixes and failed independently, proving that checking only the root platform was insufficient. Before-fix Maven output and Gradle JUnit XML are retained locally under ignored `build/adversarial/`.

ADV-003/004 use deterministic `afterResolve` callbacks to switch repository views, not a timed network outage. ADV-004 uses a generated frozen Boot-shaped `4.0.0-audit` platform with native Gradle Module Metadata; it is not a claim about the metadata currently published for an official Spring Boot release. The same baseline logic handles that native platform representation.

Maven relocation remains explicitly unsupported for a trustworthy comparison. The fix prevents a false pass; it does not guess a version mapping between renamed artifacts. Even an aligned relocation is incomplete analysis, and an exception cannot suppress that diagnostic.

## Additional coverage

The audit adds **15 distinct tests**: five Maven tests and ten Gradle tests. The four defect regressions are included in that count.

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

Fresh local verification on Windows, JDK 21.0.11 and Maven 3.9.16:

| Check | Result |
| --- | --- |
| Maven offline install / shared core | 12 tests passed |
| Native Maven integration suite | 29 tests passed |
| Gradle 8.14.3 full forced task rerun | 12 shared core + 35 TestKit tests passed; plugin validation passed |
| Gradle 9.8.2 full forced task rerun | 12 shared core + 35 TestKit tests passed; plugin validation passed |
| Empty-cache source install and external consumers | 15 commands passed, covering Maven and both Gradle versions, Groovy and Kotlin DSL |
| Distinct tests, shared core counted once | **76 passed, zero failures/skips** |

The final commit also runs the hosted CI matrix. Its persisted check status is authoritative for Ubuntu; local results above do not imply a hosted result before those checks complete.

```sh
mvn -B -ntp --offline install
python scripts/verify_maven.py --offline
/path/to/gradle-8.14.3/bin/gradle --no-daemon --offline check --rerun-tasks -PtestOffline=true
/path/to/gradle-9.8.2/bin/gradle --no-daemon --offline check --rerun-tasks -PtestOffline=true
python scripts/verify_install.py --gradle /path/to/gradle-8.14.3/bin/gradle --gradle /path/to/gradle-9.8.2/bin/gradle
```

Maven snapshot/file fixtures bootstrap through native online Resolver mode even with the script's `--offline` option; guard invocations then honor offline mode. Previously cached tool dependencies are required. The installation smoke check intentionally starts with empty caches and requires network access. Logs and before-fix evidence are retained under ignored `build/adversarial/`; this installer run is retained in `build/install-smoke-fbjy_j6u/`, with external consumers in the separately printed OS temporary directory.

The historical external-repository campaign and six P1–P2 project replays were **not rerun for this adversarial change**. Their pinned results apply to the revisions stated in VERIFICATION.md, not an implied fresh corpus run here.

## Remaining boundaries

| Priority | Boundary | Status / practical consequence |
| --- | --- | --- |
| P2 | Arbitrary component-metadata rewriting, init scripts and third-party dependency-management plugins | Not exhaustively tested or supported. They can change native metadata/selection beyond these bounded scenarios; no claim that every such build is understood. |
| P2 | Very large/deep graphs and full enterprise reactors | No load/depth ceiling established. The retained corpus checks selected modules, not every reactor module or an unrestricted scale guarantee. |
| P2 | Repository proxies, authentication/mirror combinations and concurrent metadata changes | These tests simulate missing repository views deterministically, not every transport/deployment setup. Native resolution failures remain incomplete analysis. |
| P2 | Maven 4, Gradle 10 and Gradle configuration cache | Outside the documented supported contract. |
| P2 | Android/Kotlin Multiplatform/native targets and local file libraries | No new support claim. Gradle comparison is for selected external JVM modules; local files have no comparable module identity. |
| P2 | Application runtime behavior, bytecode/API compatibility and malicious build plugins | Outside a dependency-version policy check. Matching the BOM does not establish runtime compatibility or sandbox build logic. |

No additional crash was confirmed in the executed probes. The confirmed failures were misleading successful policy reports. Untested boundaries above are risks to validate when needed, not verified defects.

## Native API references

- [Gradle composite builds: disabling global substitution](https://docs.gradle.org/current/userguide/composite_builds.html)
- [Gradle ResolutionStrategy API](https://docs.gradle.org/current/dsl/org.gradle.api.artifacts.ResolutionStrategy.html)
- [Maven Resolver DependencyNode relocation API](https://maven.apache.org/resolver-archives/resolver-1.9.25/maven-resolver-api/apidocs/org/eclipse/aether/graph/DependencyNode.html)
