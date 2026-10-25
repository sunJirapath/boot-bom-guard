# boot-bom-guard — Spring Boot BOM drift checks for Maven and Gradle

[![CI](https://github.com/sunJirapath/boot-bom-guard/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/sunJirapath/boot-bom-guard/actions/workflows/ci.yml)
[![Java 21](https://img.shields.io/badge/Java-21-blue)](#install)
[![Spring Boot 4](https://img.shields.io/badge/Spring%20Boot-4-green)](#install)
[![Maven 3.9.16+](https://img.shields.io/badge/Maven-3.9.16%2B-blue)](#maven)
[![Gradle 8.14.3 / 9.8.2](https://img.shields.io/badge/Gradle-8.14.3%20%2F%209.8.2-blue)](#gradle--groovy-dsl)

Reports dependencies whose resolved versions differ from the selected **Spring Boot 4 BOM**. Native Maven and
Gradle resolution, one comparison policy, warning-only by default. ตรวจสอบ dependency ที่ใช้เวอร์ชันต่างจาก Spring Boot BOM.

**Features:** expected/resolved versions · direct and transitive drift · intentional exceptions with reasons ·
optional CI failure · Maven, Gradle Groovy DSL and Gradle Kotlin DSL.

> **A version difference is drift, not proof of incompatibility.** Missing, ambiguous or unsupported analysis
> is reported as `UNKNOWN`; a passing check does not guarantee application runtime compatibility.

[English](#english) · [ภาษาไทย](#ภาษาไทย)

## English

### Install

Current version: **0.1.0-SNAPSHOT**, available from this source checkout only. Nothing has been published to
Maven Central or the Gradle Plugin Portal.

**Supported and tested:** JDK 21, Maven 3.9.16, Gradle 8.14.3 and 9.8.2, Spring Boot 4. The wrapper pins Gradle
8.14.3 with a distribution checksum. Maven requires 3.9.16 or newer; unlisted versions are unverified.
See [VERIFICATION.md](VERIFICATION.md) for exact commands and test coverage.

Build and install the Maven plugin and its core dependency from the repository root:

```sh
mvn -B -ntp install
```

Gradle consumers use the local composite build shown below. On Windows use `gradlew.bat` instead of `./gradlew`.

### Quick start

After installation, try the included fixtures from the repository root. Both deliberately override
`slf4j-api` to show a warning without failing the build:

```sh
mvn -f fixtures/maven/aligned/pom.xml boot-bom-guard:check -Pdirect
./gradlew -p fixtures/gradle/groovy "-PguardBuild=../../.." bootBomGuard -Pscenario=direct
```

Report excerpt (adapter evidence abbreviated):

```text
boot-bom-guard BOM=org.springframework.boot:spring-boot-dependencies:4.0.0
DRIFT org.slf4j:slf4j-api expected=2.0.17 resolved=2.0.18 classification=DIRECT_OVERRIDE evidence=...
WARN checked=1 drift=1 unknown=0
```

For your own project, configure [Maven](#maven), [Gradle Groovy DSL](#gradle--groovy-dsl), or
[Gradle Kotlin DSL](#gradle--kotlin-dsl). The examples include an optional, reasoned exception; remove it to report
that coordinate's drift as a warning.

### Maven

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

### Gradle — Groovy DSL

With the consumer and `boot-bom-guard` checkouts in sibling directories, put this first in the consumer's
`settings.gradle` (adjust the path for your checkout):

```groovy
pluginManagement {
    includeBuild('../boot-bom-guard')
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

### Gradle — Kotlin DSL

`settings.gradle.kts`:

```kotlin
pluginManagement {
    includeBuild("../boot-bom-guard")
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

### Modules

| Module | Contents |
| --- | --- |
| `core` | Coordinates, version comparison, classification vocabulary, exceptions and deterministic text reports |
| `maven-plugin` | Native effective model, BOM model building and resolved dependency graph |
| `gradle-plugin` | Native platforms, constraints and dependency resolution results |
| `fixtures` | Runnable Maven, Gradle Groovy DSL and Gradle Kotlin DSL examples |

Core has no runtime dependencies or build-tool APIs. Each adapter determines its own expected and resolved
versions using native resolution semantics.

### Policy and reports

| Classification | Factual evidence |
| --- | --- |
| `DIRECT_OVERRIDE` | A selected direct dependency request differs from the BOM baseline |
| `MANAGED_OVERRIDE` | Maven effective management or a Gradle root constraint matches the differing selected version |
| `TRANSITIVE_DRIFT` | A selected transitive request/path differs from the baseline |
| `UNKNOWN_ORIGIN` | Drift is confirmed, but origin is not reliable (for example Gradle force/rule selection) |

These labels describe observed evidence, not a proof of the sole cause or an incompatibility verdict. Gradle constraint provenance remains unknown even when a root constraint is observed. Maven reports transitive drift caused by changed effective management as `MANAGED_OVERRIDE`, with `path=transitive`; root dependencyManagement normally wins over transitive requests.

`PASS` means no unaccepted drift or incomplete-analysis diagnostics for the inspected graph. `WARN` is the default outcome when either exists. `failOnDrift=true` turns that policy result into a failing build. Missing/ambiguous BOMs and resolution failures also fail CI when opted in. Invalid configuration always fails. `checked` counts resolved managed coordinates; unused BOM entries are not drift.

Exceptions use exact `group:artifact` keys (jar, no classifier), or `group:artifact:type:classifier` for Maven variants. Reasons must be nonblank. No wildcards. An exception accepts drift at that coordinate across versions; review/remove it when changing BOMs. It does not suppress incomplete analysis. Allowed findings still show expected/resolved versions, classification and reason. Output is sorted and control characters are escaped.

### Resolution and security

All resolution uses each build tool's configured repositories, mirrors, credentials and offline mode. Running the task may fetch BOM metadata, imported BOMs and dependency metadata; Maven's resolved graph API may also fetch artifacts. The guard makes no separate HTTP requests and adds no repositories to consumer builds. The examples/tests explicitly use Maven Central. Offline mode does not bypass missing caches. Resolver exception text is omitted from guard reports to avoid exposing credentials in repository URLs; use the build tool's own diagnostics to troubleshoot.

### Build and contribute

Requires JDK 21 and Maven 3.9.16+. Python 3 is needed only for the Maven integration assertions.

```sh
mvn -B -ntp install
python scripts/verify_maven.py
./gradlew check
```

The suites exercise real Spring Boot 4 dependency resolution, not mocked graphs. Gradle uses TestKit's plugin
classpath; consumer examples use a composite build. The completed verification has 12 core tests, 15 Maven
integration tests and 25 Gradle integration tests; see [VERIFICATION.md](VERIFICATION.md).

After the first resolution, test the cached dependencies without repository access:

```sh
python scripts/verify_maven.py --offline
./gradlew --offline check -PtestOffline=true
```

`-PtestOffline=true` also passes `--offline` to the nested TestKit builds. A new machine needs the Gradle
distribution and dependencies cached first. The [CI workflow](.github/workflows/ci.yml) runs the full Maven and Gradle suites
on Ubuntu with Java 21, Maven 3.9.16 and the Gradle 8.14.3 wrapper. Pull requests run the same checks; the README
status badge follows `main` and shows its result after the workflow is merged and runs there.
Coverage badge is omitted: no coverage service is configured. Licensed under [Apache-2.0](LICENSE).

Research and bounded smaller-agent review are recorded in [DESIGN.md](DESIGN.md). Actual commands, test counts
and remaining limitations are in [VERIFICATION.md](VERIFICATION.md).

## ภาษาไทย

ปลั๊กอินสำหรับตรวจสอบ dependency ที่ resolve ได้จริงว่าใช้เวอร์ชันต่างจากที่ **Spring Boot 4 BOM** กำหนดหรือไม่
รองรับ Maven และ Gradle ทั้ง Groovy DSL และ Kotlin DSL โดยใช้ API ของแต่ละ build tool และแสดงเวอร์ชันที่คาดหวัง
เวอร์ชันที่ใช้จริง พร้อมหลักฐานประกอบ ค่าเริ่มต้นแสดงคำเตือนโดยไม่ทำให้ build ล้มเหลว

### ติดตั้ง

เวอร์ชันปัจจุบัน **0.1.0-SNAPSHOT** ต้อง build จาก source ยังไม่ได้เผยแพร่บน Maven Central หรือ Gradle Plugin Portal
ใช้ JDK 21 และ Maven 3.9.16 ขึ้นไป ส่วน Gradle ทดสอบแล้วบน 8.14.3 และ 9.8.2

รันจากโฟลเดอร์ repository เพื่อติดตั้ง Maven plugin และ core ลง local repository:

```sh
mvn -B -ntp install
```

สำหรับ Gradle ใช้ local composite build ตามตัวอย่าง [Groovy DSL](#gradle--groovy-dsl) หรือ
[Kotlin DSL](#gradle--kotlin-dsl) และปรับ `includeBuild` ให้ตรงกับตำแหน่ง checkout ของคุณ

### เริ่มต้นใช้งาน

หลังตั้งค่า plugin ในโปรเจกต์แล้ว:

```sh
# Maven
mvn boot-bom-guard:check

# Gradle
./gradlew bootBomGuard
```

บน Windows ใช้ `gradlew.bat` ดูตัวอย่างที่รันได้ทันทีใน [Quick start](#quick-start)

### ผลลัพธ์และนโยบาย

- `DRIFT` คือเวอร์ชันต่างจาก BOM ไม่ได้ยืนยันว่าเข้ากันไม่ได้
- `ALLOWED` คือยอมรับความต่างของ dependency ที่ระบุไว้ โดยต้องมีเหตุผลที่ไม่ว่าง
- `UNKNOWN` คือข้อมูลไม่ครบ หา BOM ไม่ได้ มีความกำกวม หรือเป็นกรณีที่ยังไม่รองรับ
- `PASS` คือไม่พบ drift ที่ยังไม่ได้ยอมรับหรือปัญหาการวิเคราะห์ ส่วน `WARN` เป็นค่าเริ่มต้นเมื่อพบปัญหา

หากต้องการให้ CI ล้มเหลว ใช้ `-DbootBomGuard.failOnDrift=true` สำหรับ Maven หรือกำหนด `failOnDrift` เป็น `true`
ใน Gradle extension ข้อยกเว้นต้องเป็น coordinate แบบเจาะจงและมีเหตุผล ไม่รองรับ wildcard และไม่ซ่อนผล `UNKNOWN`
ดู [Policy and reports](#policy-and-reports) สำหรับรายละเอียด

### ข้อจำกัด

Gradle รองรับ native `platform` และ `enforcedPlatform` โดยแยกความหมายของทั้งสองแบบ ไม่เดาที่มาของ constraint
เมื่อไม่มีหลักฐานเพียงพอ ยังไม่รองรับ configuration cache และ Gradle 10 ทดสอบแล้วบน Windows และ Ubuntu 24.04 ส่วน Maven 4 และ macOS ยังไม่ได้ทดสอบ
การ resolve อาจดาวน์โหลดข้อมูลผ่าน repository ที่ build tool ตั้งค่าไว้ ใช้ `--offline` ได้เมื่อมี cache ครบแล้ว

คำสั่งทดสอบอยู่ใน [Build and contribute](#build-and-contribute) และหลักฐานผลทดสอบอยู่ใน [VERIFICATION.md](VERIFICATION.md)
