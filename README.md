# Boot BOM Guard

Reports differences between resolved dependencies and the versions managed by the selected Spring Boot 4 BOM. Java 21. Warning-only by default; opt into CI failure. A difference is **drift**, not a claim of binary incompatibility.

```
core/           Coordinates, comparison, classification vocabulary, exceptions, deterministic text reports
maven-plugin/   Native Maven effective model, BOM model building and resolved graph
gradle-plugin/  Native Gradle platforms, constraints and resolution results
fixtures/       Runnable Maven, Gradle Groovy DSL and Gradle Kotlin DSL projects
```

No runtime dependencies in core. No script/POM text parsing, custom resolver, telemetry, scanning service or automatic upgrades.

## Build and verify

Requires JDK 21, Maven 3.9.16+, Python 3 (Maven integration assertions only). Gradle 8.14.3 is pinned by the checksum-verified wrapper. The plugin also runs on Gradle 9.x; see [verification](VERIFICATION.md) for the actual tested versions.

```sh
mvn -B -ntp install
python scripts/verify_maven.py
./gradlew check
```

On Windows use `gradlew.bat`. Maven installs the local snapshot and its core dependency. Gradle tests use TestKit's plugin classpath; consumer examples below use a composite build. Nothing has been published to Maven Central or the Gradle Plugin Portal.

After the first resolution, test the cached dependencies without repository access:

```sh
python scripts/verify_maven.py --offline
./gradlew --offline check -PtestOffline=true
```

`-PtestOffline=true` also passes `--offline` to the nested TestKit builds. A new machine needs the Gradle distribution and dependencies cached first.

## Maven

Use a Spring Boot parent or import its BOM. Declare the guard under **build/plugins** so Maven can resolve the `boot-bom-guard` prefix:

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-dependencies</artifactId>
      <version>4.0.0</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
<build>
  <plugins>
    <plugin>
      <groupId>io.github.bootbomguard</groupId>
      <artifactId>boot-bom-guard-maven-plugin</artifactId>
      <version>0.1.0-SNAPSHOT</version>
      <configuration>
        <failOnDrift>false</failOnDrift>
        <exceptions>
          <exception>
            <dependency>org.slf4j:slf4j-api</dependency>
            <reason>Reviewed logging upgrade</reason>
          </exception>
        </exceptions>
      </configuration>
    </plugin>
  </plugins>
</build>
```

```sh
mvn boot-bom-guard:check
mvn boot-bom-guard:check -DbootBomGuard.failOnDrift=true
mvn --offline boot-bom-guard:check
```

Alternatively use the full goal coordinate, without prefix lookup:
`mvn io.github.bootbomguard:boot-bom-guard-maven-plugin:0.1.0-SNAPSHOT:check`.
An execution bound to `verify` is optional; the guard does not run until invoked/bound. Configure the exception only when you intend to accept that dependency's drift.

Maven uses effective dependency-management source locations to identify the BOM, including inherited Boot parents and active profile imports. Shadowed raw imports do not create false ambiguity. A clean, separately built effective Boot BOM supplies the baseline, so a consumer's `slf4j.version` property cannot overwrite the expected version. The selected dependency graph includes direct and transitive project dependencies across Maven scopes, preserving artifact type/classifier; build-plugin dependencies are excluded.

When a project effectively combines managed entries sourced from multiple Boot BOM versions, analysis reports `UNKNOWN` rather than choosing one. If effective source locations are unavailable, BOM identification is unsupported and reports unknown. Maven may itself reject an invalid effective project before any goal can execute.

## Gradle — Groovy DSL

For local use, put this first in the consumer's `settings.gradle`:

```groovy
pluginManagement {
    includeBuild('E:/boot-bom-guard')
}
```

`build.gradle`:

```groovy
plugins {
    id 'java'
    id 'io.github.bootbomguard'
}
repositories { mavenCentral() }
dependencies {
    implementation platform('org.springframework.boot:spring-boot-dependencies:4.0.0')
    implementation 'org.slf4j:slf4j-api:2.0.18'
}
bootBomGuard {
    failOnDrift = false
    // Optional: accepts this coordinate's drift, with a mandatory reason.
    exceptions.put('org.slf4j:slf4j-api', 'Reviewed logging upgrade')
    // Optional: defaults cover compile/runtime and test compile/runtime classpaths.
    // configurations.set(['runtimeClasspath'])
}
```

```sh
./gradlew bootBomGuard
./gradlew --offline bootBomGuard
```

Set `failOnDrift = true` in the extension for CI. A consumer can wire it to a Gradle property using
`failOnDrift = providers.gradleProperty('failOnDrift').map { it.toBoolean() }.getOrElse(false)`.
The fixture uses this binding; `-PfailOnDrift=true` alone is not a global plugin setting.

## Gradle — Kotlin DSL

`settings.gradle.kts`:

```kotlin
pluginManagement {
    includeBuild("E:/boot-bom-guard")
}
```

`build.gradle.kts`:

```kotlin
plugins {
    java
    id("io.github.bootbomguard")
}
repositories { mavenCentral() }
dependencies {
    implementation(platform("org.springframework.boot:spring-boot-dependencies:4.0.0"))
    implementation("org.slf4j:slf4j-api:2.0.18")
}
bootBomGuard {
    failOnDrift.set(false)
    exceptions.put("org.slf4j:slf4j-api", "Reviewed logging upgrade")
    // configurations.set(listOf("runtimeClasspath"))
}
```

The task is registered lazily and resolves graphs during task execution. Apply it per project. Default configurations are `compileClasspath`, `runtimeClasspath`, `testCompileClasspath`, `testRuntimeClasspath`; custom JVM configurations can be selected explicitly. Missing/non-resolvable configurations report `UNKNOWN`.

Gradle's selected Boot platform version is authoritative. Multiple requested versions can resolve to one selected version; the report records the requests and selected platform categories. A regular `platform` recommends versions and permits other dependencies/constraints to select a higher version. `enforcedPlatform` forces platform versions and can align an otherwise overriding request. Conflicting strict requirements can leave the graph unresolved; this is incomplete analysis, never an aligned pass.

The baseline is a separate Gradle configuration containing the exact selected Boot platform plus versionless, non-transitive requests for actual library modules. Gradle resolves the platform's imported constraints. Library transitive requests, source configuration forces and source constraints cannot contaminate that baseline. Versions are module-level in Gradle; Maven's type/classifier management semantics are not imposed on it.

MVP boundaries: native platforms only (including a platform brought in transitively), external JVM modules and exact BOM versions/constraints. Spring's separate `io.spring.dependency-management` DSL without a native Boot platform is unsupported and reports missing BOM. Dependency substitutions report `UNKNOWN`. Arbitrary component-metadata rewriting plugins are outside the supported contract. Configuration cache and Gradle 10 are unsupported: execution-time native Project access is deprecated for removal in Gradle 10. Configuration remains lazy and no application compilation is required.

## Policy and reports

Example (adapter evidence abbreviated):

```text
boot-bom-guard BOM=org.springframework.boot:spring-boot-dependencies:4.0.0
DRIFT org.slf4j:slf4j-api expected=2.0.17 resolved=2.0.18 classification=DIRECT_OVERRIDE evidence=...
WARN checked=1 drift=1 unknown=0
```

| Classification | Factual evidence |
| --- | --- |
| `DIRECT_OVERRIDE` | A selected direct dependency request differs from the BOM baseline |
| `MANAGED_OVERRIDE` | Maven effective management or a Gradle root constraint matches the differing selected version |
| `TRANSITIVE_DRIFT` | A selected transitive request/path differs from the baseline |
| `UNKNOWN_ORIGIN` | Drift is confirmed, but origin is not reliable (for example Gradle force/rule selection) |

These labels describe observed evidence, not a proof of the sole cause or an incompatibility verdict. Gradle constraint provenance remains unknown even when a root constraint is observed. Maven reports transitive drift caused by changed effective management as `MANAGED_OVERRIDE`, with `path=transitive`; root dependencyManagement normally wins over transitive requests.

`PASS` means no unaccepted drift or incomplete-analysis diagnostics for the inspected graph. `WARN` is the default outcome when either exists. `failOnDrift=true` turns that policy result into a failing build. Missing/ambiguous BOMs and resolution failures also fail CI when opted in. Invalid configuration always fails. `checked` counts resolved managed coordinates; unused BOM entries are not drift.

Exceptions use exact `group:artifact` keys (jar, no classifier), or `group:artifact:type:classifier` for Maven variants. Reasons must be nonblank. No wildcards. An exception accepts drift at that coordinate across versions; review/remove it when changing BOMs. It does not suppress incomplete analysis. Allowed findings still show expected/resolved versions, classification and reason. Output is sorted and control characters are escaped.

## Resolution and security

All resolution uses each build tool's configured repositories, mirrors, credentials and offline mode. Running the task may fetch BOM metadata, imported BOMs and dependency metadata; Maven's resolved graph API may also fetch artifacts. The guard makes no separate HTTP requests and adds no repositories to consumer builds. The examples/tests explicitly use Maven Central. Offline mode does not bypass missing caches. Resolver exception text is omitted from guard reports to avoid exposing credentials in repository URLs; use the build tool's own diagnostics to troubleshoot.

Research and bounded smaller-agent review are recorded in [DESIGN.md](DESIGN.md). Actual commands, test counts and remaining limitations are in [VERIFICATION.md](VERIFICATION.md).
