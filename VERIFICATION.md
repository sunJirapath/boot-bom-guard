# Verification — 2026-10-25

Executed on Windows 11 with Temurin JDK 21.0.11, Maven 3.9.16, Gradle 8.14.3 and Gradle 9.8.2. All commands below ran from `E:/boot-bom-guard`.

## Final results

| Check | Result |
| --- | --- |
| Core unit tests | 4 passed |
| Maven real-resolution integration tests | 13 passed |
| Gradle TestKit real-resolution integration tests | 18 passed on 8.14.3 and on 9.8.2 |
| Gradle plugin validation | Passed on both tested Gradle versions |
| Final cached/offline Maven and Gradle 8.14.3 integration suites | Passed, no skipped tests |

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

## Commands executed

```powershell
mvn -B -ntp install
python scripts/verify_maven.py
python scripts/verify_maven.py --offline
.\gradlew.bat --console=plain check
.\gradlew.bat --offline --console=plain check -PtestOffline=true --rerun-tasks
& 'C:\Users\Sun\.gradle\wrapper\dists\gradle-9.8.2-bin\8wepis63pzuhrlfaiy04bagwu\gradle-9.8.2\bin\gradle.bat' --console=plain check --rerun-tasks
```

The final Maven suite completed all 13 tests in 21.042 seconds. The final Gradle 8.14.3 offline run completed successfully in 14 seconds; Gradle 9.8.2's full run completed successfully in 42 seconds. Earlier runs warmed each build tool's own dependency cache. A newly added verbose-graph fixture first demonstrated the expected offline-cache miss, was resolved normally, then passed the final complete offline suite.

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

Configuration cache and Gradle 10 are unsupported. Gradle 8 emits the documented execution-time `Task.project` deprecation (removal in Gradle 10); both tested Gradle versions execute successfully. Maven emits native Maven 3 API/Plexus injection deprecation warnings. Maven 4, other Gradle versions, Linux/macOS and arbitrary third-party metadata-rewriting plugins were not tested. Spring's separate dependency-management DSL requires a native Boot platform for identification.

No plugin was published externally. No application runtime compatibility guarantee is inferred from a passing drift check. The guard does not inspect build-plugin dependency classpaths, vulnerabilities or unused BOM entries. Exceptions intentionally apply across versions at the named coordinate; users must review them after BOM upgrades.
