package io.github.bootbomguard.gradle;

import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

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
        try (var files = Files.list(fixture)) {
            for (Path file : files.filter(Files::isRegularFile).toList()) {
                Files.copy(file, directory.resolve(file.getFileName()), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            }
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
}
