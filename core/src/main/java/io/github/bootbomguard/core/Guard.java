package io.github.bootbomguard.core;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;

public final class Guard {
    private Guard() {}

    public enum Origin { DIRECT_OVERRIDE, MANAGED_OVERRIDE, TRANSITIVE_DRIFT, UNKNOWN_ORIGIN }
    public record Resolved(Coordinates coordinates, String version, Origin origin, String evidence) {
        public Resolved {
            Objects.requireNonNull(coordinates);
            requireText(version, "Resolved version");
            Objects.requireNonNull(origin);
            requireText(evidence, "Evidence");
        }
    }
    public record Finding(Coordinates coordinates, String expected, String resolved, Origin origin,
                          String evidence, String reason) {}
    public record Report(String bom, List<Finding> findings, List<String> diagnostics, int checked) {
        public boolean violation() {
            return !diagnostics.isEmpty() || findings.stream().anyMatch(f -> f.reason() == null);
        }

        public String format() {
            StringBuilder out = new StringBuilder("boot-bom-guard BOM=").append(safe(bom)).append('\n');
            diagnostics.stream().distinct().sorted().forEach(d -> out.append("UNKNOWN ").append(safe(d)).append('\n'));
            for (Finding f : findings) {
                out.append(f.reason() == null ? "DRIFT " : "ALLOWED ").append(f.coordinates())
                   .append(" expected=").append(safe(f.expected())).append(" resolved=").append(safe(f.resolved()))
                   .append(" classification=").append(f.origin()).append(" evidence=").append(safe(f.evidence()));
                if (f.reason() != null) out.append(" reason=").append(safe(f.reason()));
                out.append('\n');
            }
            return out.append(violation() ? "WARN" : "PASS").append(" checked=").append(checked)
                      .append(" drift=").append(findings.size()).append(" unknown=").append(diagnostics.size()).toString();
        }
    }

    public static Report compare(String bom, Map<Coordinates, String> expected, List<Resolved> actual,
                                 Map<Coordinates, String> exceptions, List<String> diagnostics) {
        exceptions.forEach((key, reason) -> {
            Objects.requireNonNull(key);
            requireText(reason, "Exception reason for " + key);
        });
        expected.forEach((key, version) -> requireText(version, "Expected version for " + key));
        Map<Coordinates, String> versions = new HashMap<>(expected);
        List<Finding> findings = new ArrayList<>();
        int checked = 0;
        Set<Resolved> seen = new HashSet<>();
        for (Resolved dependency : actual) {
            if (!seen.add(dependency)) continue;
            String version = versions.get(dependency.coordinates());
            if (version == null) continue;
            checked++;
            if (!version.equals(dependency.version())) {
                findings.add(new Finding(dependency.coordinates(), version, dependency.version(), dependency.origin(),
                                         dependency.evidence(), exceptions.get(dependency.coordinates())));
            }
        }
        findings.sort(Comparator.comparing(Finding::coordinates).thenComparing(Finding::resolved)
                .thenComparing(Finding::evidence).thenComparing(Finding::origin));
        return new Report(bom, List.copyOf(findings), diagnostics.stream().distinct().sorted().toList(), checked);
    }

    public static Map<Coordinates, String> exceptions(Map<String, String> values) {
        Map<Coordinates, String> result = new TreeMap<>();
        values.forEach((coordinate, reason) -> {
            Coordinates key = Coordinates.parse(coordinate);
            requireText(reason, "Exception reason for " + key);
            if (result.put(key, reason) != null) throw new IllegalArgumentException("Duplicate exception: " + key);
        });
        return result;
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
    }

    public static String safe(String value) {
        if (value == null) return "unknown";
        StringBuilder out = null;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (Character.isISOControl(c) || c == 0x2028 || c == 0x2029) {
                if (out == null) out = new StringBuilder(value.length() + 6).append(value, 0, i);
                out.append("\\u");
                for (int shift = 12; shift >= 0; shift -= 4) out.append(Character.forDigit((c >>> shift) & 15, 16));
            } else if (out != null) out.append(c);
        }
        return out == null ? value : out.toString();
    }
}
