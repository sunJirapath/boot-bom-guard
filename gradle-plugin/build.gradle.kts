plugins { `java-gradle-plugin` }
java { toolchain.languageVersion.set(JavaLanguageVersion.of(17)) }
tasks.withType<JavaCompile>().configureEach { options.release.set(17) }
dependencies { implementation(project(":core")) }
gradlePlugin {
    plugins {
        create("bootBomGuard") {
            id = "io.github.sunjirapath.bootbomguard"
            implementationClass = "io.github.bootbomguard.gradle.BootBomGuardPlugin"
            displayName = "Boot BOM Guard"
            description = "Reports resolved dependency drift from a selected Spring Boot BOM"
        }
    }
}
tasks.test {
    systemProperty("fixtures", rootProject.file("fixtures/gradle").absolutePath)
    systemProperty("guard.test.offline", providers.gradleProperty("testOffline").getOrElse("false"))
}
