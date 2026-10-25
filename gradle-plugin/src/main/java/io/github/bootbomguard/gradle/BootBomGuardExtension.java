package io.github.bootbomguard.gradle;

import org.gradle.api.provider.ListProperty;
import org.gradle.api.provider.MapProperty;
import org.gradle.api.provider.Property;

public abstract class BootBomGuardExtension {
    public abstract Property<Boolean> getFailOnDrift();
    public abstract ListProperty<String> getConfigurations();
    public abstract MapProperty<String, String> getExceptions();
}
