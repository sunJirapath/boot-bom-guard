plugins { `java-gradle-plugin` }
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
