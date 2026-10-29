# Real-world differential test campaign — boot-bom-guard

> Copy the entire prompt in the next section into a coding agent. Give it the 100-repository catalog below as its target list. This is a **test plan**, not a claim that integrations were executed.

## Agent prompt (copy/paste)

You are a senior Java build-tool integration tester and adversarial QA engineer. Your task is to find **reproducible bugs, false positives, false negatives, incorrect classification, crashes, incomplete-analysis mistakes, and scalability problems** in https://github.com/sunJirapath/boot-bom-guard by applying it to 100 real, public GitHub repositories (25 Small, 25 Medium, 25 Large, 25 Huge) listed below.

### Ground truth and boundaries

1. Read the guard's current README.md, DESIGN.md, VERIFICATION.md, core Guard.java, Maven CheckMojo.java, Gradle BootBomGuardTask.java/Plugin.java, and existing integration fixtures. Pin and record the exact guard commit SHA. Current catalog research used commit `763c38e05eef052ab7284ff77f7bd9e567da4708`; refresh if HEAD has moved.
2. The library is **0.1.0-SNAPSHOT**, not published. Its supported positive contract is Spring Boot **4.x**, JDK 21+ for running the guard, Maven **3.9.16+**, and tested Gradle **8.14.3 / 9.8.2**. For Maven, install guard artifacts from its checkout using `mvn -B -ntp install`. For Gradle, use the local composite build with `pluginManagement { includeBuild(...) }` as documented. Do not pretend a Plugin Portal release exists.
3. The Maven goal is `boot-bom-guard:check` (or the fully qualified goal), and the Gradle task is `bootBomGuard` per **applied JVM project**. Default policy is warnings; `failOnDrift` is opt-in. Gradle `-PfailOnDrift=true` has no effect unless the build explicitly binds that property to the extension.
4. The library compares **native selected dependency versions** to the **selected Spring Boot BOM baseline**. Difference is drift, not runtime incompatibility. Unsupported/missing/ambiguous/incomplete resolution must report `UNKNOWN`, not a false `PASS`. Exceptions need exact coordinates and nonblank reasons; they must never hide `UNKNOWN`.
5. Spring Boot 2/3, Gradle builds using only `io.spring.dependency-management` without a native Boot `platform(...)`, dependency substitutions, Gradle configuration cache/10, and non-app framework modules are **boundary/negative-control tests** unless the documented contract changes. Do not label expected unsupported behavior a product bug.

### Safety and isolation

- Clone/fetch only into isolated disposable directories/worktrees at pinned SHAs; never change or push to upstream repositories, open PRs, or touch user worktrees.
- Inspect build scripts before executing them; run untrusted builds in containers or isolated sandboxes with no production secrets, privileged Docker socket, deployment credentials, or unrestricted filesystem mounts. Maven/Gradle resolution may legitimately fetch metadata using configured repositories. Redact URLs/tokens from evidence.
- Record each original build's baseline before adding the guard. Preserve original dependency semantics as much as possible; never overwrite a project's BOM version merely to force the guard to pass.
- Limit changes to integration wiring and one controlled dependency mutation at a time. Save diffs, then revert the mutation before the next scenario. No speculative refactors or unrelated upgrades.
- For Boot 2/3 projects, first record the expected `UNKNOWN`. A migration experiment to Boot 4 is a **separate track**; do it only when the baseline and scope make the migration practical. Track migration failures separately from guard failures. For Large/Huge, prefer one representative Boot 4-ready leaf module instead of migrating a whole platform.
- Some listed repositories are collections of nested samples or frameworks rather than applications. Find a real Maven/Gradle JVM consumer module with a selected Boot 4 BOM; if none exists, classify it as unsupported/skip with evidence, not as a PASS or a bug. Reassign the **measured** tier if initial sizing is misleading, but preserve original list and quotas in the report.

### Execute in waves

- Pilot: 3–5 diverse candidates from **each tier** (prefer a mix of Maven, Gradle Groovy/Kotlin, Boot 4-native, and documented boundary cases). Record feasibility and fix the test harness, not the library.
- Scale to all 100 candidates. Each row must receive an outcome, including skipped or blocked. Never claim 100 successful integrations simply because 100 repos were listed.
- Per repo: identify commit, build root(s), modules/services, build tool/wrapper, JDK toolchain, Boot version, selected BOM mechanism and scope. Measure the actual size using **number of projects/modules, dependency graph breadth, and build complexity**; GitHub repository KB/stars are not sizing evidence.
- Run the **unmodified project baseline** first. Capture command, exit code, elapsed time, failure cause. When infrastructure is required (DB/Kafka/etc.), prefer dependency-resolution checks over application integration tests; don't start arbitrary services or deployment scripts.
- Integrate the locally built guard minimally. For Maven, configure its plugin in the selected module or inherited build correctly, and check reactor `-pl`/`-am` behavior. For Gradle, use `pluginManagement.includeBuild`, apply `io.github.bootbomguard` to the relevant subproject, and invoke e.g. `:service:bootBomGuard`. Confirm the inspected configurations are **resolvable** and actually contain a native Boot platform.
- Establish independent truth with Maven `help:effective-pom`, `dependency:tree`, and/or Gradle `dependencies`, `dependencyInsight`, resolutionResult. Record exact expected BOM-managed version and selected version. Never infer bugs from raw declared versions alone.
- Perform smallest useful mutations below. In every mutation run both warning mode (exit 0 for valid configuration) and strict mode (nonzero on unresolved/unaccepted drift) where applicable, and compare report evidence with the native resolver.
- Capture sanitizer-safe logs and minimal before/after diffs. Reset to original project state after each experiment.

### Mutation and oracle matrix

| Priority | Scenario | Expected result |
|---|---|---|
| P0 | Correctly selected Boot 4 BOM, fully aligned graph | `PASS`; only actually checked managed coordinates counted |
| P0 | Force an **actually BOM-managed** direct dependency to a different resolved version | `DRIFT` with correct expected/resolved; appropriate origin evidence; warning exit 0, strict nonzero |
| P0 | Existing real drift, no mutation | Correct report; no false `PASS` |
| P0 | Boot BOM missing, ambiguous, unsupported, or native dependency resolution incomplete | `UNKNOWN`, warning exit 0, strict nonzero; never quietly pass |
| P0 | Inject unresolved dependency or simulate missing cache safely | Clear `UNKNOWN` without leaking secrets/credentials |
| P1 | Maven effective dependencyManagement or Gradle root constraint overrides BOM | `MANAGED_OVERRIDE` only when evidence warrants it |
| P1 | Transitive dependency changes selected version | `TRANSITIVE_DRIFT` only when evidence warrants it, not a guessed cause |
| P1 | Exact-coordinate exception with reason | `ALLOWED` visibly reports drift, strict mode passes if no other violation; blank/duplicate exception is invalid |
| P1 | Maven inherited Boot parent, active profiles, import precedence, shadowed BOM, classifier/type | Correct selected BOM and exact coordinate comparison |
| P1 | Gradle `platform` vs `enforcedPlatform`, Kotlin/Groovy DSL, subproject task, compile/runtime/test classpaths | Respect native selection semantics, configuration boundaries and platform variants |
| P1 | Gradle force, selection rule, substitution, custom resolvable/unresolvable configurations | Honest `UNKNOWN_ORIGIN` or `UNKNOWN`; no misleading success |
| P1 | Duplicate paths and repeated execution with identical lockfiles | Deterministic, sorted and de-duplicated reports |
| P2 | Offline build with warmed cache, proxy/mirror, credentials in resolver errors | Same comparison policy, no secrets in guard diagnostics |
| P2/Huge | Large reactors and broad dependency graphs | Capture median of 3 run times, peak RSS if measurable, task/goal failure, OOM, hangs and scaling vs native resolver |

Use a **valid Boot-managed coordinate actually present in the target dependency graph** for each injected drift. Compute the alternate version from available metadata and prove native resolver selected it. Do not hardcode `slf4j-api:2.0.18` across arbitrary Boot 4.x versions.

### Bug attribution

A candidate becomes **CONFIRMED_LIB_BUG** only with all of:
1. A baseline that works or a narrowly isolated control showing the project/environment problem is irrelevant.
2. Native Maven/Gradle resolver evidence proving what should have been selected and compared.
3. A minimal guard integration/diff with exact command and exit code.
4. Reproduction at the pinned guard commit (twice if timing-related); ideally a minimized fixture in a disposable branch or patch file.

Classify others honestly: `PASS_EXPECTED`, `DRIFT_DETECTED_CORRECTLY`, `EXPECTED_UNSUPPORTED`, `MIGRATION_FAILURE`, `BASELINE_BROKEN`, `ENV_BLOCKED`, `SUSPECTED_LIB_BUG`, `NOT_RUN`. Distinguish false positives, false negatives, crashes, wrong BOM baseline, wrong classification, non-determinism, performance, and leaking sensitive data. Do not “fix” the product as part of this investigation without separate authorization.

### Deliverables

1. A machine-readable `results.csv` (100 rows, even for skipped repos) with: `tier_proposed,tier_measured,repo,sha,build_root,build_tool,module_count,boot_version,bom_mechanism,jdk,baseline_status,scenario,guard_warn_exit,guard_strict_exit,drift_count,unknown_count,elapsed_s,peak_rss_mb,outcome,issue_id,evidence_path`.
2. `summary.md`: counts by tier and build tool; numbers **attempted**, **Boot 4 eligible**, **fully exercised**, **skipped**, **baseline-broken**, **blocked**, **suspected/confirmed bugs**, and false-positive/negative rates only when sample denominators are justified. Show a capability matrix, not just a success percentage.
3. `bugs.md`: every confirmed bug with severity P0/P1/P2, root-cause hypothesis, minimal repro steps, original-vs-guard output, version matrix, regression test recommendation, and suspected source location. Rank confirmed defects before speculative ones.
4. A short list of the 10 most valuable next tests and the exact unresolved questions. Do not invent outcomes or claim you ran commands that were not actually executed.

The 100-repo candidate inventory starts below. Only GitHub existence and top-level file listings were checked during candidate selection. Current Boot version, native BOM usage, leaf-module eligibility and actual size **must be verified live** before each integration.

## Candidate inventory (100 repositories)

Catalog date: **2026-10-25**. All 100 repository URLs were confirmed by GitHub repository search or repository metadata and their top-level contents fetched successfully. Entries with `Nested build(s)` need a search for application projects inside directories. Tiers are **provisional hypotheses**; a large framework may correctly return `UNKNOWN` or lack a supported consumer and should be recorded as such.

### Small — Single app or focused sample; one easy target module (25)

| # | Repository | Root build entry | Hypothesis to probe |
|---:|---|---|---|
| 1 | [Genc/spring-boot-boilerplate](https://github.com/Genc/spring-boot-boilerplate) | Maven | aligned / direct override |
| 2 | [MossaabFrifita/spring-boot-4-security-7-jwt](https://github.com/MossaabFrifita/spring-boot-4-security-7-jwt) | Maven | security dependency mediation |
| 3 | [ywcheong/springboot4-demo](https://github.com/ywcheong/springboot4-demo) | Gradle Groovy | dependency-management DSL / native platform |
| 4 | [javatarz/todo-backend-kotlin-spring-boot-4](https://github.com/javatarz/todo-backend-kotlin-spring-boot-4) | Gradle Groovy | Kotlin DSL / JVM |
| 5 | [spring-guides/gs-spring-boot](https://github.com/spring-guides/gs-spring-boot) | Nested build(s) | nested fixtures / profile selection |
| 6 | [spring-guides/gs-testing-web](https://github.com/spring-guides/gs-testing-web) | Nested build(s) | test classpath |
| 7 | [spring-guides/gs-spring-boot-docker](https://github.com/spring-guides/gs-spring-boot-docker) | Nested build(s) | nested fixtures / profile selection |
| 8 | [snicoll/spring-boot-4tw-uni](https://github.com/snicoll/spring-boot-4tw-uni) | Maven | aligned / direct override |
| 9 | [sdeleuze/spring-boot-kotlin-demo](https://github.com/sdeleuze/spring-boot-kotlin-demo) | Gradle Kotlin | Kotlin DSL / JVM |
| 10 | [philipplackner/SpringBootCrashCourse](https://github.com/philipplackner/SpringBootCrashCourse) | Gradle Kotlin | aligned / direct override |
| 11 | [team-dodn/spring-boot-java-template](https://github.com/team-dodn/spring-boot-java-template) | Gradle Groovy | aligned / direct override |
| 12 | [team-dodn/spring-boot-kotlin-template](https://github.com/team-dodn/spring-boot-kotlin-template) | Gradle Kotlin | Kotlin DSL / JVM |
| 13 | [ali-bouali/spring-boot-3-jwt-security](https://github.com/ali-bouali/spring-boot-3-jwt-security) | Maven | Boot 3 negative control |
| 14 | [callicoder/kotlin-spring-boot-jpa-rest-api-demo](https://github.com/callicoder/kotlin-spring-boot-jpa-rest-api-demo) | Maven | Kotlin DSL / JVM |
| 15 | [davidkiss/spring-boot-quartz-demo](https://github.com/davidkiss/spring-boot-quartz-demo) | Maven | aligned / direct override |
| 16 | [givanthak/spring-boot-rest-api-tutorial](https://github.com/givanthak/spring-boot-rest-api-tutorial) | Maven | aligned / direct override |
| 17 | [piomin/sample-spring-modulith](https://github.com/piomin/sample-spring-modulith) | Maven | BOM provenance / non-app boundary |
| 18 | [piomin/sample-spring-reactive](https://github.com/piomin/sample-spring-reactive) | Maven | aligned / direct override |
| 19 | [piomin/sample-spring-redis](https://github.com/piomin/sample-spring-redis) | Maven | transitive dependencies |
| 20 | [piomin/sample-spring-kafka-transactions](https://github.com/piomin/sample-spring-kafka-transactions) | Maven | transitive dependencies |
| 21 | [murraco/spring-boot-jwt](https://github.com/murraco/spring-boot-jwt) | Maven | security dependency mediation |
| 22 | [joshiste/spring-boot-admin-samples](https://github.com/joshiste/spring-boot-admin-samples) | Nested build(s) | aggregator / BOM conflicts |
| 23 | [Romeh/spring-boot-sample-app](https://github.com/Romeh/spring-boot-sample-app) | Maven | aligned / direct override |
| 24 | [bzdgn/spring-boot-restful-web-service-example](https://github.com/bzdgn/spring-boot-restful-web-service-example) | Maven | aligned / direct override |
| 25 | [mechero/spring-boot-testing-strategies](https://github.com/mechero/spring-boot-testing-strategies) | Maven | test classpath |

### Medium — App with database, security, several configurations or integration tests (25)

| # | Repository | Root build entry | Hypothesis to probe |
|---:|---|---|---|
| 26 | [spring-projects/spring-petclinic](https://github.com/spring-projects/spring-petclinic) | Maven + Gradle | JPA / test scopes / Boot parent |
| 27 | [spring-petclinic/spring-petclinic-rest](https://github.com/spring-petclinic/spring-petclinic-rest) | Maven | JPA / test scopes / Boot parent |
| 28 | [spring-petclinic/spring-petclinic-data-jdbc](https://github.com/spring-petclinic/spring-petclinic-data-jdbc) | Maven | JPA / test scopes / Boot parent |
| 29 | [spring-petclinic/spring-petclinic-reactive](https://github.com/spring-petclinic/spring-petclinic-reactive) | Maven | JPA / test scopes / Boot parent |
| 30 | [spring-petclinic/spring-petclinic-modulith](https://github.com/spring-petclinic/spring-petclinic-modulith) | Maven + Gradle | JPA / test scopes / Boot parent |
| 31 | [spring-petclinic/spring-petclinic-ai](https://github.com/spring-petclinic/spring-petclinic-ai) | Maven + Gradle | JPA / test scopes / Boot parent |
| 32 | [gothinkster/spring-boot-realworld-example-app](https://github.com/gothinkster/spring-boot-realworld-example-app) | Gradle Groovy | managed / transitive drift |
| 33 | [springframeworkguru/springbootwebapp](https://github.com/springframeworkguru/springbootwebapp) | Maven | managed / transitive drift |
| 34 | [ThomasVitale/cloud-native-spring-in-action](https://github.com/ThomasVitale/cloud-native-spring-in-action) | Nested build(s) | managed / transitive drift |
| 35 | [ThomasVitale/spring-boot-multitenancy](https://github.com/ThomasVitale/spring-boot-multitenancy) | Nested build(s) | managed / transitive drift |
| 36 | [ThomasVitale/llm-apps-java-spring-ai](https://github.com/ThomasVitale/llm-apps-java-spring-ai) | Gradle (nested build) | managed / transitive drift |
| 37 | [callicoder/spring-boot-react-oauth2-social-login-demo](https://github.com/callicoder/spring-boot-react-oauth2-social-login-demo) | Nested build(s) | security dependency mediation |
| 38 | [callicoder/spring-security-react-ant-design-polls-app](https://github.com/callicoder/spring-security-react-ant-design-polls-app) | Nested build(s) | security dependency mediation |
| 39 | [naturalprogrammer/spring-lemon](https://github.com/naturalprogrammer/spring-lemon) | Maven | managed / transitive drift |
| 40 | [spring-guides/tut-spring-boot-kotlin](https://github.com/spring-guides/tut-spring-boot-kotlin) | Maven + Gradle | Kotlin DSL / JVM |
| 41 | [jkazama/ddd-java](https://github.com/jkazama/ddd-java) | Gradle Groovy | managed / transitive drift |
| 42 | [jkazama/sample-boot-jpa](https://github.com/jkazama/sample-boot-jpa) | Gradle Groovy | managed / transitive drift |
| 43 | [piomin/sample-spring-boot-graphql](https://github.com/piomin/sample-spring-boot-graphql) | Maven | managed / transitive drift |
| 44 | [piomin/sample-spring-kafka-microservices](https://github.com/piomin/sample-spring-kafka-microservices) | Maven | multi-module / transitive graph |
| 45 | [in28minutes/full-stack-with-angular-and-spring-boot](https://github.com/in28minutes/full-stack-with-angular-and-spring-boot) | Nested build(s) | managed / transitive drift |
| 46 | [xpinjection/test-driven-spring-boot](https://github.com/xpinjection/test-driven-spring-boot) | Maven | test classpath |
| 47 | [hamvocke/spring-testing](https://github.com/hamvocke/spring-testing) | Gradle Groovy | test classpath |
| 48 | [ivangfr/springboot-keycloak-mongodb-testcontainers](https://github.com/ivangfr/springboot-keycloak-mongodb-testcontainers) | Maven | test classpath |
| 49 | [istonikula/realworld-api](https://github.com/istonikula/realworld-api) | Gradle Kotlin | managed / transitive drift |
| 50 | [hantsy/spring-microservice-sample](https://github.com/hantsy/spring-microservice-sample) | Maven | multi-module / transitive graph |

### Large — Many modules/services or a collection of substantial projects (25)

| # | Repository | Root build entry | Hypothesis to probe |
|---:|---|---|---|
| 51 | [spring-petclinic/spring-petclinic-microservices](https://github.com/spring-petclinic/spring-petclinic-microservices) | Maven | multi-service and profiles |
| 52 | [spring-petclinic/spring-petclinic-cloud](https://github.com/spring-petclinic/spring-petclinic-cloud) | Maven | multi-service and profiles |
| 53 | [eazybytes/microservices](https://github.com/eazybytes/microservices) | Nested build(s) | multi-module / transitive graph |
| 54 | [rohitghatol/spring-boot-microservices](https://github.com/rohitghatol/spring-boot-microservices) | Nested build(s) | multi-module / transitive graph |
| 55 | [piomin/sample-spring-microservices-kubernetes](https://github.com/piomin/sample-spring-microservices-kubernetes) | Maven | multi-module / transitive graph |
| 56 | [piomin/sample-spring-microservices-new](https://github.com/piomin/sample-spring-microservices-new) | Maven | multi-module / transitive graph |
| 57 | [yudaocode/SpringBoot-Labs](https://github.com/yudaocode/SpringBoot-Labs) | Maven | multi-module / profiles |
| 58 | [dyc87112/SpringBoot-Learning](https://github.com/dyc87112/SpringBoot-Learning) | Maven | multi-module / profiles |
| 59 | [xkcoding/spring-boot-demo](https://github.com/xkcoding/spring-boot-demo) | Maven | nested fixtures / profile selection |
| 60 | [heibaiying/spring-samples-for-all](https://github.com/heibaiying/spring-samples-for-all) | Nested build(s) | nested fixtures / profile selection |
| 61 | [sivaprasadreddy/spring-boot-microservices-course](https://github.com/sivaprasadreddy/spring-boot-microservices-course) | Maven | multi-module / transitive graph |
| 62 | [eventuate-tram/eventuate-tram-examples-customers-and-orders](https://github.com/eventuate-tram/eventuate-tram-examples-customers-and-orders) | Gradle Groovy | multi-module / profiles |
| 63 | [eventuate-tram/eventuate-tram-sagas-examples-customers-and-orders](https://github.com/eventuate-tram/eventuate-tram-sagas-examples-customers-and-orders) | Gradle Groovy | multi-module / profiles |
| 64 | [meysamhadeli/booking-microservices-java-spring-boot](https://github.com/meysamhadeli/booking-microservices-java-spring-boot) | Nested build(s) | multi-module / transitive graph |
| 65 | [SelimHorri/ecommerce-microservice-backend-app](https://github.com/SelimHorri/ecommerce-microservice-backend-app) | Maven | multi-module / transitive graph |
| 66 | [oktadev/java-microservices-examples](https://github.com/oktadev/java-microservices-examples) | Nested build(s) | multi-module / transitive graph |
| 67 | [piomin/sample-spring-microservices-advanced](https://github.com/piomin/sample-spring-microservices-advanced) | Maven | multi-module / transitive graph |
| 68 | [apache/camel-spring-boot-examples](https://github.com/apache/camel-spring-boot-examples) | Maven | BOM provenance / non-app boundary |
| 69 | [safa-yesilyurt/spring-boot-microservices](https://github.com/safa-yesilyurt/spring-boot-microservices) | Nested build(s) | multi-module / transitive graph |
| 70 | [rajadilipkolli/spring-boot-microservices-series-v2](https://github.com/rajadilipkolli/spring-boot-microservices-series-v2) | Maven | multi-module / transitive graph |
| 71 | [hoangtien2k3/ecommerce-microservices](https://github.com/hoangtien2k3/ecommerce-microservices) | Maven | multi-module / transitive graph |
| 72 | [AndriyKalashnykov/spring-microservices-k8s](https://github.com/AndriyKalashnykov/spring-microservices-k8s) | Maven | multi-module / transitive graph |
| 73 | [geekidea/spring-boot-plus](https://github.com/geekidea/spring-boot-plus) | Maven | multi-module / profiles |
| 74 | [RameshMF/springboot-microservices](https://github.com/RameshMF/springboot-microservices) | Nested build(s) | multi-module / transitive graph |
| 75 | [in28minutes/spring-microservices](https://github.com/in28minutes/spring-microservices) | Nested build(s) | multi-module / transitive graph |

### Huge — Broad ecosystem framework, enterprise monorepo or complex multi-module reactor (25)

| # | Repository | Root build entry | Hypothesis to probe |
|---:|---|---|---|
| 76 | [apache/camel-spring-boot](https://github.com/apache/camel-spring-boot) | Maven | BOM provenance / non-app boundary |
| 77 | [codecentric/spring-boot-admin](https://github.com/codecentric/spring-boot-admin) | Maven | aggregator / BOM conflicts |
| 78 | [spring-cloud/spring-cloud-gateway](https://github.com/spring-cloud/spring-cloud-gateway) | Maven | BOM provenance / non-app boundary |
| 79 | [spring-cloud/spring-cloud-stream](https://github.com/spring-cloud/spring-cloud-stream) | Maven | BOM provenance / non-app boundary |
| 80 | [spring-cloud/spring-cloud-kubernetes](https://github.com/spring-cloud/spring-cloud-kubernetes) | Maven | BOM provenance / non-app boundary |
| 81 | [spring-cloud/spring-cloud-config](https://github.com/spring-cloud/spring-cloud-config) | Maven | BOM provenance / non-app boundary |
| 82 | [spring-cloud/spring-cloud-netflix](https://github.com/spring-cloud/spring-cloud-netflix) | Maven | BOM provenance / non-app boundary |
| 83 | [alibaba/spring-cloud-alibaba](https://github.com/alibaba/spring-cloud-alibaba) | Maven | BOM provenance / non-app boundary |
| 84 | [Tencent/spring-cloud-tencent](https://github.com/Tencent/spring-cloud-tencent) | Maven | BOM provenance / non-app boundary |
| 85 | [apolloconfig/apollo](https://github.com/apolloconfig/apollo) | Maven | scale / reactor / memory |
| 86 | [geoserver/geoserver-cloud](https://github.com/geoserver/geoserver-cloud) | Maven | scale / reactor / memory |
| 87 | [pig-mesh/pig](https://github.com/pig-mesh/pig) | Maven | scale / reactor / memory |
| 88 | [zlt2000/microservices-platform](https://github.com/zlt2000/microservices-platform) | Maven | multi-module / transitive graph |
| 89 | [nashtech-garage/yas](https://github.com/nashtech-garage/yas) | Maven | scale / reactor / memory |
| 90 | [wxiaoqi/Spring-Cloud-Platform](https://github.com/wxiaoqi/Spring-Cloud-Platform) | Maven | BOM provenance / non-app boundary |
| 91 | [spring-projects/spring-modulith](https://github.com/spring-projects/spring-modulith) | Maven | BOM provenance / non-app boundary |
| 92 | [Netflix/genie](https://github.com/Netflix/genie) | Gradle Groovy | scale / reactor / memory |
| 93 | [Activiti/Activiti](https://github.com/Activiti/Activiti) | Maven | scale / reactor / memory |
| 94 | [vaadin/hilla](https://github.com/vaadin/hilla) | Maven | scale / reactor / memory |
| 95 | [langchain4j/langchain4j](https://github.com/langchain4j/langchain4j) | Maven | BOM provenance / non-app boundary |
| 96 | [newbee-ltd/newbee-mall](https://github.com/newbee-ltd/newbee-mall) | Maven | scale / reactor / memory |
| 97 | [merikbest/OnlineShop](https://github.com/merikbest/OnlineShop) | Maven | scale / reactor / memory |
| 98 | [KouShenhai/KCloud-Platform-IoT](https://github.com/KouShenhai/KCloud-Platform-IoT) | Maven | aggregator / BOM conflicts |
| 99 | [weiguangli-io/rydr](https://github.com/weiguangli-io/rydr) | Nested build(s) | scale / reactor / memory |
| 100 | [spring-cloud/spring-cloud-commons](https://github.com/spring-cloud/spring-cloud-commons) | Maven | BOM provenance / non-app boundary |


## Pilot hints with inspected build declarations

- [spring-projects/spring-petclinic](https://github.com/spring-projects/spring-petclinic): Maven parent **Spring Boot 4.1.0**; both Maven and Gradle root files present.
- [spring-petclinic/spring-petclinic-rest](https://github.com/spring-petclinic/spring-petclinic-rest): Maven parent **Spring Boot 4.1.1**.
- [spring-petclinic/spring-petclinic-microservices](https://github.com/spring-petclinic/spring-petclinic-microservices): Maven parent **Spring Boot 4.0.1**.
- [codecentric/spring-boot-admin](https://github.com/codecentric/spring-boot-admin): root Maven property `spring-boot.version=4.1.1`; many reactor modules, inspect each leaf's effective BOM.
- [MossaabFrifita/spring-boot-4-security-7-jwt](https://github.com/MossaabFrifita/spring-boot-4-security-7-jwt): Maven parent **Spring Boot 4.0.1**.
- [Genc/spring-boot-boilerplate](https://github.com/Genc/spring-boot-boilerplate): Maven parent **Spring Boot 4.1.2** but Java toolchain **25**; do not call a JDK-21 mismatch a guard bug.
- [ywcheong/springboot4-demo](https://github.com/ywcheong/springboot4-demo): Gradle applies Spring Boot **4.0.0** and `io.spring.dependency-management`, but no native Boot `platform(...)` in the root dependencies. Expect the documented unsupported/missing-BOM behavior **unless** a separate native-platform experiment is explicitly conducted and labelled.

The plugin's own [README](https://github.com/sunJirapath/boot-bom-guard/blob/main/README.md), [design](https://github.com/sunJirapath/boot-bom-guard/blob/main/DESIGN.md), and [verification matrix](https://github.com/sunJirapath/boot-bom-guard/blob/main/VERIFICATION.md) define the asserted product contract, not evidence that this external 100-repo campaign has been run.
