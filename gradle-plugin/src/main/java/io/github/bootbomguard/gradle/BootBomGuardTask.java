package io.github.bootbomguard.gradle;

import io.github.bootbomguard.core.Coordinates;
import io.github.bootbomguard.core.Guard;
import org.gradle.api.DefaultTask;
import org.gradle.api.GradleException;
import org.gradle.api.Project;
import org.gradle.api.artifacts.Configuration;
import org.gradle.api.artifacts.ExternalModuleDependency;
import org.gradle.api.artifacts.component.ModuleComponentIdentifier;
import org.gradle.api.artifacts.component.ModuleComponentSelector;
import org.gradle.api.artifacts.result.DependencyResult;
import org.gradle.api.artifacts.result.ResolvedComponentResult;
import org.gradle.api.artifacts.result.ResolvedDependencyResult;
import org.gradle.api.artifacts.result.UnresolvedDependencyResult;
import org.gradle.api.attributes.Category;
import org.gradle.api.provider.ListProperty;
import org.gradle.api.provider.MapProperty;
import org.gradle.api.provider.Property;
import org.gradle.api.tasks.Input;
import org.gradle.api.tasks.TaskAction;
import org.gradle.work.DisableCachingByDefault;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

@DisableCachingByDefault(because = "Checks the current native dependency resolution graph on every invocation")
public abstract class BootBomGuardTask extends DefaultTask {
    @Input public abstract Property<Boolean> getFailOnDrift();
    @Input public abstract ListProperty<String> getConfigurationNames();
    @Input public abstract MapProperty<String, String> getExceptions();

    @TaskAction public void check() {
        Map<Coordinates, String> exceptions;
        try { exceptions = Guard.exceptions(getExceptions().get()); }
        catch (IllegalArgumentException e) { throw new GradleException("Invalid bootBomGuard exceptions", e); }
        boolean violation = false;
        if (getConfigurationNames().get().isEmpty()) throw new GradleException("bootBomGuard configurations must not be empty");
        for (String name : new TreeSet<>(getConfigurationNames().get())) {
            List<String> diagnostics = new ArrayList<>();
            Guard.Report report;
            try { report = inspect(getProject(), name, exceptions, diagnostics); }
            catch (Exception e) {
                // Resolver messages may contain repository credentials; do not echo them in reports.
                diagnostics.add("Gradle dependency resolution failed (" + e.getClass().getSimpleName()
                        + "); inspect Gradle diagnostics and configured repositories/offline cache.");
                report = Guard.compare("unknown", Map.of(), List.of(), exceptions, diagnostics);
            }
            getLogger().lifecycle("configuration=" + Guard.safe(name) + "\n" + report.format());
            violation |= report.violation();
        }
        if (getFailOnDrift().get() && violation) throw new GradleException("boot-bom-guard policy failed: drift or incomplete analysis");
    }

    private Guard.Report inspect(Project project, String name, Map<Coordinates, String> exceptions,
                                 List<String> diagnostics) {
        Configuration configuration = project.getConfigurations().findByName(name);
        if (configuration == null || !configuration.isCanBeResolved()) {
            diagnostics.add("Missing or non-resolvable configuration: " + name + "; configure bootBomGuard.configurations.");
            return Guard.compare("unknown", Map.of(), List.of(), exceptions, diagnostics);
        }
        var graph = configuration.getIncoming().getResolutionResult();
        var root = graph.getRootComponent().get();
        List<DependencyResult> edges = new ArrayList<>(graph.getAllDependencies());
        if (edges.stream().anyMatch(UnresolvedDependencyResult.class::isInstance)) diagnostics.add("Unresolved Gradle dependencies; analysis is incomplete.");
        Set<ModuleComponentIdentifier> boms = new TreeSet<>(Comparator.comparing(ModuleComponentIdentifier::getDisplayName));
        Set<String> modes = new TreeSet<>();
        Set<String> requestedBoms = new TreeSet<>();
        for (DependencyResult edge : edges) {
            if (edge instanceof ResolvedDependencyResult resolved && edge.getRequested() instanceof ModuleComponentSelector selector) {
                if (!(resolved.getSelected().getId() instanceof ModuleComponentIdentifier selected)
                        || !selector.getGroup().equals(selected.getGroup()) || !selector.getModule().equals(selected.getModule())) {
                    diagnostics.add("Unsupported dependency substitution: " + selector.getDisplayName()
                            + " -> " + resolved.getSelected().getId().getDisplayName() + "; comparison is incomplete.");
                }
            }
            if (edge.getRequested() instanceof ModuleComponentSelector selector && selector.getGroup().equals("org.springframework.boot")
                    && selector.getModule().equals("spring-boot-dependencies")) {
                requestedBoms.add(selector.getDisplayName());
                if (edge instanceof UnresolvedDependencyResult) diagnostics.add("Unresolved/ambiguous Spring Boot BOM selection: " + selector.getDisplayName());
            }
            if (edge instanceof ResolvedDependencyResult resolved && resolved.getSelected().getId() instanceof ModuleComponentIdentifier id
                    && id.getGroup().equals("org.springframework.boot") && id.getModule().equals("spring-boot-dependencies")) {
                Category category = resolved.getResolvedVariant().getAttributes().getAttribute(Category.CATEGORY_ATTRIBUTE);
                if (category == null || !Set.of(Category.REGULAR_PLATFORM, Category.ENFORCED_PLATFORM).contains(category.getName())) {
                    diagnostics.add("Boot BOM selected without a platform variant; use platform(...) or enforcedPlatform(...).");
                } else modes.add(category.getName());
                boms.add(id);
            }
        }
        if (boms.size() != 1) {
            diagnostics.add(boms.isEmpty() ? "Missing Spring Boot BOM; import a native Gradle platform."
                    : "Ambiguous selected Spring Boot BOMs: " + boms);
            return Guard.compare("unknown", Map.of(), List.of(), exceptions, diagnostics);
        }
        ModuleComponentIdentifier bom = boms.iterator().next();
        String label = bom.getDisplayName() + " mode=" + modes + " requested=" + requestedBoms;
        if (!bom.getVersion().startsWith("4.")) {
            diagnostics.add("Unsupported Spring Boot BOM " + bom.getVersion() + "; MVP supports Boot 4.x.");
            return Guard.compare(label, Map.of(), List.of(), exceptions, diagnostics);
        }
        List<ResolvedComponentResult> modules = graph.getAllComponents().stream()
                .filter(component -> component.getId() instanceof ModuleComponentIdentifier)
                .filter(component -> edges.stream().anyMatch(edge -> edge instanceof ResolvedDependencyResult resolved
                        && !edge.isConstraint() && resolved.getSelected().equals(component) && !platform(resolved)))
                .sorted(Comparator.comparing(component -> component.getId().getDisplayName())).toList();
        Map<Coordinates, String> expected = expected(project, configuration, bom, modules, diagnostics);
        List<Guard.Resolved> actual = new ArrayList<>();
        for (ResolvedComponentResult module : modules) {
            ModuleComponentIdentifier id = (ModuleComponentIdentifier) module.getId();
            Coordinates key = new Coordinates(id.getGroup(), id.getModule(), "jar", "");
            var incoming = edges.stream().filter(edge -> edge instanceof ResolvedDependencyResult resolved
                    && resolved.getSelected().equals(module)).toList();
            var reason = module.getSelectionReason();
            Guard.Origin origin = Guard.Origin.UNKNOWN_ORIGIN;
            boolean direct = matches(incoming, root, id.getVersion(), false);
            boolean constraint = matches(incoming, root, id.getVersion(), true);
            boolean transitive = incoming.stream().anyMatch(edge -> !edge.isConstraint() && !edge.getFrom().equals(root)
                    && edge.getRequested() instanceof ModuleComponentSelector selector && selector.getVersion().equals(id.getVersion()));
            if (!reason.isForced() && !reason.isSelectedByRule()) {
                if (direct) origin = Guard.Origin.DIRECT_OVERRIDE;
                else if (constraint) origin = Guard.Origin.MANAGED_OVERRIDE;
                else if (transitive) origin = Guard.Origin.TRANSITIVE_DRIFT;
            }
            String evidence = "configuration=" + name + "; rootRequest=" + direct + "; rootConstraint=" + constraint
                    + "; transitiveRequest=" + transitive + "; constrained=" + reason.isConstrained()
                    + "; forced=" + reason.isForced() + "; rule=" + reason.isSelectedByRule()
                    + "; conflict=" + reason.isConflictResolution() + "; constraint origin unknown";
            actual.add(new Guard.Resolved(key, id.getVersion(), origin, evidence));
        }
        return Guard.compare(label, expected, actual, exceptions, diagnostics);
    }

    private boolean matches(List<DependencyResult> edges, ResolvedComponentResult root, String version, boolean constraint) {
        return edges.stream().anyMatch(edge -> edge.isConstraint() == constraint && edge.getFrom().equals(root)
                && edge.getRequested() instanceof ModuleComponentSelector selector && selector.getVersion().equals(version));
    }

    private boolean platform(ResolvedDependencyResult edge) {
        Category category = edge.getResolvedVariant().getAttributes().getAttribute(Category.CATEGORY_ATTRIBUTE);
        return category != null && Set.of(Category.REGULAR_PLATFORM, Category.ENFORCED_PLATFORM).contains(category.getName());
    }

    private Map<Coordinates, String> expected(Project project, Configuration source, ModuleComponentIdentifier bom,
                                               List<ResolvedComponentResult> modules, List<String> diagnostics) {
        List<org.gradle.api.artifacts.Dependency> requests = new ArrayList<>();
        requests.add(project.getDependencies().platform(bom.getDisplayName()));
        for (ResolvedComponentResult module : modules) {
            ModuleComponentIdentifier id = (ModuleComponentIdentifier) module.getId();
            ExternalModuleDependency dependency = (ExternalModuleDependency) project.getDependencies().create(id.getGroup() + ":" + id.getModule());
            // Only BOM constraints participate in baseline selection, never the libraries' transitive dependency versions.
            dependency.setTransitive(false);
            requests.add(dependency);
        }
        Configuration baseline = project.getConfigurations().detachedConfiguration(requests.toArray(org.gradle.api.artifacts.Dependency[]::new));
        copyAttributes(source, baseline);
        var graph = baseline.getIncoming().getResolutionResult();
        Map<Coordinates, String> result = new TreeMap<>();
        Set<Coordinates> managed = new HashSet<>();
        Set<Coordinates> requestedKeys = new HashSet<>();
        for (var module : modules) {
            var id = (ModuleComponentIdentifier) module.getId();
            requestedKeys.add(new Coordinates(id.getGroup(), id.getModule(), "jar", ""));
        }
        for (DependencyResult edge : graph.getAllDependencies()) {
            if (edge.isConstraint() && edge.getRequested() instanceof ModuleComponentSelector selector) {
                Coordinates key = new Coordinates(selector.getGroup(), selector.getModule(), "jar", "");
                if (!requestedKeys.contains(key)) continue;
                managed.add(key);
                var constraint = selector.getVersionConstraint();
                String requested = constraint.getRequiredVersion().isEmpty() ? constraint.getStrictVersion() : constraint.getRequiredVersion();
                if (requested.isEmpty() || requested.matches(".*[+\\[\\](),].*") || requested.startsWith("latest.")) {
                    diagnostics.add("Unsupported non-exact BOM constraint for " + selector.getGroup() + ":" + selector.getModule());
                }
            }
        }
        for (var component : graph.getAllComponents()) {
            if (component.getId() instanceof ModuleComponentIdentifier id) {
                Coordinates key = new Coordinates(id.getGroup(), id.getModule(), "jar", "");
                if (managed.contains(key)) result.put(key, id.getVersion());
            }
        }
        if (graph.getAllDependencies().stream().anyMatch(edge -> edge instanceof UnresolvedDependencyResult && edge.isConstraint())) {
            diagnostics.add("Could not resolve a Boot BOM constraint; baseline analysis is incomplete.");
        }
        for (Coordinates key : managed) {
            if (!result.containsKey(key)) diagnostics.add("Unresolved Boot-managed baseline for " + key);
        }
        return result;
    }

    private void copyAttributes(Configuration source, Configuration target) {
        for (var attribute : source.getAttributes().keySet()) copyAttribute(source, target, attribute);
    }
    private <T> void copyAttribute(Configuration source, Configuration target, org.gradle.api.attributes.Attribute<T> attribute) {
        target.getAttributes().attribute(attribute, source.getAttributes().getAttribute(attribute));
    }
}
