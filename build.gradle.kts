subprojects {
    group = "io.github.sunjirapath.bootbomguard"
    version = "0.1.1-SNAPSHOT"
    repositories { mavenCentral() }
    apply(plugin = "java-library")
    extensions.configure<JavaPluginExtension> {
        toolchain.languageVersion.set(JavaLanguageVersion.of(17))
    }
    tasks.withType<JavaCompile>().configureEach { options.release.set(17) }
    dependencies {
        "testImplementation"("org.junit.jupiter:junit-jupiter:5.12.2")
        "testRuntimeOnly"("org.junit.platform:junit-platform-launcher:1.12.2")
    }
    tasks.withType<Test>().configureEach {
        useJUnitPlatform()
        javaLauncher.set(project.extensions.getByType<JavaToolchainService>().launcherFor {
            languageVersion.set(JavaLanguageVersion.of(JavaVersion.current().majorVersion))
        })
    }
}
