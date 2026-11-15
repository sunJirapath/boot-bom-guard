package io.github.bootbomguard.maven;

import io.github.bootbomguard.core.Coordinates;
import io.github.bootbomguard.core.Guard;
import org.apache.maven.model.DependencyManagement;
import org.apache.maven.model.InputLocation;
import org.apache.maven.model.InputSource;
import org.apache.maven.plugin.MojoFailureException;
import org.apache.maven.plugin.MojoExecutionException;
import org.apache.maven.plugin.logging.SystemStreamLog;
import org.apache.maven.project.MavenProject;
import org.eclipse.aether.artifact.DefaultArtifact;
import org.eclipse.aether.graph.DefaultDependencyNode;
import org.eclipse.aether.graph.Dependency;
import org.eclipse.aether.graph.DependencyNode;
import org.eclipse.aether.util.graph.transformer.ConflictResolver;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class CheckMojoTest {
    @Test void nullFirstReasonDuplicateAllowlistAttackIsRejectedBeforeAnalysis() throws Exception {
        // Kills using Map.put's nullable return value to detect duplicate configuration entries.
        var mojo = new CheckMojo();
        var entries = new ArrayList<CheckMojo.ExceptionEntry>();
        for (String reason : new String[]{null, "accepted later"}) {
            var entry = new CheckMojo.ExceptionEntry();
            var dependency = CheckMojo.ExceptionEntry.class.getDeclaredField("dependency");
            dependency.setAccessible(true);
            dependency.set(entry, "g:library");
            var reasonField = CheckMojo.ExceptionEntry.class.getDeclaredField("reason");
            reasonField.setAccessible(true);
            reasonField.set(entry, reason);
            entries.add(entry);
        }
        var field = CheckMojo.class.getDeclaredField("exceptions");
        field.setAccessible(true);
        field.set(mojo, entries);
        var error = assertThrows(MojoExecutionException.class, mojo::execute);
        assertTrue(error.getMessage().startsWith("Duplicate exception:"));
    }

    @Test void unsupportedBomCredentialAndWorkflowInjectionAttackIsSanitizedAndFailsClosed() throws Exception {
        // Kills bypassing the shared formatter in the unsupported-BOM Maven warning sink.
        String attack = "2.0.3.RELEASE https://u:bomCredential@host/x?token=queryCredential\n::error::forged";
        var source = new InputSource();
        source.setModelId("org.springframework.boot:spring-boot-dependencies:" + attack);
        var dependency = new org.apache.maven.model.Dependency();
        dependency.setGroupId("g");
        dependency.setArtifactId("library");
        dependency.setVersion("1");
        dependency.setLocation("version", new InputLocation(1, 1, source));
        var management = new DependencyManagement();
        management.addDependency(dependency);
        var project = new MavenProject();
        project.getModel().setDependencyManagement(management);
        var mojo = new CheckMojo();
        var field = CheckMojo.class.getDeclaredField("project");
        field.setAccessible(true);
        field.set(mojo, project);
        field = CheckMojo.class.getDeclaredField("failOnDrift");
        field.setAccessible(true);
        field.setBoolean(mojo, true);
        var output = new StringBuilder();
        mojo.setLog(new SystemStreamLog() {
            @Override public void warn(CharSequence content) { output.append(content); }
        });
        assertThrows(MojoFailureException.class, mojo::execute);
        assertTrue(output.toString().contains("UNKNOWN Unsupported Spring Boot BOM 2.0.3.RELEASE"));
        assertFalse(output.toString().contains("bomCredential"));
        assertFalse(output.toString().contains("queryCredential"));
        assertFalse(output.toString().lines().anyMatch(line -> line.startsWith("::error::")));
        assertFalse(output.toString().contains("PASS checked="));
    }

    @Test void bomGateAcceptsSupportedMajorsAndFailsClosedWithoutResolutionEvidence() throws Exception {
        for (String version : List.of("3.5.16", "4.0.0", "2.7.18", "5.0.0", "4.invalid", "3.5.x")) {
            var source = new InputSource();
            source.setModelId("org.springframework.boot:spring-boot-dependencies:" + version);
            var dependency = new org.apache.maven.model.Dependency();
            dependency.setGroupId("org.slf4j");
            dependency.setArtifactId("slf4j-api");
            dependency.setVersion("2.0.17");
            dependency.setLocation("version", new InputLocation(1, 1, source));
            var management = new DependencyManagement();
            management.addDependency(dependency);
            var project = new MavenProject();
            project.getModel().setDependencyManagement(management);
            for (boolean strict : List.of(false, true)) {
                var mojo = new CheckMojo();
                var projectField = CheckMojo.class.getDeclaredField("project");
                projectField.setAccessible(true);
                projectField.set(mojo, project);
                var strictField = CheckMojo.class.getDeclaredField("failOnDrift");
                strictField.setAccessible(true);
                strictField.setBoolean(mojo, strict);
                var output = new StringBuilder();
                mojo.setLog(new SystemStreamLog() {
                    @Override public void warn(CharSequence content) { output.append(content); }
                });
                // No resolver is injected: accepted versions must still fail closed on missing evidence.
                if (strict) assertThrows(MojoFailureException.class, mojo::execute);
                else assertDoesNotThrow(mojo::execute);
                String diagnostic = Guard.supportedBootVersion(version)
                        ? "UNKNOWN Maven model/dependency resolution failed:"
                        : "UNKNOWN Unsupported Spring Boot BOM " + version;
                assertTrue(output.toString().contains(diagnostic), output.toString());
                assertFalse(output.toString().contains("PASS checked="), output.toString());
                if (!Guard.supportedBootVersion(version)) assertFalse(output.toString().contains("resolution failed"), output.toString());
            }
        }
    }

    private static DefaultDependencyNode node(String name) {
        return new DefaultDependencyNode(new Dependency(new DefaultArtifact("guard.fixture", name, "jar", "1"), "compile"));
    }

    private static List<Guard.Resolved> collect(DependencyNode root) throws Exception {
        var actual = new ArrayList<Guard.Resolved>();
        var method = CheckMojo.class.getDeclaredMethod("collect", DependencyNode.class, int.class,
                Map.class, Map.class, List.class, java.util.Set.class, List.class);
        method.setAccessible(true);
        method.invoke(new CheckMojo(), root, 0, Map.of(), Map.of(), actual, new HashSet<>(), new ArrayList<>());
        return actual;
    }

    @Test void deepNativeGraphDoesNotOverflowTheJavaStack() {
        var root = node("root");
        var parent = root;
        for (int i = 0; i < 20000; i++) {
            var child = node("module-" + i);
            parent.getChildren().add(child);
            parent = child;
        }
        var actual = assertDoesNotThrow(() -> collect(root));
        assertEquals(20000, actual.size());
        assertEquals(Guard.Origin.TRANSITIVE_DRIFT, actual.get(actual.size() - 1).origin());
    }

    @Test void sharedDirectNodeKeepsItsShortestRootPath() throws Exception {
        var root = node("root");
        var bridge = node("bridge");
        var direct = node("direct");
        root.getChildren().addAll(List.of(bridge, direct));
        bridge.getChildren().add(direct);
        var actual = collect(root);
        assertEquals(2, actual.size());
        assertEquals(Guard.Origin.DIRECT_OVERRIDE, actual.stream()
                .filter(item -> item.coordinates().equals(Coordinates.parse("guard.fixture:direct"))).findFirst().orElseThrow().origin());
    }

    @Test void cyclicAndVerboseLosingNodesAreNotTraversedAgain() throws Exception {
        var root = node("root");
        var selected = node("selected");
        var loser = node("loser");
        loser.setData(ConflictResolver.NODE_DATA_WINNER, selected);
        loser.getChildren().add(node("loser-child"));
        root.getChildren().addAll(List.of(selected, loser));
        selected.getChildren().add(root);
        var actual = collect(root);
        assertEquals(1, actual.size());
        assertEquals("selected", actual.get(0).coordinates().artifact());
    }
}
