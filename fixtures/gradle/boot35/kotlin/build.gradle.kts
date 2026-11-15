plugins {
    java
    id("io.github.sunjirapath.bootbomguard")
}
repositories { mavenCentral() }
val scenario = providers.gradleProperty("scenario").getOrElse("aligned")
val boot = "org.springframework.boot:spring-boot-dependencies:3.5.16"
dependencies {
    if (scenario == "range") {
        implementation(platform("org.springframework.boot:spring-boot-dependencies:[3.5.16,3.5.16]"))
    } else {
        implementation(if (scenario == "enforced") enforcedPlatform(boot) else platform(boot))
    }
    if (scenario == "ambiguous") {
        implementation(platform(boot)) { (this as ExternalModuleDependency).version { strictly("3.5.16-conflict") } }
    }
    if (scenario in listOf("direct", "strict", "allowlist")) {
        implementation("org.slf4j:slf4j-api") { version { strictly("2.0.0") } }
    } else if (scenario == "enforced") {
        implementation("org.slf4j:slf4j-api:2.0.0")
    } else {
        implementation("org.slf4j:slf4j-api")
    }
    if (scenario == "framework-jakarta") {
        implementation("org.springframework:spring-core")
        implementation("jakarta.servlet:jakarta.servlet-api")
    }
}
if (scenario == "selection-rule") {
    configurations.configureEach {
        resolutionStrategy.eachDependency {
            if (requested.group == "org.slf4j" && requested.name == "slf4j-api") useVersion("2.0.0")
        }
    }
}
bootBomGuard {
    configurations.set(listOf("runtimeClasspath"))
    failOnDrift.set(providers.gradleProperty("failOnDrift").map { it.toBoolean() }.getOrElse(false))
    if (scenario == "allowlist") exceptions.put("org.slf4j:slf4j-api", "Reviewed fixture downgrade")
    if (scenario == "stale-exception") exceptions.put("guard.fixture:deleted", "Old exemption")
}
