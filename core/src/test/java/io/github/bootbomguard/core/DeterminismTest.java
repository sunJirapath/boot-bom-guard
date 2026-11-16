package io.github.bootbomguard.core;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;

import static io.github.bootbomguard.core.Guard.*;
import static org.junit.jupiter.api.Assertions.*;

class DeterminismTest {
    private static String report() {
        Coordinates a = Coordinates.parse("org.example:alpha");
        Coordinates b = Coordinates.parse("org.example:beta");
        return compare("4.0.0", Map.of(a, "1", b, "2"),
                List.of(new Resolved(a, "3", Origin.DIRECT_OVERRIDE, "first"),
                        new Resolved(b, "4", Origin.TRANSITIVE_DRIFT, "second")),
                Map.of(), List.of("diagnostic")).format();
    }

    @Test void repeatedFormattingIsByteIdentical() {
        assertEquals(report(), report());
        assertArrayEquals(report().getBytes(java.nio.charset.StandardCharsets.UTF_8),
                report().getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }

    @Test void concurrentComparisonsProduceIdenticalReports() throws Exception {
        String expected = report();
        var workers = Executors.newFixedThreadPool(8);
        try {
            var results = workers.invokeAll(java.util.Collections.nCopies(64,
                    (java.util.concurrent.Callable<String>) DeterminismTest::report));
            for (var result : results) assertEquals(expected, result.get());
        } finally {
            workers.shutdownNow();
        }
    }

    @Test void outputDoesNotDependOnDefaultLocaleOrTimezone() {
        var originalLocale = java.util.Locale.getDefault();
        var originalTimezone = java.util.TimeZone.getDefault();
        try {
            String expected = report();
            for (var locale : List.of(java.util.Locale.forLanguageTag("tr-TR"),
                    java.util.Locale.forLanguageTag("th-TH"))) {
                java.util.Locale.setDefault(locale);
                java.util.TimeZone.setDefault(java.util.TimeZone.getTimeZone("Pacific/Kiritimati"));
                assertEquals(expected, report(), locale.toString());
            }
        } finally {
            java.util.Locale.setDefault(originalLocale);
            java.util.TimeZone.setDefault(originalTimezone);
        }
    }
}
