package io.github.bootbomguard.core;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static io.github.bootbomguard.core.Guard.*;
import static org.junit.jupiter.api.Assertions.*;

class SecurityBoundaryTest {
    private final Coordinates key = Coordinates.parse("g:library");

    @Test void credentialExfiltrationThroughEveryReportFieldIsRedacted() {
        // Kills removing redaction from Guard.safe, even when no exception reaches Redact.cause.
        String hostile = "https://user:repoCredential@host/x?access%5Ftoken=queryCredential#fragmentCredential "
                + "Authorization: Bearer headerCredential password='quoted Credential'";
        var report = compare(hostile, Map.of(key, "expected " + hostile),
                List.of(new Resolved(key, "resolved " + hostile, Origin.UNKNOWN_ORIGIN, "evidence " + hostile)),
                Map.of(key, "reason " + hostile), List.of("diagnostic " + hostile));
        String output = report.format();
        for (String secret : List.of("repoCredential", "queryCredential", "fragmentCredential",
                "headerCredential", "quoted", "Credential")) assertFalse(output.contains(secret), output);
        assertTrue(output.contains("ALLOWED g:library expected="), output);
        assertTrue(report.violation(), "Redaction must not clear incomplete-analysis diagnostics");
        assertEquals("resolved " + hostile, report.findings().get(0).resolved());
    }

    @Test void encodedAndSchemlessUrlCredentialAttacksAreRedacted() {
        // Kills restricting URL userinfo to :// and relying only on recognizable query key names.
        for (String input : List.of("HTTPS://u:p%40encoded@[::1]/x?%74oken=opaqueCredential",
                "//u:schemeCredential@[::1]/x?%74oken=opaqueCredential", "mirror=(u:bareCredential@repo.example/x#opaqueCredential)",
                "https://u:firstCredential@secondCredential@host/x", "https://host/x#opaqueCredential",
                "<password>xml Credential with spaces</password>")) {
            String output = Redact.cause(new RuntimeException(input));
            for (String secret : List.of("p%40encoded", "opaqueCredential", "schemeCredential",
                    "bareCredential", "firstCredential", "secondCredential", "xml Credential"))
                assertFalse(output.contains(secret), output);
            assertTrue(output.contains("***"), output);
        }
    }

    @Test void workflowCommandAnsiAndNewlineInjectionCannotCreateReportLines() {
        // Kills removing the control-character loop in Guard.safe; commands must stay inside a data line.
        String attack = "\r\n::error::forged\u001b[2J\u0085::warning::forged\u2028PASS\u2029";
        String output = compare("4" + attack, Map.of(key, "1" + attack),
                List.of(new Resolved(key, "2" + attack, Origin.DIRECT_OVERRIDE, "<b>[x](javascript:x)" + attack)),
                Map.of(key, "review" + attack), List.of("failure" + attack)).format();
        assertEquals(4, output.lines().count(), output);
        assertFalse(output.lines().anyMatch(line -> line.startsWith("::") || line.startsWith("PASS")), output);
        assertFalse(output.chars().anyMatch(c -> c != '\n' && (Character.isISOControl(c) || c == 0x2028 || c == 0x2029)));
        assertTrue(output.contains("\\u001b[2J"), output);
        // The documented sink is plain text; HTML/Markdown is not rendered by the guard.
        assertTrue(output.contains("<b>[x](javascript:x)"), output);
    }

    @Test void coordinateTraversalControlAndUnicodeLookalikeAttacksAreRejected() {
        // Kills replacing Coordinates.token validation with unchecked metadata passthrough.
        for (String attack : List.of("../escape:a", "g:../escape", "g:a/../../x", "g:a\\..\\x",
                "g:a\n::error::x", "g:a\u001b[31m", "g:а", ":a", "g:"))
            assertThrows(IllegalArgumentException.class, () -> Coordinates.parse(attack), attack);
        var error = assertThrows(IllegalArgumentException.class,
                () -> Coordinates.parse("https://user:invalidCoordinateCredential@host/a"));
        assertFalse(error.getMessage().contains("invalidCoordinateCredential"));
    }

    @Test void aliasDuplicateAndLookalikeAllowlistAttacksCannotHideDrift() {
        // Kills explicit-type validation, duplicate normalization, exact matching, reason checks, or unmatched diagnostics.
        var aliases = new LinkedHashMap<String, String>();
        aliases.put("g:library", "first");
        aliases.put("g:library:jar:", "second");
        assertThrows(IllegalArgumentException.class, () -> exceptions(aliases));
        assertThrows(IllegalArgumentException.class, () -> exceptions(Map.of("g:library", "\r\n\t")));
        assertThrows(IllegalArgumentException.class, () -> exceptions(Map.of("g:librаry", "lookalike")));
        for (String malformed : List.of("g:library::", "g:library: :", "g:library:\n:", "g:library:\u000b:"))
            assertThrows(IllegalArgumentException.class, () -> exceptions(Map.of(malformed, "reviewed")), malformed);
        var result = compare("4", Map.of(key, "1"),
                List.of(new Resolved(key, "2", Origin.UNKNOWN_ORIGIN, "selected")),
                exceptions(Map.of("g:library:test-jar:tests", "wrong variant")), List.of());
        assertTrue(result.violation());
        assertNull(result.findings().get(0).reason());
        assertTrue(result.diagnostics().stream().anyMatch(d -> d.startsWith("Unmatched exception")));
    }

    @Test void oversizedCoordinateAndQuotedSecretAttacksStayBoundedAndKeepEvidence() {
        // Kills recursive quoted/Boot-qualifier regexes and backtracking coordinate/URL/key scans.
        assertTimeoutPreemptively(Duration.ofSeconds(10), () -> {
            String large = "a".repeat(100_000);
            assertEquals(large, new Coordinates("g", large, "jar", "").artifact());
            assertThrows(IllegalArgumentException.class, () -> Coordinates.parse("g:" + large + "!"));
            String output = Redact.cause(new RuntimeException("password=\"" + large + "\" retained"));
            assertTrue(output.contains("password=***"), output);
            assertTrue(output.endsWith("retained"), output);
            assertFalse(output.contains("aaaa"), output);
            String repeatedKey = "token".repeat(20_000);
            assertEquals(repeatedKey, safe(repeatedKey));
            String repeatedScheme = "a://".repeat(20_000) + "end";
            assertEquals(repeatedScheme, safe(repeatedScheme));
            String deepQualifier = "4.0.0-" + "a.".repeat(20_000) + "a";
            assertTrue(supportedBootVersion(deepQualifier));
            assertFalse(supportedBootVersion(deepQualifier + "!"));
        });
    }

    @Test void hugeAllowlistAndDuplicateGraphAttacksDoNotLoseTheUnacceptedFinding() {
        // Kills treating the presence of any exception as a global exemption or skipping unseen coordinates.
        var allowed = new LinkedHashMap<String, String>();
        for (int i = 0; i < 5_000; i++) allowed.put("g:unused" + i, "reviewed");
        var actual = new ArrayList<Resolved>();
        for (int i = 0; i < 10_000; i++) actual.add(new Resolved(key, "2", Origin.UNKNOWN_ORIGIN, "selected"));
        var result = compare("4", Map.of(key, "1"), actual, exceptions(allowed), List.of());
        assertTrue(result.violation());
        assertEquals(1, result.checked());
        assertEquals(1, result.findings().size());
        assertNull(result.findings().get(0).reason());
        assertEquals(allowed.size(), result.diagnostics().size());
    }
}
