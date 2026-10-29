package io.github.bootbomguard.gradle;

import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class BootBomGuardIntegrationTest {
    @TempDir Path directory;

    private String run(String dsl, String scenario, boolean failure, String... extra) throws IOException {
        Path fixture = Path.of(System.getProperty("fixtures"), dsl);
        Path project = scenario.equals("multi-project") ? Files.createDirectories(directory.resolve("app")) : directory;
        try (var files = Files.list(fixture)) {
            for (Path file : files.filter(Files::isRegularFile).toList()) {
                Path target = file.getFileName().toString().startsWith("build.gradle") ? project : directory;
                Files.copy(file, target.resolve(file.getFileName()), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            }
        }
        if (scenario.equals("multi-project")) {
            Files.writeString(directory.resolve("settings.gradle"), "\ninclude 'app'\n", java.nio.file.StandardOpenOption.APPEND);
        }
        if (scenario.equals("composite-baseline")) {
            Path included = Files.createDirectories(directory.resolve("local-platform"));
            Files.writeString(included.resolve("settings.gradle"), "rootProject.name = 'spring-boot-dependencies'\n");
            Files.writeString(included.resolve("build.gradle"), "plugins { id 'java-platform' }\ngroup = 'org.springframework.boot'\nversion = '4.0.0'\n");
            Files.writeString(directory.resolve("settings.gradle"), "\nincludeBuild 'local-platform'\n", java.nio.file.StandardOpenOption.APPEND);
        }
        if (scenario.equals("project-substitution") || scenario.equals("transitive-platform")) {
            String name = scenario.equals("project-substitution") ? "replacement" : "local-platform";
            Path child = Files.createDirectories(directory.resolve(name));
            Files.writeString(directory.resolve("settings.gradle"), "\ninclude '" + name + "'\n", java.nio.file.StandardOpenOption.APPEND);
            Files.writeString(child.resolve("build.gradle"), scenario.equals("project-substitution")
                    ? "plugins { id 'java-library' }\ngroup = 'org.slf4j'\nversion = '2.0.18'\n"
                    : "plugins { id 'java-platform' }\nrepositories { mavenCentral() }\njavaPlatform { allowDependencies() }\ndependencies { api platform('org.springframework.boot:spring-boot-dependencies:4.0.0') }\n");
        }
        if (scenario.equals("rich-reject") || scenario.equals("bounded-range")) {
            Path module = directory.resolve("range-repository/org/slf4j/slf4j-api");
            for (String version : List.of("2.0.17", "2.0.18")) {
                Path release = Files.createDirectories(module.resolve(version));
                Files.writeString(release.resolve("slf4j-api-" + version + ".pom"),
                        "<project><modelVersion>4.0.0</modelVersion><groupId>org.slf4j</groupId><artifactId>slf4j-api</artifactId><version>" + version + "</version></project>");
                try (var jar = new java.util.zip.ZipOutputStream(Files.newOutputStream(release.resolve("slf4j-api-" + version + ".jar")))) {
                    jar.finish();
                }
            }
            Files.writeString(module.resolve("maven-metadata.xml"),
                    "<metadata><groupId>org.slf4j</groupId><artifactId>slf4j-api</artifactId><versioning><latest>2.0.18</latest><release>2.0.18</release><versions><version>2.0.17</version><version>2.0.18</version></versions><lastUpdated>20261025010203</lastUpdated></versioning></metadata>");
            Files.writeString(project.resolve("build.gradle"), "\nrepositories { exclusiveContent { forRepository { maven { url = uri('range-repository') } }; filter { includeModule('org.slf4j', 'slf4j-api') } } }\n",
                    java.nio.file.StandardOpenOption.APPEND);
        }
        if (scenario.equals("missing-imported-baseline")) {
            String bom = "<project><!-- do_not_remove: published-with-gradle-metadata --><modelVersion>4.0.0</modelVersion><groupId>org.springframework.boot</groupId><artifactId>spring-boot-dependencies</artifactId><version>4.0.0-audit</version><packaging>pom</packaging></project>";
            String metadata = """
                    {"formatVersion":"1.1","component":{"group":"org.springframework.boot","module":"spring-boot-dependencies","version":"4.0.0-audit"},
                    "variants":[
                      {"name":"apiElements","attributes":{"org.gradle.category":"platform","org.gradle.usage":"java-api"},
                       "dependencies":[{"group":"guard.fixture","module":"nested-bom","version":{"requires":"1"},"attributes":{"org.gradle.category":"platform"},"endorseStrictVersions":true}]},
                      {"name":"runtimeElements","attributes":{"org.gradle.category":"platform","org.gradle.usage":"java-runtime"},
                       "dependencies":[{"group":"guard.fixture","module":"nested-bom","version":{"requires":"1"},"attributes":{"org.gradle.category":"platform"},"endorseStrictVersions":true}]}]}
                    """;
            for (String repository : List.of("full-baseline", "partial-baseline")) {
                Path folder = Files.createDirectories(directory.resolve(repository + "/org/springframework/boot/spring-boot-dependencies/4.0.0-audit"));
                Files.writeString(folder.resolve("spring-boot-dependencies-4.0.0-audit.pom"), bom);
                Files.writeString(folder.resolve("spring-boot-dependencies-4.0.0-audit.module"), metadata);
            }
            Path nested = Files.createDirectories(directory.resolve("full-baseline/guard/fixture/nested-bom/1"));
            Files.writeString(nested.resolve("nested-bom-1.pom"),
                    "<project><modelVersion>4.0.0</modelVersion><groupId>guard.fixture</groupId><artifactId>nested-bom</artifactId><version>1</version><packaging>pom</packaging><dependencyManagement><dependencies><dependency><groupId>org.slf4j</groupId><artifactId>slf4j-api</artifactId><version>2.0.17</version></dependency></dependencies></dependencyManagement></project>");
            Files.writeString(project.resolve("build.gradle"), "\nrepositories { maven { url = uri('full-baseline') } }\n",
                    java.nio.file.StandardOpenOption.APPEND);
        }
        List<String> arguments = new ArrayList<>(List.of(scenario.equals("lazy") ? "help" : "bootBomGuard", "--console=plain", "--stacktrace", "-Pscenario=" + scenario));
        if (Boolean.getBoolean("guard.test.offline")) arguments.add("--offline");
        arguments.addAll(List.of(extra));
        GradleRunner runner = GradleRunner.create().withProjectDir(directory.toFile()).withPluginClasspath().withArguments(arguments);
        BuildResult result = failure ? runner.buildAndFail() : runner.build();
        return result.getOutput();
    }

    @Test void aligned() throws Exception {
        String out = run("groovy", "aligned", false);
        assertTrue(out.contains("PASS checked=1 drift=0 unknown=0"), out);
        assertTrue(out.contains("mode=[platform]"), out);
    }
    @Test void explicitOverrideWarns() throws Exception {
        String out = run("groovy", "direct", false);
        assertTrue(out.contains("expected=2.0.17 resolved=2.0.18 classification=DIRECT_OVERRIDE"), out);
        assertTrue(out.contains("WARN checked=1 drift=1 unknown=0"), out);
    }
    @Test void managedOverride() throws Exception {
        String out = run("groovy", "managed", false);
        assertTrue(out.contains("expected=2.0.17 resolved=2.0.18 classification=MANAGED_OVERRIDE"), out);
    }
    @Test void transitiveDrift() throws Exception {
        String out = run("groovy", "transitive", false);
        assertTrue(out.contains("org.slf4j:slf4j-api expected=2.0.17 resolved=2.0.18 classification=TRANSITIVE_DRIFT"), out);
    }
    @Test void exceptionWithReasonPassesCi() throws Exception {
        String out = run("groovy", "allowlist", false, "-PfailOnDrift=true");
        assertTrue(out.contains("ALLOWED org.slf4j:slf4j-api"), out);
        assertTrue(out.contains("reason=Reviewed logging upgrade"), out);
        assertTrue(out.contains("PASS checked=1 drift=1 unknown=0"), out);
    }
    @Test void missingBomWarnsAndFailsCi() throws Exception {
        assertTrue(run("groovy", "missing", false).contains("Missing Spring Boot BOM"));
        assertTrue(run("groovy", "missing", true, "-PfailOnDrift=true").contains("policy failed"));
    }
    @Test void conflictingPlatformVariantsExplainAmbiguity() throws Exception {
        String out = run("groovy", "ambiguous", false);
        assertTrue(out.contains("UNKNOWN Unresolved/ambiguous Spring Boot BOM selection"), out);
    }
    @Test void nativeSelectionChoosesOneBomFromDifferentRequests() throws Exception {
        String out = run("groovy", "multiple-boms", false, "-PfailOnDrift=true");
        assertTrue(out.contains("BOM=org.springframework.boot:spring-boot-dependencies:4.0.1 mode=[enforced-platform, platform]"), out);
        assertTrue(out.contains("PASS checked=1 drift=0 unknown=0"), out);
    }
    @Test void ciFailure() throws Exception {
        assertTrue(run("groovy", "direct", true, "-PfailOnDrift=true").contains("policy failed"));
    }
    @Test void enforcedPlatformIsNotARegularPlatform() throws Exception {
        String out = run("groovy", "enforced", false, "-PfailOnDrift=true");
        assertTrue(out.contains("mode=[enforced-platform]"), out);
        assertTrue(out.contains("PASS checked=1 drift=0 unknown=0"), out);
    }
    @Test void forceOriginIsUnknown() throws Exception {
        String out = run("groovy", "forced", false);
        assertTrue(out.contains("classification=UNKNOWN_ORIGIN"), out);
        assertTrue(out.contains("forced=true"), out);
    }
    @Test void blankExceptionReasonIsRejected() throws Exception {
        assertTrue(run("groovy", "invalid-exception", true).contains("Invalid bootBomGuard exceptions"));
    }
    @Test void kotlinDsl() throws Exception {
        assertTrue(run("kotlin", "allowlist", false).contains("PASS checked=1 drift=1 unknown=0"));
    }
    @Test void importedBomConstraintsParticipateInBaseline() throws Exception {
        String out = run("groovy", "imported-bom", false, "-PfailOnDrift=true");
        assertTrue(out.contains("PASS checked=4 drift=0 unknown=0"), out);
    }
    @Test void unmanagedModulesAreNotTreatedAsBrokenBaselineRequests() throws Exception {
        String out = run("groovy", "unmanaged", false, "-PfailOnDrift=true");
        assertTrue(out.contains("PASS"), out);
        assertFalse(out.contains("UNKNOWN"), out);
    }
    @Test void moduleSubstitutionCannotSilentlySkipComparison() throws Exception {
        String out = run("groovy", "substitution", true, "-PfailOnDrift=true");
        assertTrue(out.contains("UNKNOWN Unsupported dependency substitution"), out);
    }
    @Test void importedBomBaselineDoesNotAbsorbOverride() throws Exception {
        String out = run("groovy", "imported-override", false);
        assertTrue(out.contains("org.springframework:spring-core expected=7.0.1 resolved=7.0.2"), out);
    }
    @Test void helpDoesNotResolveDependencyGraphs() throws Exception {
        String out = run("groovy", "lazy", false);
        assertFalse(out.contains("boot-bom-guard BOM="), out);
    }

    @Test void unresolvedDependenciesWarnAndFailCi() throws Exception {
        String warning = run("groovy", "unresolved", false);
        assertTrue(warning.contains("UNKNOWN Unresolved Gradle dependencies; analysis is incomplete."), warning);
        assertTrue(warning.contains("WARN checked=1 drift=0 unknown=1"), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        String failure = run("groovy", "unresolved", true, "-PfailOnDrift=true");
        assertTrue(failure.contains("UNKNOWN Unresolved Gradle dependencies"), failure);
        assertTrue(failure.contains("policy failed"), failure);
    }

    @ParameterizedTest
    @ValueSource(strings = {"missing-configuration", "non-resolvable"})
    void unavailableConfigurationsWarnAndFailCi(String scenario) throws Exception {
        String warning = run("groovy", scenario, false);
        assertTrue(warning.contains("UNKNOWN Missing or non-resolvable configuration:"), warning);
        assertTrue(warning.contains("WARN checked=0 drift=0 unknown=1"), warning);
        String failure = run("groovy", scenario, true, "-PfailOnDrift=true");
        assertTrue(failure.contains("Missing or non-resolvable configuration:"), failure);
        assertTrue(failure.contains("policy failed"), failure);
    }

    @Test void emptyConfigurationListIsInvalidEvenInWarningMode() throws Exception {
        String out = run("groovy", "empty-configurations", true);
        assertTrue(out.contains("bootBomGuard configurations must not be empty"), out);
    }

    @Test void configuredClasspathIsCheckedOnce() throws Exception {
        String out = run("groovy", "custom-configuration", false, "-PfailOnDrift=true");
        assertEquals(1, out.lines().filter(line -> line.equals("configuration=runtimeClasspath")).count(), out);
        assertEquals(1, out.lines().filter(line -> line.equals("PASS checked=1 drift=0 unknown=0")).count(), out);
        assertFalse(out.contains("configuration=compileClasspath"), out);
    }

    @Test void resolutionExceptionsAreSanitizedAndFailCi() throws Exception {
        String warning = run("groovy", "resolution-error", false);
        assertTrue(warning.contains("UNKNOWN Gradle dependency resolution failed"), warning);
        assertTrue(warning.contains("WARN checked=0 drift=0 unknown=1"), warning);
        assertFalse(warning.contains("fixture-secret"), warning);
        String failure = run("groovy", "resolution-error", true, "-PfailOnDrift=true");
        assertTrue(failure.contains("UNKNOWN Gradle dependency resolution failed"), failure);
        assertTrue(failure.contains("policy failed"), failure);
        assertFalse(failure.contains("fixture-secret"), failure);
    }

    @Test void pluginCanBeAppliedOnlyToASubproject() throws Exception {
        String out = run("groovy", "multi-project", false, "-PfailOnDrift=true");
        assertTrue(out.contains("> Task :app:bootBomGuard"), out);
        assertTrue(out.contains("PASS checked=1 drift=0 unknown=0"), out);
        assertFalse(out.contains("UNKNOWN"), out);
    }
    @Test void compositeBuildCannotReplaceThePristineBaselinePlatform() throws Exception {
        String warning = run("groovy", "composite-baseline", false);
        assertTrue(warning.contains("org.slf4j:slf4j-api expected=2.0.17 resolved=2.0.18"), warning);
        assertFalse(warning.contains("UNKNOWN"), warning);
        String failure = run("groovy", "composite-baseline", true, "-PfailOnDrift=true");
        assertTrue(failure.contains("policy failed"), failure);
    }

    @Test void missingBaselinePlatformCannotPassAnOtherwiseResolvedGraph() throws Exception {
        String warning = run("groovy", "missing-baseline", false);
        assertTrue(warning.contains("NATIVE_SELECTED=[org.slf4j:slf4j-api:2.0.18, org.springframework.boot:spring-boot-dependencies:4.0.0"), warning);
        assertFalse(warning.contains("UNKNOWN Unresolved Gradle dependencies"), warning);
        assertTrue(warning.contains("UNKNOWN Could not resolve selected Spring Boot BOM in isolated baseline"), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        String failure = run("groovy", "missing-baseline", true, "-PfailOnDrift=true");
        assertTrue(failure.contains("policy failed"), failure);
    }

    @Test void missingImportedBaselineCannotPassAnOtherwiseResolvedGraph() throws Exception {
        String warning = run("groovy", "missing-imported-baseline", false);
        assertTrue(warning.contains("NATIVE_SELECTED=[guard.fixture:nested-bom:1, org.slf4j:slf4j-api:2.0.18"), warning);
        assertFalse(warning.contains("UNKNOWN Unresolved Gradle dependencies"), warning);
        assertTrue(warning.contains("UNKNOWN Could not resolve an imported Boot BOM in isolated baseline"), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        assertTrue(run("groovy", "missing-imported-baseline", true, "-PfailOnDrift=true").contains("policy failed"));
    }

    @Test void strictRequestKeepsNativeSelectedVersion() throws Exception {
        String warning = run("groovy", "rich-strict", false);
        assertTrue(warning.contains("NATIVE_SELECTED=[org.slf4j:slf4j-api:2.0.18"), warning);
        assertTrue(warning.contains("org.slf4j:slf4j-api expected=2.0.17 resolved=2.0.18"), warning);
        assertFalse(warning.contains("UNKNOWN "), warning);
        assertTrue(run("groovy", "rich-strict", true, "-PfailOnDrift=true").contains("policy failed"));
    }

    @Test void boundedRangeCanKeepTheNativeBomRecommendation() throws Exception {
        String out = run("groovy", "bounded-range", false, "-PfailOnDrift=true");
        assertTrue(out.contains("NATIVE_SELECTED=[org.slf4j:slf4j-api:2.0.17"), out);
        assertTrue(out.contains("PASS checked=1 drift=0 unknown=0"), out);
        assertFalse(out.contains("UNKNOWN"), out);
    }

    @Test void rejectingTheOnlyRecommendedVersionIsIncomplete() throws Exception {
        String warning = run("groovy", "rich-reject", false);
        assertTrue(warning.contains("NATIVE_UNRESOLVED=[org.slf4j:slf4j-api"), warning);
        assertTrue(warning.contains("UNKNOWN Unresolved Gradle dependencies"), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        assertTrue(run("groovy", "rich-reject", true, "-PfailOnDrift=true").contains("policy failed"));
    }

    @Test void incompatibleStrictRequirementsAreIncomplete() throws Exception {
        String warning = run("groovy", "strict-conflict", false);
        assertTrue(warning.contains("UNKNOWN Unresolved Gradle dependencies"), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        assertTrue(run("groovy", "strict-conflict", true, "-PfailOnDrift=true").contains("policy failed"));
    }

    @Test void selectionRuleDoesNotContaminateTheBaseline() throws Exception {
        String warning = run("groovy", "selection-rule", false);
        assertTrue(warning.contains("expected=2.0.17 resolved=2.0.18 classification=UNKNOWN_ORIGIN"), warning);
        assertTrue(warning.contains("rule=true"), warning);
        assertTrue(run("groovy", "selection-rule", true, "-PfailOnDrift=true").contains("policy failed"));
    }

    @Test void moduleToProjectSubstitutionIsIncomplete() throws Exception {
        String warning = run("groovy", "project-substitution", false);
        assertTrue(warning.contains("UNKNOWN Unsupported dependency substitution"), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        assertTrue(run("groovy", "project-substitution", true, "-PfailOnDrift=true").contains("policy failed"));
    }

    @Test void platformFromAnotherProjectKeepsThePublishedBaseline() throws Exception {
        String out = run("groovy", "transitive-platform", false, "-PfailOnDrift=true");
        assertTrue(out.contains("PASS checked=1 drift=0 unknown=0"), out);
        assertFalse(out.contains("UNKNOWN"), out);
    }
}
