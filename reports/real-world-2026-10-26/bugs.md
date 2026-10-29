# Confirmed defects

## P1 — BBG-001: Maven SNAPSHOT identity false positives — fixed

**Root cause:** Maven's resolved artifact can expose a timestamp such as `4.2.0-20261023.172449-288`, while the pristine Boot BOM contains `4.2.0-SNAPSHOT`. Literal string comparison treated one native selected identity as two versions and assigned misleading override classifications.

**Affected versions:** guard `0.1.0-SNAPSHOT` at `137b0026e3fd24952a0aa5eccc8a89b448196e16` and source-equivalent `0c5888db559e174ee8f70d99969730ba1e6bcef0`; Maven 3.9.16, Temurin 21.0.12.1; Boot 4.2.0-SNAPSHOT. **Fixed implementation:** `f961d07815c68afea08d63aada9baf754b771b65`.

**Expected:** the aligned starter graph reports `PASS checked=21 drift=0 unknown=0`; warning and strict both exit 0.

**Before:** the minimal versionless Boot starter produced `WARN checked=21 drift=4 unknown=0`; warning exited 0, strict exited 1. Real repositories produced 202 false findings. [Full before commands/native models/tree/exits](evidence/bug-before.json), [before logs](evidence/bug-before.log), [minimal POM](repro/pom.xml).

```text
DRIFT org.springframework.boot:spring-boot expected=4.2.0-SNAPSHOT resolved=4.2.0-20261023.172449-288 classification=TRANSITIVE_DRIFT
WARN checked=21 drift=4 unknown=0
```

**Fix:** resolve expected and effective managed snapshot versions through the existing Maven Resolver session before comparison and classification. Retain explicit timestamp identity so an older timestamp still drifts. A resolution failure produces sanitized UNKNOWN. Core comparison and the Gradle adapter are unchanged. [CheckMojo](../../maven-plugin/src/main/java/io/github/bootbomguard/maven/CheckMojo.java).

**Verification:** the six frozen file-repository regressions fail before and pass after the fix. They cover aligned direct/transitive aliases, current/older timestamp pins, managed snapshot overrides and genuine release drift. The minimal case now returns strict 0. [After native proof and commands](evidence/bug-after.json), [after logs](evidence/bug-after.log), [regression implementation](../../scripts/verify_maven.py).

| Frozen consumer | Target SHA | False findings removed | Genuine drift retained |
| --- | --- | --- | --- |
| spring-cloud-gateway | a6e4b522dbd2cc48e1040f030556c00ea6dcda04 | 54 | 3 |
| spring-cloud-stream | 930fd07da6417a30b8a1203b0bd18b1d9cae3242 | 40 | 0 |
| spring-cloud-kubernetes | 5d653390555abbef31abeb2c0e3d36d955dc2e6f | 25 | 0 |
| spring-cloud-netflix | fd54279c3357d280344ff5bde42c8a0474eeb430 | 41 | 0 |
| spring-cloud-commons | 31ecfe5589fc20bdf263705904c2b202f66aaeba | 42 | 0 |

All five native dependency trees are identical before/after. Each fixed run checks actual artifacts, an independent pristine BOM oracle, warning/strict exits and repeat determinism offline with networking disabled. The three retained Gateway findings are genuine gRPC drift: 1.85.1 selected versus 1.84.1 expected. See `evidence/fix/078.json`, `079.json`, `080.json`, `082.json`, `100.json` and adjacent logs.

### Reproduce

Use JDK 21 and Maven 3.9.16. Historical mutable SNAPSHOT downloads may differ; the product's frozen fixture is the durable regression.

```powershell
mvn -B -ntp install
python scripts/verify_maven.py MavenSnapshotIntegrationTest
python scripts/verify_maven.py --offline MavenSnapshotIntegrationTest
$pom = 'reports/real-world-2026-10-26/repro/pom.xml'
mvn -B -ntp -N -f $pom org.apache.maven.plugins:maven-dependency-plugin:3.10.0:tree -DoutputType=json
mvn -B -ntp -N -f $pom org.apache.maven.plugins:maven-dependency-plugin:3.10.0:resolve
mvn -B -ntp -N -f $pom io.github.bootbomguard:boot-bom-guard-maven-plugin:0.1.0-SNAPSHOT:check -DbootBomGuard.failOnDrift=true
```

The archived command arrays also record the isolated container image digest, exact flags, exits and wall times. Native resolved graphs and normalized pristine expected models are retained in their bundles.

## Findings that are not guard defects

- Boot 1/2/3, a Gradle daemon below the supported JVM boundary, and Spring DSL management without a native platform remain explicit unsupported outcomes.
- Alibaba's effective management contains entries sourced from both Boot 4.0.7 and 4.1.0. UNKNOWN is the documented mixed-source contract; shadowed raw declarations alone are not used as evidence.
- Default Maven reactors include BOM-only modules without their own Boot BOM. UNKNOWN and strict failure at those modules are expected; the supported consumers were independently compared per module.
- Missing sibling binaries were bootstrapped from the unchanged source where possible. Native compilation failures, unavailable external artifacts, transport truncation and exhausted timeouts are recorded as baseline blockers.
- Old Gradle init-script API mistakes, a missing wrapper JAR, incorrect toolchain flags, a copied JDK symlink and empty aggregation-project graphs were harness errors. Their initial attempts remain in evidence/history and were superseded by corrected retries. None is a product defect.

One distinct product defect was confirmed and fixed. No additional false negative, crash, nondeterminism or sensitive-data exposure defect was established by the exercised cases. This does not certify untested configurations.
