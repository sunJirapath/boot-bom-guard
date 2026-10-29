package io.github.bootbomguard.core;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.Collections;
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

    @Test void coordinatesRejectInvalidTokensAndNormalizeTypeAndClassifier() {
        for (String value : List.of("", ":a", "g:", "g:a:x", "g:a:x:y:z", "*:a")) {
            assertThrows(IllegalArgumentException.class, () -> Coordinates.parse(value), value);
        }
        assertThrows(NullPointerException.class, () -> Coordinates.parse(null));
        assertEquals(new Coordinates("g", "a", "jar", ""), new Coordinates("g", "a", " ", null));
        assertEquals(Coordinates.parse("g:a"), Coordinates.parse("g:a:jar:"));
        assertEquals("g:a:test-jar:tests", Coordinates.parse("g:a:test-jar:tests").toString());
    }

    @Test void rejectsMissingResolvedAndExpectedValuesAndEscapesInvalidCoordinateControls() {
        assertThrows(NullPointerException.class, () -> new Resolved(null, "1", Origin.UNKNOWN_ORIGIN, "evidence"));
        assertThrows(IllegalArgumentException.class, () -> new Resolved(key, " ", Origin.UNKNOWN_ORIGIN, "evidence"));
        assertThrows(IllegalArgumentException.class, () -> new Resolved(key, "1", Origin.UNKNOWN_ORIGIN, " "));
        assertThrows(NullPointerException.class, () -> new Resolved(key, "1", null, "evidence"));
        assertThrows(IllegalArgumentException.class,
                () -> compare("4.0.0", Map.of(key, " "), List.of(), Map.of(), List.of()));
        assertThrows(IllegalArgumentException.class,
                () -> compare("4.0.0", Collections.singletonMap(key, null), List.of(), Map.of(), List.of()));

        IllegalArgumentException invalidControl = assertThrows(IllegalArgumentException.class,
                () -> Coordinates.parse("g:a:jar:\u0001"));
        assertTrue(invalidControl.getMessage().contains("\\u0001"));
        assertFalse(invalidControl.getMessage().contains("\u0001"));
    }

    @Test void versionsUseExactStringEquality() {
        for (String[] versions : List.of(new String[]{"1.0-rc1", "1.0-rc2"},
                                         new String[]{"1.0-SNAPSHOT", "1.0"},
                                         new String[]{"1.0", "1.0.0"})) {
            Report report = compare("4.0.0", Map.of(key, versions[0]),
                    List.of(new Resolved(key, versions[1], Origin.UNKNOWN_ORIGIN, "selected")), Map.of(), List.of());
            assertTrue(report.violation());
            assertEquals(versions[0], report.findings().getFirst().expected());
            assertEquals(versions[1], report.findings().getFirst().resolved());
        }
    }

    @Test void ignoresUnmanagedResolvedCoordinatesAndDeduplicatesExactResolvedEntries() {
        Resolved same = new Resolved(key, "2.0.18", Origin.DIRECT_OVERRIDE, "declaration");
        Report report = compare("4.0.0", Map.of(key, "2.0.17"), List.of(same, same), Map.of(), List.of());
        assertEquals(1, report.checked());
        assertEquals(1, report.findings().size());

        Coordinates unmanaged = Coordinates.parse("g:unmanaged");
        Report ignored = compare("4.0.0", Map.of(key, "2.0.17"),
                List.of(new Resolved(unmanaged, "1", Origin.UNKNOWN_ORIGIN, "unmanaged")), Map.of(), List.of());
        assertEquals(0, ignored.checked());
        assertFalse(ignored.violation());

        Report unresolved = compare("4.0.0", Map.of(key, "2.0.17"), List.of(), Map.of(),
                List.of("Unresolved managed coordinate: " + key));
        assertEquals(0, unresolved.checked());
        assertTrue(unresolved.violation());
    }

    @Test void exceptionsMatchExactCoordinatesAndRejectNormalizedDuplicatesAndInvalidReasons() {
        Coordinates testJar = Coordinates.parse("org.slf4j:slf4j-api:test-jar:tests");
        Report report = compare("4.0.0", Map.of(key, "2.0.17", testJar, "2.0.17"),
                List.of(new Resolved(key, "2.0.18", Origin.DIRECT_OVERRIDE, "main"),
                        new Resolved(testJar, "2.0.18", Origin.DIRECT_OVERRIDE, "tests")),
                Map.of(key, "Reviewed"), List.of());
        assertEquals(2, report.findings().size());
        assertEquals("Reviewed", report.findings().getFirst().reason());
        assertNull(report.findings().getLast().reason());

        Map<String, String> aliases = new LinkedHashMap<>();
        aliases.put("g:a", "one");
        aliases.put("g:a:jar:", "two");
        assertThrows(IllegalArgumentException.class, () -> exceptions(aliases));
        assertThrows(IllegalArgumentException.class, () -> exceptions(Map.of("g:a", " ")));
        Map<String, String> nullReason = Collections.singletonMap("g:a", null);
        assertThrows(IllegalArgumentException.class, () -> exceptions(nullReason));
    }

    @Test void diagnosticsRemainViolationsWhenAllDriftIsAllowedAndResultsAreImmutable() {
        Report report = compare("4.0.0", Map.of(key, "2.0.17"), List.of(drift), Map.of(key, "Reviewed"),
                List.of("Unresolved managed coordinate"));
        assertTrue(report.violation());
        assertThrows(UnsupportedOperationException.class, () -> report.findings().clear());
        assertThrows(UnsupportedOperationException.class, () -> report.diagnostics().clear());
    }

    @Test void sanitizesBomReasonAndDiagnosticIncludingUnicodeSeparators() {
        String out = compare("4\nBOM\u2028", Map.of(key, "2.0.17"), List.of(drift),
                Map.of(key, "reason\u2029next"), List.of("diag\nnext")).format();
        assertTrue(out.contains("BOM=4\\u000aBOM\\u2028"), out);
        assertTrue(out.contains("diag\\u000anext"), out);
        assertTrue(out.contains("reason=reason\\u2029next"), out);
        assertEquals(1, out.lines().filter(line -> line.startsWith("UNKNOWN ")).count());
    }

    @Test void sameEvidenceWithDifferentOriginsFormatsIdenticallyRegardlessOfInputOrder() {
        Resolved direct = new Resolved(key, "2.0.18", Origin.DIRECT_OVERRIDE, "same evidence");
        Resolved transitive = new Resolved(key, "2.0.18", Origin.TRANSITIVE_DRIFT, "same evidence");
        Map<Coordinates, String> expected = Map.of(key, "2.0.17");
        String forward = compare("4.0.0", expected, List.of(direct, transitive), Map.of(), List.of()).format();
        String reverse = compare("4.0.0", expected, List.of(transitive, direct), Map.of(), List.of()).format();
        assertEquals(forward, reverse);
    }

    @Test void mixedGraphsMatchThePreviousComparisonPolicyAcrossShuffledInputs() {
        var random = new java.util.Random(729);
        for (int round = 0; round < 100; round++) {
            Map<Coordinates, String> expected = new java.util.TreeMap<>();
            Map<Coordinates, String> allowed = new java.util.HashMap<>();
            List<Resolved> actual = new java.util.ArrayList<>();
            for (int i = 0; i < 200; i++) {
                Coordinates coordinate = new Coordinates(i % 2 == 0 ? "g" : "g-prefix", "a" + (i % 31),
                        i % 3 == 0 ? "test-jar" : "jar", i % 3 == 0 ? "tests" : "");
                if (i % 4 != 0) expected.put(coordinate, "1");
                if (i % 13 == 0) allowed.put(coordinate, "reviewed\nreason");
                Resolved item = new Resolved(coordinate, random.nextBoolean() ? "1" : "2",
                        Origin.values()[random.nextInt(Origin.values().length)], "evidence" + random.nextInt(3));
                actual.add(item);
                if (i % 5 == 0) actual.add(item);
            }
            Collections.shuffle(actual, random);
            var diagnostics = List.of("z", "a\u2028next", "a\u2028next");
            // Reference the previous policy independently: deduplicate/sort all resolutions, then filter.
            List<Resolved> ordered = actual.stream().distinct().sorted(java.util.Comparator.comparing(Resolved::coordinates)
                    .thenComparing(Resolved::version).thenComparing(Resolved::evidence).thenComparing(Resolved::origin)).toList();
            List<Finding> findings = new java.util.ArrayList<>();
            int checked = 0;
            for (Resolved item : ordered) {
                String version = expected.get(item.coordinates());
                if (version == null) continue;
                checked++;
                if (!version.equals(item.version())) findings.add(new Finding(item.coordinates(), version, item.version(),
                        item.origin(), item.evidence(), allowed.get(item.coordinates())));
            }
            Report reference = new Report("4", findings, diagnostics.stream().distinct().sorted().toList(), checked);
            Report result = compare("4", expected, actual, allowed, diagnostics);
            assertEquals(reference, result, "round=" + round);
            assertEquals(reference.format(), result.format(), "round=" + round);
            assertEquals(reference.violation(), result.violation());
        }
    }

    @Test void sanitizationPreservesEveryUtf16CodeUnitAndSupplementaryCharacters() {
        var input = new StringBuilder("plain\ud83d\ude80");
        for (int c = 0; c <= Character.MAX_VALUE; c++) input.append((char) c);
        input.append("\ud800end\udc00");
        var reference = new StringBuilder();
        input.toString().codePoints().forEach(c -> {
            if (Character.isISOControl(c) || c == 0x2028 || c == 0x2029)
                reference.append(String.format(java.util.Locale.ROOT, "\\u%04x", c));
            else reference.appendCodePoint(c);
        });
        assertEquals(reference.toString(), safe(input.toString()));
        assertEquals("unknown", safe(null));
        assertEquals("", safe(""));
    }

    @Test void coordinateValidationKeepsTheExactAsciiTokenGrammar() {
        for (int c = 0; c < 256; c++) {
            String token = "a" + (char) c + "z";
            if (token.matches("[A-Za-z0-9_.+\\-]+"))
                assertEquals(token, new Coordinates(token, token, token, token).group());
            else assertThrows(IllegalArgumentException.class, () -> new Coordinates(token, "a", "jar", ""));
        }
        for (String token : List.of("ไทย", "é", "\u2028", "\ud83d\ude80", "\ud800", "\udc00"))
            assertThrows(IllegalArgumentException.class, () -> new Coordinates("g", token, "jar", ""));
    }

    @Test void collidingCoordinateHashesCannotMergeDifferentDependencies() {
        Map<Coordinates, String> expected = new java.util.TreeMap<>();
        List<Resolved> actual = new java.util.ArrayList<>();
        for (int i = 0; i < 256; i++) {
            var group = new StringBuilder();
            for (int bit = 0; bit < 8; bit++) group.append((i & (1 << bit)) == 0 ? "Aa" : "BB");
            Coordinates coordinate = new Coordinates(group.toString(), "library", "jar", "");
            expected.put(coordinate, "1");
            actual.add(new Resolved(coordinate, "2", Origin.DIRECT_OVERRIDE, "declared"));
        }
        assertEquals(1, expected.keySet().stream().map(Coordinates::hashCode).distinct().count());
        Report result = compare("4", expected, actual, Map.of(), List.of());
        assertEquals(256, result.checked());
        assertEquals(List.copyOf(expected.keySet()), result.findings().stream().map(Finding::coordinates).toList());
        Collections.reverse(actual);
        assertEquals(result, compare("4", expected, actual, Map.of(), List.of()));
    }
}
