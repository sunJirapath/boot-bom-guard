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
    failOnDrift.set(true)
    exceptions.put("org.slf4j:slf4j-api", "Reviewed logging upgrade")
}
