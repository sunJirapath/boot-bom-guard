# Design and research decisions

The main agent owned contracts, both adapters and integration. Three bounded `gpt-6-luna` agents researched Maven, researched Gradle, and independently reviewed correctness. They made no concurrent edits to core. No custom agent framework was added.

## Shared contract

Core accepts exact expected versions and selected resolved coordinates, with adapter-produced evidence. It performs equality comparison, applies exact-coordinate exceptions, and formats sorted diagnostics. It has no build-tool imports. Version ordering, mediation, platform semantics and model interpolation belong to adapters/native APIs.

Core uses a per-comparison hash index for exact expected-version lookup and deduplicates resolved entries before counting managed coordinates. Only drift findings are sorted, using the existing coordinate/version/evidence/origin order. Coordinate validation reuses a compiled pattern. Report escaping scans UTF-16 once, allocates only when escaping is needed, and renders control codes directly. [PERFORMANCE.md](PERFORMANCE.md) records bounded measurements; native resolution is outside those timings.

Scope includes three build modules, plugin entry points/configuration, core tests, real Maven/Gradle fixtures, TestKit tests, the Maven integration script, wrapper and documentation. No existing repository/data was overwritten.

## Maven

Use the built `MavenProject` for effective dependency management and its `InputLocation` source model IDs for selected Boot BOM provenance. Rebuild the resolved pristine BOM with `ProjectBuilder`, clearing consumer properties/profiles. Use `ProjectDependenciesResolver` for the actual graph and omit verbose conflict losers. Traverse breadth-first with an explicit queue to avoid adapter stack growth and preserve shortest direct paths for shared nodes. Preserve native type/classifier distinctions through the artifact type registry. Raw parent/import/profile scanning would reimplement model merging and mistake shadowed imports for selected BOMs.

For selected comparable snapshot coordinates, resolve the pristine BOM version and effective managed version with the existing Resolver session before equality comparison and origin classification. Preserve the artifact type/classifier and explicit timestamps; stripping timestamps would hide older pinned snapshots. Unresolvable expected snapshots retain the existing sanitized incomplete-analysis behavior.

Primary references:

- [MavenProject API](https://maven.apache.org/ref/3.9.0/apidocs/org/apache/maven/project/MavenProject.html)
- [InputLocation API](https://maven.apache.org/ref/3.9.0/maven-model/apidocs/org/apache/maven/model/InputLocation.html)
- [ProjectBuilder API](https://maven.apache.org/components/3.9.15/apidocs/org/apache/maven/project/ProjectBuilder.html)
- [Native dependency graph and conflict resolution](https://maven.apache.org/resolver/dependency-graph.html)
- [Plugin prefix mapping](https://maven.apache.org/guides/introduction/introduction-to-plugin-prefix-mapping.html)

## Gradle

Use selected component identifiers and resolved variant categories for Boot platform identity. Preserve requested versions separately from the selected version. Obtain baseline versions by native resolution with only the selected platform and non-transitive versionless library requests. Constraints alone do not select all modules. Source configuration rules/forces/constraints are not copied. The detached configuration still shares project/settings-wide component metadata rules; rewriting Boot/imported BOM metadata is outside the pristine-baseline contract. Missing root/imported platforms and fully erased constraints are incomplete analysis. Index incoming edges/component membership once rather than scanning every edge for each library. Use exact native preferred versions when required/strict versions are absent; dynamic/range constraints remain unsupported. File dependencies on the selected configuration are incomplete analysis because they lack comparable module coordinates. Read the real source graph for selected versions and evidence; do not infer a specific constraint's origin from `isConstrained` or `isForced`.

Primary references:

- [Gradle platforms and enforced platforms](https://docs.gradle.org/current/userguide/platforms.html)
- [ResolutionResult](https://docs.gradle.org/current/javadoc/org/gradle/api/artifacts/result/ResolutionResult.html)
- [ComponentSelectionReason](https://docs.gradle.org/current/javadoc/org/gradle/api/artifacts/result/ComponentSelectionReason.html)
- [ConfigurationContainer / detachedConfiguration](https://docs.gradle.org/current/javadoc/org/gradle/api/artifacts/ConfigurationContainer.html)
- [Task configuration avoidance](https://docs.gradle.org/current/userguide/task_configuration_avoidance.html)
- [Spring Boot 4 build-tool requirements](https://docs.spring.io/spring-boot/4.0/system-requirements.html)

## Review fixes

- Effective Maven provenance replaced raw declaration scanning; the profile override fixture verifies the native winner.
- Gradle requested BOM versions and selected BOM versions are reported separately; resolved version conflict is not automatically ambiguity.
- Missing/unresolved/unsupported analysis stays unknown and fails optional CI policy.
- Maven verbose conflict losers are excluded from actual resolved dependencies.
- Gradle substitutions cannot silently remove a managed module from comparison.
- Allowlist reasons are mandatory and control characters are escaped in reports.
