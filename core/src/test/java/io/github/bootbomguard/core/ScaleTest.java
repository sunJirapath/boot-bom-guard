package io.github.bootbomguard.core;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static io.github.bootbomguard.core.Guard.*;
import static org.junit.jupiter.api.Assertions.*;

class ScaleTest {
    @Test void comparesAndFormatsTenThousandUniqueDependenciesWithinLimit() {
        assertTimeout(Duration.ofSeconds(60), () -> {
            Map<Coordinates, String> expected = new HashMap<>();
            List<Resolved> actual = new ArrayList<>();
            for (int i = 0; i < 10_000; i++) {
                var coordinate = new Coordinates("generated.group" + (i % 10), "module" + i, "jar", "");
                expected.put(coordinate, "1.0");
                actual.add(new Resolved(coordinate, "2.0", Origin.DIRECT_OVERRIDE, "generated"));
            }
            var result = compare("4.0.0", expected, actual, Map.of(), List.of());
            assertEquals(10_000, result.checked());
            assertEquals(10_000, result.findings().size());
            String first = result.format();
            assertTrue(first.startsWith("boot-bom-guard BOM=4.0.0\nDRIFT generated.group0:module0"));
            assertEquals(first, compare("4.0.0", expected, actual, Map.of(), List.of()).format());
        });
    }
}
