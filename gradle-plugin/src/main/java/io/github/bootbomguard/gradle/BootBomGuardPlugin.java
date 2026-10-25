package io.github.bootbomguard.gradle;

import org.gradle.api.Plugin;
import org.gradle.api.Project;
import java.util.List;
import java.util.Map;

public final class BootBomGuardPlugin implements Plugin<Project> {
    @Override public void apply(Project project) {
        BootBomGuardExtension extension = project.getExtensions().create("bootBomGuard", BootBomGuardExtension.class);
        extension.getFailOnDrift().convention(false);
        extension.getConfigurations().convention(List.of("compileClasspath", "runtimeClasspath", "testCompileClasspath", "testRuntimeClasspath"));
        extension.getExceptions().convention(Map.of());
        project.getTasks().register("bootBomGuard", BootBomGuardTask.class, task -> {
            task.setGroup("verification");
            task.setDescription("Reports resolved dependency drift from the selected Spring Boot BOM");
            task.getFailOnDrift().convention(extension.getFailOnDrift());
            task.getConfigurationNames().convention(extension.getConfigurations());
            task.getExceptions().convention(extension.getExceptions());
            // shortcut: native graph access uses Project during execution; add configuration-cache support when needed.
            task.notCompatibleWithConfigurationCache("Uses native configuration resolution at execution time");
        });
    }
}
