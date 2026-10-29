package io.github.bootbomguard.core;

import java.util.Objects;
import java.util.regex.Pattern;

public record Coordinates(String group, String artifact, String type, String classifier)
        implements Comparable<Coordinates> {
    private static final Pattern TOKEN = Pattern.compile("[A-Za-z0-9_.+\\-]+");

    public Coordinates {
        group = token(group);
        artifact = token(artifact);
        type = type == null || type.isBlank() ? "jar" : token(type);
        classifier = classifier == null || classifier.isEmpty() ? "" : token(classifier);
    }

    public static Coordinates parse(String value) {
        String[] parts = Objects.requireNonNull(value).split(":", -1);
        if (parts.length == 2) return new Coordinates(parts[0], parts[1], "jar", "");
        if (parts.length == 4) return new Coordinates(parts[0], parts[1], parts[2], parts[3]);
        throw new IllegalArgumentException("Dependency must be group:artifact or group:artifact:type:classifier");
    }

    private static String token(String value) {
        if (value == null || !TOKEN.matcher(value).matches()) {
            throw new IllegalArgumentException("Invalid dependency coordinate: " + Guard.safe(value));
        }
        return value;
    }

    @Override public String toString() {
        return group + ":" + artifact + (type.equals("jar") && classifier.isEmpty() ? "" : ":" + type + ":" + classifier);
    }

    @Override public int compareTo(Coordinates other) { return toString().compareTo(other.toString()); }
}
