pluginManagement {
    providers.gradleProperty("guardBuild").orNull?.let { includeBuild(it) }
}
rootProject.name = "guard-kotlin-fixture"
