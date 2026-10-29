package io.github.bootbomguard.maven;

import io.github.bootbomguard.core.Coordinates;
import io.github.bootbomguard.core.Guard;
import org.apache.maven.execution.MavenSession;
import org.apache.maven.model.Dependency;
import org.apache.maven.model.InputLocation;
import org.apache.maven.plugin.AbstractMojo;
import org.apache.maven.plugin.MojoExecutionException;
import org.apache.maven.plugin.MojoFailureException;
import org.apache.maven.plugins.annotations.Component;
import org.apache.maven.plugins.annotations.Mojo;
import org.apache.maven.plugins.annotations.Parameter;
import org.apache.maven.project.DefaultDependencyResolutionRequest;
import org.apache.maven.project.DefaultProjectBuildingRequest;
import org.apache.maven.project.MavenProject;
import org.apache.maven.project.ProjectBuilder;
import org.apache.maven.project.ProjectDependenciesResolver;
import org.eclipse.aether.RepositorySystem;
import org.eclipse.aether.artifact.Artifact;
import org.eclipse.aether.artifact.DefaultArtifact;
import org.eclipse.aether.graph.DependencyNode;
import org.eclipse.aether.resolution.ArtifactRequest;
import org.eclipse.aether.resolution.VersionRequest;
import org.eclipse.aether.util.graph.transformer.ConflictResolver;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

@Mojo(name = "check", threadSafe = true)
public final class CheckMojo extends AbstractMojo {
    private static final String BOOT = "org.springframework.boot:spring-boot-dependencies:";
    @Parameter(defaultValue = "${project}", readonly = true, required = true) private MavenProject project;
    @Parameter(defaultValue = "${session}", readonly = true, required = true) private MavenSession session;
    @Parameter(property = "bootBomGuard.failOnDrift", defaultValue = "false") private boolean failOnDrift;
    @Parameter private List<ExceptionEntry> exceptions = new ArrayList<>();
    @Component private RepositorySystem repositorySystem;
    @Component private ProjectBuilder projectBuilder;
    @Component private ProjectDependenciesResolver dependenciesResolver;

    public static final class ExceptionEntry {
        @Parameter(required = true) private String dependency;
        @Parameter(required = true) private String reason;
    }

    @Override public void execute() throws MojoExecutionException, MojoFailureException {
        Map<String, String> configured = new LinkedHashMap<>();
        for (ExceptionEntry entry : exceptions) {
            if (configured.put(entry.dependency, entry.reason) != null) {
                throw new MojoExecutionException("Duplicate exception: " + Guard.safe(entry.dependency));
            }
        }
        Map<Coordinates, String> allowed;
        try { allowed = Guard.exceptions(configured); }
        catch (IllegalArgumentException | NullPointerException e) { throw new MojoExecutionException("Invalid bootBomGuard exceptions", e); }

        List<String> diagnostics = new ArrayList<>();
        Map<Coordinates, String> expected = new TreeMap<>();
        List<Guard.Resolved> actual = new ArrayList<>();
        String bom = "unknown";
        try {
            Set<String> versions = bomVersions();
            if (versions.isEmpty()) diagnostics.add("Missing Spring Boot BOM; use a Boot parent or import spring-boot-dependencies.");
            else if (versions.size() != 1) diagnostics.add("Ambiguous Spring Boot BOM versions: " + versions);
            else {
                String version = versions.iterator().next();
                bom = BOOT + version;
                if (!version.startsWith("4.")) diagnostics.add("Unsupported Spring Boot BOM " + version + "; MVP supports Boot 4.x.");
                else {
                    expected = expected(version, diagnostics);
                    Map<Coordinates, String> managed = management(project);
                    DependencyNode root = dependenciesResolver.resolve(
                            new DefaultDependencyResolutionRequest(project, session.getRepositorySession())).getDependencyGraph();
                    collect(root, 0, expected, managed, actual, new HashSet<>());
                }
            }
        } catch (Exception e) {
            // Resolver messages may contain repository credentials; do not echo them in reports.
            diagnostics.add("Maven model/dependency resolution failed (" + e.getClass().getSimpleName()
                    + "); inspect Maven diagnostics and configured repositories/offline cache.");
        }
        Guard.Report report = Guard.compare(bom, expected, actual, allowed, diagnostics);
        if (report.violation()) getLog().warn(report.format()); else getLog().info(report.format());
        if (failOnDrift && report.violation()) throw new MojoFailureException("boot-bom-guard policy failed: drift or incomplete analysis");
    }

    private Set<String> bomVersions() {
        Set<String> versions = new TreeSet<>();
        if (project.getDependencyManagement() != null) {
            for (Dependency dependency : project.getDependencyManagement().getDependencies()) {
                for (String field : List.of("groupId", "artifactId", "type", "classifier", "version")) {
                    InputLocation location = dependency.getLocation(field);
                    if (location != null && location.getSource() != null) {
                        String id = location.getSource().getModelId();
                        if (id != null && id.startsWith(BOOT)) versions.add(id.substring(BOOT.length()));
                    }
                }
            }
        }
        // Effective source locations survive imports and profile merging; shadowed raw declarations are not selected BOMs.
        return versions;
    }

    private Map<Coordinates, String> expected(String version, List<String> diagnostics) throws Exception {
        var artifact = repositorySystem.resolveArtifact(session.getRepositorySession(),
                new ArtifactRequest(new DefaultArtifact("org.springframework.boot", "spring-boot-dependencies", "pom", version),
                        project.getRemoteProjectRepositories(), "project")).getArtifact();
        var request = new DefaultProjectBuildingRequest(session.getProjectBuildingRequest());
        request.setRepositorySession(session.getRepositorySession());
        request.setRemoteRepositories(project.getRemoteArtifactRepositories());
        request.setProcessPlugins(false);
        request.setResolveDependencies(false);
        request.setUserProperties(new Properties());
        request.setSystemProperties(new Properties());
        request.setProfiles(List.of());
        request.setActiveProfileIds(List.of());
        request.setInactiveProfileIds(List.of());
        Map<Coordinates, String> result = management(projectBuilder.build(artifact.getFile(), request).getProject());
        result.entrySet().removeIf(entry -> {
            boolean unsupported = entry.getValue().contains("${") || entry.getValue().matches(".*[\\[\\](),].*");
            if (unsupported) diagnostics.add("Unsupported non-exact BOM version for " + entry.getKey());
            return unsupported;
        });
        if (result.isEmpty()) diagnostics.add("Selected Spring Boot BOM has no comparable managed versions.");
        return result;
    }

    private Map<Coordinates, String> management(MavenProject source) {
        Map<Coordinates, String> result = new TreeMap<>();
        if (source.getDependencyManagement() != null) {
            for (Dependency dependency : source.getDependencyManagement().getDependencies()) {
                if (dependency.getVersion() != null && !"import".equals(dependency.getScope())) {
                    result.put(coordinates(dependency), dependency.getVersion());
                }
            }
        }
        return result;
    }

    private Coordinates coordinates(Dependency dependency) {
        var type = session.getRepositorySession().getArtifactTypeRegistry().get(dependency.getType());
        String classifier = dependency.getClassifier();
        if ((classifier == null || classifier.isEmpty()) && type != null) classifier = type.getClassifier();
        return new Coordinates(dependency.getGroupId(), dependency.getArtifactId(), dependency.getType(), classifier);
    }

    private String resolvedVersion(Artifact artifact, String version) throws Exception {
        if (!version.endsWith("-SNAPSHOT")) return version;
        var resolved = repositorySystem.resolveVersion(session.getRepositorySession(),
                new VersionRequest(artifact.setVersion(version), project.getRemoteProjectRepositories(), "project"));
        // Resolver may fall back to the alias when no snapshot metadata is available.
        if (resolved.getRepository() == null || resolved.getVersion() == null) {
            throw new IllegalStateException("Snapshot identity is unavailable");
        }
        return resolved.getVersion();
    }

    private void collect(DependencyNode node, int depth, Map<Coordinates, String> expected,
                         Map<Coordinates, String> managed, List<Guard.Resolved> actual, Set<DependencyNode> visited) throws Exception {
        // Verbose Resolver sessions retain losing nodes; only the selected graph is an actual dependency.
        if (node.getData().get(ConflictResolver.NODE_DATA_WINNER) != null) return;
        if (!visited.add(node)) return;
        Artifact artifact = node.getArtifact();
        if (artifact != null && depth > 0) {
            Coordinates key = new Coordinates(artifact.getGroupId(), artifact.getArtifactId(),
                    artifact.getProperty("type", artifact.getExtension()), artifact.getClassifier());
            String version = artifact.getVersion();
            if (expected.containsKey(key)) {
                // Compare native snapshot identities; an explicitly older timestamp must remain drift.
                expected.put(key, resolvedVersion(artifact, expected.get(key)));
                if (managed.containsKey(key)) managed.put(key, resolvedVersion(artifact, managed.get(key)));
            }
            Guard.Origin origin;
            String evidence;
            boolean managedOverride = managed.containsKey(key) && !managed.get(key).equals(expected.get(key));
            if (managedOverride && managed.get(key).equals(version)) {
                origin = Guard.Origin.MANAGED_OVERRIDE;
                evidence = "effective dependencyManagement=" + managed.get(key) + "; declaration source unknown";
            } else if (depth == 1) {
                origin = Guard.Origin.DIRECT_OVERRIDE;
                evidence = "direct dependency selected by Maven; managed=" + ((node.getManagedBits() & DependencyNode.MANAGED_VERSION) != 0);
            } else {
                origin = Guard.Origin.TRANSITIVE_DRIFT;
                evidence = "transitive dependency selected by Maven mediation; managed=" + ((node.getManagedBits() & DependencyNode.MANAGED_VERSION) != 0);
            }
            actual.add(new Guard.Resolved(key, version, origin, evidence + "; path=" + (depth == 1 ? "direct" : "transitive")));
        }
        for (DependencyNode child : node.getChildren()) collect(child, depth + 1, expected, managed, actual, visited);
    }
}
