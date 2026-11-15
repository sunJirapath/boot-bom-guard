package io.github.bootbomguard.core;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

class RedactTest {
    @Test void redactsUrlCredentialsAndCommonSecrets() {
        String cause = Redact.cause(new RuntimeException(
                "https://user:pw@repo.example.com/x token=abc123 password: hunter2 Authorization: Bearer xyz"));
        assertTrue(cause.contains("https://***@repo.example.com/x"), cause);
        for (String secret : new String[]{"user", "pw", "abc123", "hunter2", "xyz"})
            assertFalse(cause.contains(secret), cause);
        assertTrue(cause.contains("token=***"), cause);
        assertTrue(cause.contains("password=***"), cause);
        assertTrue(cause.contains("Authorization=***"), cause);
    }

    @Test void redactsSecretsGluedToOtherNameCharacters() {
        String[][] cases = {
                {"access_token=abc123", "abc123", "access_token"},
                {"client_secret=s3cr3t", "s3cr3t", "client_secret"},
                {"secret_access_key=AKIAXYZ", "AKIAXYZ", "secret_access_key"},
                {"X-Api-Key: k9k9", "k9k9", "X-Api-Key"},
                {"db_password=pw77", "pw77", "db_password"},
                {"{\"password\":\"hunter9\"}", "hunter9", "password"}
        };
        for (String[] testCase : cases) {
            String cause = Redact.cause(new RuntimeException(testCase[0]));
            assertFalse(cause.contains(testCase[1]), cause);
            assertTrue(cause.contains(testCase[2]), cause);
        }
    }

    @Test void redactsBasicAuthorizationAndQuotedSecrets() {
        String cause = Redact.cause(new RuntimeException(
                "Authorization: Basic dXNlcjpwYXNz password=\"alpha beta\" token='gamma delta' {\"secret\":\"epsilon zeta\"}"));
        for (String secret : new String[]{"dXNlcjpwYXNz", "alpha", "beta", "gamma", "delta", "epsilon", "zeta"})
            assertFalse(cause.contains(secret), cause);
        for (String key : new String[]{"Authorization", "password", "token", "secret"})
            assertTrue(cause.contains(key + "=***"), cause);
    }

    @Test void redactsEscapedAndUnterminatedQuotedSecrets() {
        for (String message : new String[]{
                "password=\"alpha \\\"beta\\\" gamma\"",
                "password='alpha \\'beta\\' gamma'",
                "password=\"alpha beta",
                "password='alpha beta\\"}) {
            String cause = Redact.cause(new RuntimeException(message));
            assertTrue(cause.contains("password=***"), cause);
            for (String secret : new String[]{"alpha", "beta", "gamma"})
                assertFalse(cause.contains(secret), cause);
        }
    }

    @Test void truncatesSanitizedMessagesAtThreeHundredCharacters() {
        String cause = Redact.cause(new IllegalArgumentException("x".repeat(301)));
        String message = cause.substring(cause.indexOf(": ") + 2);
        assertEquals(303, message.length());
        assertTrue(message.endsWith("..."));
    }

    @Test void includesAtMostFiveCausesAndStopsOnCycles() {
        Throwable root = new IllegalStateException("root");
        Throwable middle = new IllegalArgumentException("middle", root);
        String chain = Redact.cause(new RuntimeException("top", middle));
        assertTrue(chain.indexOf("RuntimeException") < chain.indexOf("IllegalArgumentException"), chain);
        assertTrue(chain.indexOf("IllegalArgumentException") < chain.indexOf("IllegalStateException"), chain);

        Throwable nine = new RuntimeException("0");
        for (int i = 1; i < 9; i++) nine = new RuntimeException(Integer.toString(i), nine);
        String bounded = Redact.cause(nine);
        assertEquals(5, bounded.split(" <- caused by ", -1).length, bounded);
        assertTrue(bounded.endsWith("RuntimeException: 4"), bounded);

        CyclicException a = new CyclicException("a");
        CyclicException b = new CyclicException("b");
        a.next = b;
        b.next = a;
        assertEquals("CyclicException: a <- caused by CyclicException: b", Redact.cause(a));
    }

    @Test void handlesMissingMessagesNullInputAndControlCharacters() {
        assertEquals("IllegalStateException", Redact.cause(new IllegalStateException()));
        assertEquals("unknown", Redact.cause(null));
        String cause = Redact.cause(new RuntimeException("line1\nline2\u0001\u2028end"));
        assertFalse(cause.contains("\n"), cause);
        assertFalse(cause.contains("\u0001"), cause);
        assertFalse(cause.contains("\u2028"), cause);
        assertTrue(cause.contains("line1 line2\\u0001 end"), cause);
    }

    @Test void preservesHarmlessMessages() {
        assertEquals("RuntimeException: Could not find artifact g:a:jar:1",
                Redact.cause(new RuntimeException("Could not find artifact g:a:jar:1")));
    }

    @Test void preservesSecretLikeCoordinatesWithVersions() {
        for (String coordinate : new String[]{
                "org.springframework.boot:spring-boot-starter-oauth2-authorization-server 1.5.0",
                "org.springframework.security:spring-security-token 2.3.4",
                "com.example:db-password-provider 4.0.0"})
            assertEquals(coordinate, Guard.safe(coordinate));
    }

    @Test void doesNotRedactSecretLikeKeysFollowedBySpaceAndVersion() {
        for (String diagnostic : new String[]{"token 1.5.0", "password 1.5.0"}) {
            assertEquals(diagnostic, Guard.safe(diagnostic));
            assertFalse(Guard.safe(diagnostic).contains("=***"));
        }
    }

    @Test void continuesRedactingExplicitSchemesQuotedXmlAndUserInfoSecrets() {
        String[] cases = {
                "password=hunter2",
                "Authorization: Bearer bearerCredential",
                "Authorization: Basic basicCredential==",
                "Bearer standaloneCredential",
                "api_key: apiCredential",
                "password=\"escaped \\\"credential\\\" value\"",
                "password=\"unterminated credential",
                "<password>xmlCredential</password>",
                "https://user:urlCredential@host/path",
                "user:bareCredential@host"
        };
        String[] credentials = {
                "hunter2", "bearerCredential", "basicCredential==", "standaloneCredential", "apiCredential",
                "credential", "credential", "xmlCredential", "urlCredential", "bareCredential"
        };
        for (int i = 0; i < cases.length; i++) {
            String output = Redact.text(cases[i]);
            assertFalse(output.contains(credentials[i]), output);
            assertTrue(output.contains("***"), output);
        }
    }

    @Test void repeatedBareSecretLikeKeysCompleteWithoutBacktracking() {
        String input = "token ".repeat(100_000);
        assertTimeoutPreemptively(Duration.ofSeconds(2), () -> assertEquals(input, Redact.text(input)));
    }

    private static final class CyclicException extends Exception {
        private Throwable next;

        private CyclicException(String message) { super(message); }

        @Override public synchronized Throwable getCause() { return next; }
    }
}
