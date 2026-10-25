package io.github.bootbomguard.core;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.bootbomguard.core.Guard.*;

class GuardTest {
    private final Coordinates key = Coordinates.parse("org.slf4j:slf4j-api");
    private final Resolved drift = new Resolved(key, "2.0.18", Origin.DIRECT_OVERRIDE, "declaration");

    @Test void classifiesAndAppliesPolicyWithoutCallingDriftIncompatibility() {
        Report warn = compare("4.0.0", Map.of(key, "2.0.17"), List.of(drift), Map.of(), List.of());
        assertTrue(warn.violation());
        assertEquals(Origin.DIRECT_OVERRIDE, warn.findings().getFirst().origin());
        assertTrue(warn.format().contains("expected=2.0.17 resolved=2.0.18"));
        Report allowed = compare("4.0.0", Map.of(key, "2.0.17"), List.of(drift), Map.of(key, "Reviewed upgrade"), List.of());
        assertFalse(allowed.violation());
        assertTrue(allowed.format().contains("reason=Reviewed upgrade"));
    }

    @Test void checksOnlyResolvedManagedCoordinatesAndPreservesClassifier() {
        Coordinates tests = Coordinates.parse("org.slf4j:slf4j-api:test-jar:tests");
        Report report = compare("4.0.0", Map.of(key, "2.0.17", tests, "1"),
                List.of(new Resolved(key, "2.0.17", Origin.UNKNOWN_ORIGIN, "aligned")), Map.of(), List.of());
        assertFalse(report.violation());
        assertEquals(1, report.checked());
        assertEquals(new Coordinates("org.slf4j", "slf4j-api", null, null), key);
        assertNotEquals(key, tests);
    }

    @Test void unknownCannotBecomeGreenAndExceptionsNeedReasons() {
        assertTrue(compare("unknown", Map.of(), List.of(), Map.of(), List.of("Missing BOM")).violation());
        assertThrows(IllegalArgumentException.class, () -> exceptions(Map.of(key.toString(), " ")));
        assertThrows(IllegalArgumentException.class, () -> Coordinates.parse("*:slf4j-api"));
    }

    @Test void formattingIsDeterministicAndEscapesUntrustedControlCharacters() {
        Coordinates other = Coordinates.parse("a:b");
        Resolved first = new Resolved(other, "2", Origin.UNKNOWN_ORIGIN, "rule\nPASS\u001b[0m");
        Map<Coordinates, String> expected = Map.of(key, "2.0.17", other, "1");
        assertEquals(compare("4", expected, List.of(drift, first), Map.of(), List.of("z", "a")).format(),
                     compare("4", expected, List.of(first, drift), Map.of(), List.of("a", "z")).format());
        assertTrue(compare("4", expected, List.of(first), Map.of(), List.of()).format().contains("rule\\u000aPASS\\u001b"));
    }
}
