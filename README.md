# boot-bom-guard — Spring Boot BOM drift checks for Maven and Gradle

[![CI](https://github.com/sunJirapath/boot-bom-guard/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/sunJirapath/boot-bom-guard/actions/workflows/ci.yml)
[![Java target 17+](https://img.shields.io/badge/Java_target-17%2B-blue)](#install)
[![Spring Boot fixtures 3.5.16 / 4.0.0 / 4.0.1 / 4.1.0](https://img.shields.io/badge/Spring_Boot_fixtures-3.5.16%20%2F%204.0.0%20%2F%204.0.1%20%2F%204.1.0-green)](#install)
[![Maven 3.9.16+](https://img.shields.io/badge/Maven-3.9.16%2B-blue)](#maven)
[![Gradle 8.14.3 / 9.8.2](https://img.shields.io/badge/Gradle-8.14.3%20%2F%209.8.2-blue)](#gradle--groovy-dsl)

Reports dependencies whose resolved versions differ from the selected **Spring Boot 3.5.x or 4.x BOM**. Native Maven and
Gradle resolution, one comparison policy, warning-only by default. ตรวจสอบ dependency ที่ใช้เวอร์ชันต่างจาก Spring Boot BOM.

**Features:** expected/resolved versions · direct and transitive drift · intentional exceptions with reasons ·
optional CI failure · Maven, Gradle Groovy DSL and Gradle Kotlin DSL.

> **A version difference is drift, not proof of incompatibility.** Missing, ambiguous or unsupported analysis
> is reported as `UNKNOWN`; a passing check does not guarantee application runtime compatibility.

[English](#english) · [ภาษาไทย](#ภาษาไทย)

## English

### Install

This checkout builds **0.1.1-SNAPSHOT** (`io.github.sunjirapath.bootbomguard`). The Maven examples below
use that source-installed version. To use a released artifact instead, first verify its availability in Maven
Central and use its version in both the plugin declaration and full goal coordinate. Remote publication is not
verified by these source-install instructions; a Git tag or release profile alone does not establish it.
The Gradle examples use a local source composite build; they do not rely on Plugin Portal publication.

**Supported and tested:** the plugins target **Java 17+ runtime** and BOM drift checks for **Boot 3.5.x and 4.x**.
Exact real BOM fixture versions are **3.5.16**, **4.0.0**, **4.0.1**, and **4.1.0** (the last is used only for mixed-source ambiguity).
The 3.5.16 fixtures and Java 17 changes are **added but not executed** in this round; historical execution evidence covers
JDK 21, Maven 3.9.16 / 3.10.0 and Gradle 8.14.3 / 9.8.2. No claim is made for Boot **3.0–3.4, 2.x**, other exact
Boot versions, or application runtime compatibility. Accepting a major version is not evidence for every release in it.
The wrapper pins Gradle 8.14.3 with a distribution checksum. Maven requires 3.9.16 or newer; unlisted versions are unverified.
Maven 4.0.0-rc-7 has historical full-suite results as preview compatibility, without a stable Maven 4 support guarantee.
See [VERIFICATION.md](VERIFICATION.md) for exact commands and test coverage.

Build and install the Maven plugin and its core dependency as `0.1.1-SNAPSHOT` from the repository root:

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
      <groupId>io.github.sunjirapath.bootbomguard</groupId>
      <artifactId>boot-bom-guard-maven-plugin</artifactId>
      <version>0.1.1-SNAPSHOT</version>
      <configuration>
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

`failOnDrift` defaults to `false`. Leave it out of `<configuration>` when using the command-line switch;
a literal POM value overrides that switch.

Alternatively use the full goal coordinate, without prefix lookup:
`mvn io.github.sunjirapath.bootbomguard:boot-bom-guard-maven-plugin:0.1.1-SNAPSHOT:check`.
An execution bound to `verify` is optional; the guard does not run until invoked/bound. Configure the exception only when you intend to accept that dependency's drift.

Maven uses effective dependency-management source locations to identify the BOM, including inherited Boot parents and active profile imports. Shadowed raw imports do not create false ambiguity. A clean, separately built effective Boot BOM supplies the baseline, so a consumer's `slf4j.version` property cannot overwrite the expected version. The selected dependency graph includes direct and transitive project dependencies across Maven scopes, preserving artifact type/classifier; build-plugin dependencies are excluded.

For comparable Maven snapshots, Resolver translates BOM and effective managed versions to their native timestamped identities using metadata for the artifact extension and classifier. An alias and its selected timestamp align; an explicitly pinned older timestamp remains drift. Missing snapshot identity metadata reports `UNKNOWN` and fails strict mode.

When a project effectively combines managed entries sourced from multiple Boot BOM versions, analysis reports `UNKNOWN` rather than choosing one. If effective source locations are unavailable, BOM identification is unsupported and reports unknown. Maven may itself reject an invalid effective project before any goal can execute.

Maven dependency relocations report `UNKNOWN` because renamed coordinates cannot be compared reliably against the original BOM entry; strict mode fails. Reactor execution checks each module independently and supports parallel `-T` execution; it does not produce an aggregated reactor report. The adapter walks graphs iteratively and retains shortest direct paths for shared nodes.

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
    id 'io.github.sunjirapath.bootbomguard'
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

The plugin attaches `bootBomGuard` to every `check` task in the same project, including one registered later.
With strict mode enabled, an existing `./gradlew check` CI job therefore fails on drift or incomplete analysis.
Projects without a `check` task must invoke `bootBomGuard` explicitly.

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
    id("io.github.sunjirapath.bootbomguard")
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

The baseline is a separate Gradle configuration containing the exact selected Boot platform plus versionless, non-transitive requests for actual library modules. Gradle resolves the platform's imported constraints. Library transitive requests, source configuration forces and source constraints are excluded from that baseline. Project/settings-wide component metadata rules still apply: do not rewrite the Boot BOM or its imported BOMs when using this policy gate; partial rewrites can change expected versions. A detached configuration is not an independent metadata environment. Versions are module-level in Gradle; Maven's type/classifier management semantics are not imposed on it.

MVP boundaries: native platforms only (including a platform brought in transitively), external JVM modules and exact BOM versions/constraints. Non-exact Boot BOM requests (ranges, dynamic versions or `latest.*`) report `UNKNOWN` even when Gradle selects one concrete version. Required, strict and preferred selectors must each be exact when present. Spring's separate `io.spring.dependency-management` DSL without a native Boot platform is unsupported and reports missing BOM. Dependency substitutions and rule-selected modules report `UNKNOWN`, including version-only substitutions within the same `group:artifact`. Gradle's shared rule-selection signal cannot distinguish substitutions from other selection rules, so even an aligned rule-selected module is conservatively incomplete; native conflict resolution remains supported. The isolated baseline disables global composite-build substitutions and must resolve the selected Boot platform and its nested platforms; missing baseline metadata or removal of every managed constraint reports incomplete analysis. Exact preferred-only constraints are supported. Local file dependencies declared/inherited on an inspected configuration report `UNKNOWN` because they have no comparable module identity. Checks apply per JVM project; they do not audit every transitive project’s local files. Arbitrary BOM metadata rewriting remains outside the supported contract. Configuration-cache reuse is unsupported; requesting `--configuration-cache` safely discards the incompatible entry and still executes warning/strict policy on both tested versions. Gradle 10 is unsupported: execution-time native Project access is deprecated for removal in Gradle 10. Configuration remains lazy and no application compilation is required.

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

Exceptions use exact `group:artifact` keys (jar, no classifier), or `group:artifact:type:classifier` for Maven variants. Reasons must be nonblank. No wildcards. An exception accepts drift at that coordinate across versions; review/remove it when changing BOMs. It does not suppress incomplete analysis. An exception with no resolved managed coordinate produces an `UNKNOWN Unmatched exception` diagnostic and fails strict mode. Matching is checked per inspected graph/configuration; a present, aligned managed dependency still matches. Remove obsolete keys and Maven classifier keys copied into Gradle, or scope the inspected configurations appropriately. Allowed findings still show expected/resolved versions, classification and reason. Output is sorted and control characters are escaped.

Both adapters currently expose text logs only. No JSON, SARIF, JUnit XML or report file is emitted.
Structured CI reporting is unsupported; use strict mode as the gate. A successful warning-mode build is not evidence of alignment.
Build exit codes do not distinguish drift, incomplete analysis and invalid configuration; inspect the diagnostic text for that distinction.

| Outcome | Default build exit | Strict build exit |
| --- | --- | --- |
| Aligned or allowed drift (`PASS`) | 0 | 0 |
| Unaccepted drift (`WARN` / `DRIFT`) | 0 | 1 |
| Incomplete analysis or unmatched exception (`WARN` / `UNKNOWN`) | 0 | 1 |
| Invalid guard configuration | 1 | 1 |

These codes describe standalone guard invocations when the build tool reaches the guard; other build failures can also fail the command.

### Resolution and security

All resolution uses each build tool's configured repositories, mirrors, credentials and offline mode. Running the task may fetch BOM metadata, imported BOMs and dependency metadata; Maven's resolved graph API may also fetch artifacts. The guard makes no separate HTTP requests and adds no repositories to consumer builds. The examples/tests explicitly use Maven Central. Offline mode does not bypass missing caches. Guard reports include sanitized exception summaries, bounded to five causes and 300 characters per message before escaping. URL userinfo and common named secrets are redacted, including Basic/Bearer authorization and quoted values. Custom secret formats may not be recognized; keep them out of exception messages. Use the build tool's own diagnostics to troubleshoot.

### Build and contribute

Requires JDK 17 and Maven 3.9.16+. Gradle compiles core and the plugin with a Java 17 toolchain and `--release 17`;
install JDK 17 alongside JDK 21 when running Gradle on 21. Tests use the build JVM's Java major, retaining Java 21
coverage alongside the new Java 17 CI lane. The build tool's own JVM requirements still apply.
Python 3 is needed only for the Maven integration assertions.

```sh
mvn -B -ntp install
python scripts/verify_maven.py
./gradlew check
```

For a repeatable cold-cache source-install check, run:

```sh
python scripts/verify_install.py
# Optional: repeat --gradle for other installed distributions.
python scripts/verify_install.py --gradle /path/to/gradle-8.14.3/bin/gradle --gradle /path/to/gradle-9.8.2/bin/gradle
```

This downloads dependencies into fresh Maven/Gradle caches, copies the consumer fixtures to an OS temporary directory outside the checkout, and checks aligned, warning, strict-failure and reasoned-exception scenarios. Kotlin DSL covers a strict allowed exception; Groovy DSL and Maven cover all four policies. Logs and caches are retained under ignored `build/install-smoke-*`; the command prints the consumer directory.

The integration suites contain real Spring Boot 3.5.16 and 4.0.0/4.0.1 BOM resolution cases; Maven also uses 4.1.0 for
mixed-source ambiguity. Boot 3 fixtures are under `fixtures/maven/boot35` and `fixtures/gradle/boot35`.
Both Gradle DSLs cover native platform/enforcedPlatform, exact strict overrides, unresolved conflicting BOM requests,
non-exact BOM requests, rule selection, allowed drift and stale exceptions. The Spring 6/Jakarta case requests
`spring-core` and `jakarta.servlet-api` without pinning their versions; it checks BOM resolution, not framework/EE runtime behavior.
Maven covers imported/parent BOMs, direct/managed/transitive overrides and ambiguity, plus frozen synthetic 3.5.16-qualified
snapshot BOMs. Snapshot alias/timestamp/classifier tests do not exercise public Boot snapshot releases.
Expected Boot 3 managed versions come from native BOM resolution; assertions do not hardcode unread BOM values.
These additions have not run. A separate Maven adapter unit suite uses native Resolver node objects to test traversal limits without publishing 20,000 artifacts. Gradle uses TestKit's plugin
classpath; consumer examples use a composite build. Current source inventory is recorded below and checked by
`test_readme_test_inventory_matches_sources`; shared core tests are counted once, and parameterized values count separately.
See [VERIFICATION.md](VERIFICATION.md), the [adversarial audit](ADVERSARIAL-AUDIT.md), and [measured core performance](PERFORMANCE.md) for revision-specific execution evidence.
The review-round changes have only been reviewed statically; source counts do not establish passing tests.

| Suite | Source cases |
| --- | ---: |
| Core | 28 |
| Maven adapter | 4 |
| Python Maven integrations | 43 |
| Gradle integrations | 63 |
| Total | 138 |

The Python suite includes three documentation/CI contract checks. The Spring dependency-management-only
TestKit regression also needs `io.spring.dependency-management:1.1.7` cached before an offline run.

After the first resolution, test with cached remote dependencies:

```sh
python scripts/verify_maven.py --offline
./gradlew --offline check -PtestOffline=true
```

The Maven snapshot regressions generate a frozen local file repository and prime it through native resolution in online Resolver mode, including when `--offline` is set. The guard invocations then honor `--offline`; the dependency plugin must already be cached to run without network access. No mutable public snapshots are used by these regressions. Repository-authentication tests use loopback HTTP and dummy credentials; the Gradle transport probe intentionally runs online even when TestKit offline mode is requested.

`-PtestOffline=true` also passes `--offline` to the nested TestKit builds. A new machine needs the Gradle
distribution and dependencies cached first. The [CI workflow](.github/workflows/ci.yml) runs the full Maven and Gradle suites
on Ubuntu with Java 21, Maven 3.9.16 and a Gradle 8.14.3 / 9.8.2 matrix, plus macOS 15 and Windows Server 2025 with Gradle 8.14.3.
A new Ubuntu / Java 17 / Gradle 8.14.3 lane runs the same suites. Java 21 lanes install JDK 17 for compilation.
Each of these jobs also checks a source install with empty caches and external Maven/Groovy/Kotlin consumers.
The new Java 17 lane and Windows job have not been executed as part of this review. Separate Ubuntu jobs run the full Maven suites with 3.10.0 and preview 4.0.0-rc-7. Pull requests run the same checks; the README
status badge follows `main` and shows its result after the workflow is merged and runs there.
Licensed under the [MIT License](LICENSE). No coverage badge is shown because no coverage service is configured.

Research and bounded smaller-agent review are recorded in [DESIGN.md](DESIGN.md). Actual commands, test counts
and remaining limitations are in [VERIFICATION.md](VERIFICATION.md).

## ภาษาไทย

ปลั๊กอินสำหรับตรวจสอบ dependency ที่ resolve ได้จริงว่าใช้เวอร์ชันต่างจากที่ **Spring Boot 3.5.x หรือ 4.x BOM** กำหนดหรือไม่
รองรับ Maven และ Gradle ทั้ง Groovy DSL และ Kotlin DSL โดยใช้ API ของแต่ละ build tool และแสดงเวอร์ชันที่คาดหวัง
เวอร์ชันที่ใช้จริง พร้อมหลักฐานประกอบ ค่าเริ่มต้นแสดงคำเตือนโดยไม่ทำให้ build ล้มเหลว

### ติดตั้ง

checkout นี้ build เวอร์ชัน **0.1.1-SNAPSHOT** (`io.github.sunjirapath.bootbomguard`) ตัวอย่าง Maven ใช้เวอร์ชันที่ติดตั้งจาก source นี้
หากจะใช้ release ต้องตรวจสอบว่ามีใน Maven Central ก่อน แล้วเปลี่ยนเวอร์ชันใน plugin declaration และ full goal ให้ตรงกัน คำแนะนำนี้ไม่ได้ยืนยันสถานะการเผยแพร่
ตัวอย่าง Gradle ใช้ local composite build จาก source โดยไม่อาศัย Plugin Portal
ปลั๊กอินตั้งเป้า runtime **Java 17+** โดยเพิ่ม fixture ของ Boot **3.5.16** ควบคู่กับ **4.0.0 / 4.0.1** และ **4.1.0** (เฉพาะกรณี BOM กำกวม)
รอบนี้ยังไม่ได้รัน build หรือ test ของ 3.5.16 และ Java 17 จึงยังไม่ยืนยันว่าผ่าน ไม่อ้างรองรับ **3.0–3.4, 2.x**, เวอร์ชันอื่นที่ไม่ได้ทดสอบ หรือความเข้ากันได้ขณะรันแอป
หลักฐานที่เคยรันใช้ JDK 21, Maven 3.9.16 / 3.10.0 และ Gradle 8.14.3 / 9.8.2 ส่วน Maven 4.0.0-rc-7 เป็น preview เท่านั้น
เมื่อใช้ Gradle บน JDK 21 ต้องติดตั้ง JDK 17 สำหรับ compile ด้วย โดย CI เพิ่ม lane Java 17 และคง lane Java 21 ไว้

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
คำขอ Boot BOM ต้องเป็นเวอร์ชันเจาะจง ส่วน range, dynamic version, dependency substitution และ module ที่ถูกเลือกด้วย rule จะแสดง `UNKNOWN` และทำให้ strict mode ล้มเหลว แม้เวอร์ชันที่เลือกจะตรงกับ BOM
เมื่อไม่มีหลักฐานเพียงพอ ยังไม่รองรับ configuration-cache reuse และ Gradle 10 แต่ทดสอบแล้วว่าการขอ configuration cache ยังรันการตรวจและ strict policy โดย discard cache ที่ใช้ไม่ได้ CI ตั้งค่าไว้สำหรับ Ubuntu, macOS 15 และ Windows Server 2025 ตาม matrix ข้างต้น โดย Windows job ที่เพิ่มในรอบนี้ยังไม่ได้รัน
ห้าม rewrite metadata ของ Boot BOM หรือ BOM ที่ import หากต้องการ baseline ที่เชื่อถือได้ ส่วน local file dependencies บน configuration ที่ตรวจจะแสดง UNKNOWN
การ resolve อาจดาวน์โหลดข้อมูลผ่าน repository ที่ build tool ตั้งค่าไว้ ใช้ `--offline` ได้เมื่อมี cache ครบแล้ว

คำสั่งทดสอบอยู่ใน [Build and contribute](#build-and-contribute) และหลักฐานผลทดสอบอยู่ใน [VERIFICATION.md](VERIFICATION.md)
