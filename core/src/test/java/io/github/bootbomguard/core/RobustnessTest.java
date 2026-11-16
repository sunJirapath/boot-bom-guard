package io.github.bootbomguard.core;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static io.github.bootbomguard.core.Guard.*;
import static org.junit.jupiter.api.Assertions.*;

class RobustnessTest {
    @Test void emptyComparisonHasCanonicalPassOutput() {
        var result = compare("4.0.0", Map.of(), List.of(), Map.of(), List.of());
        assertEquals("boot-bom-guard BOM=4.0.0\nPASS checked=0 drift=0 unknown=0", result.format());
        assertEquals(0, result.checked());
        assertFalse(result.violation());
    }

    @Test void textFieldsRetainUnicodeAndEscapeMixedLineEndings() {
        var key = Coordinates.parse("g:library");
        String evidence = "\u0e44\u0e17\u0e22 \ud83d\ude00 \ud801\udc37 "
                + "\u05e9\u05dc\u05d5\u05dd\r\nsecond\nthird\rfinal";
        var result = compare("4.0.0", Map.of(key, "1"),
                List.of(new Resolved(key, "2", Origin.UNKNOWN_ORIGIN, evidence)), Map.of(), List.of());
        String output = result.format();
        assertTrue(output.contains("\u0e44\u0e17\u0e22 \ud83d\ude00 \ud801\udc37 "
                + "\u05e9\u05dc\u05d5\u05dd\\u000d\\u000asecond\\u000athird\\u000dfinal"), output);
        assertEquals(3, output.lines().count());
        assertFalse(output.contains("\r"));
    }

    @Test void bomPrefixAndLongTextRemainOrdinaryReportData() {
        var key = Coordinates.parse("g:library");
        String longEvidence = "x".repeat(128_000);
        var result = compare("\ufeff4.0.0", Map.of(key, "\ufeff1"),
                List.of(new Resolved(key, "\ufeff2", Origin.UNKNOWN_ORIGIN, longEvidence)), Map.of(), List.of());
        assertEquals(1, result.findings().size());
        assertTrue(result.format().contains("BOM=\ufeff4.0.0"));
        assertTrue(result.format().contains("evidence=" + longEvidence));
    }
}
