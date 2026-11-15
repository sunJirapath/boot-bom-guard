package io.github.bootbomguard.core;

import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class Redact {
    private static final Pattern URL_USERINFO = Pattern.compile("(//)[^/\\s]*@");
    private static final Pattern BARE_USERINFO = Pattern.compile("(^|[\\s=(\\[])[^\\s/:@=(\\[]++:[^\\s/@]*+@");
    private static final Pattern URL = Pattern.compile(
            "(?i)(?<![a-z0-9+.-])(?:(?:[a-z][a-z0-9+.-]*:)?//|\\*{3}@)[^\\s<>\"']+");
    private static final Pattern XML_SECRET = Pattern.compile(
            "(?is)(<(?:password|passwd|token|secret|authorization|api[-_]?key)[\\w-]*>)[^<]*");
    // Unterminated quoted values consume the rest of the message rather than expose a secret suffix.
    private static final Pattern SECRET = Pattern.compile(
            "(?is)(?<![\\w-])((?=[\\w-]*(?:password|passwd|token|secret|authorization|bearer|api[-_]?key))[\\w-]++)[\"']?\\s*(?:[=:]\\s*|\\s+(?=(?:basic|bearer)\\s+)|(?<=basic)\\s+|(?<=bearer)\\s+)"
                    + "(?:(?:basic|bearer)\\s+)?(?:\"(?:\\\\.|[^\"\\\\])*+(?:\"|\\\\?\\z)"
                    + "|'(?:\\\\.|[^'\\\\])*+(?:'|\\\\?\\z)|\\S+)");
    // A dotted group id makes group:artifact[:version] or group:artifact version a coordinate, not a key/value pair.
    private static final Pattern COORDINATE = Pattern.compile(
            "(?<![\\w.-])[\\w-]+(?:\\.[\\w-]+)+:[\\w.-]+(?::[\\w.-]+|\\s+[\\w.-]+)?");
    private static final Pattern WHITESPACE = Pattern.compile("(?U)\\s+");

    private Redact() {}

    public static String text(String value) {
        value = URL_USERINFO.matcher(value).replaceAll("$1***@");
        value = BARE_USERINFO.matcher(value).replaceAll("$1***@");
        // Encoded query keys and opaque fragments can carry secrets without a recognizable key name.
        value = URL.matcher(value).replaceAll(match -> {
            String url = match.group();
            int query = url.indexOf('?'), fragment = url.indexOf('#');
            int suffix = query < 0 ? fragment : fragment < 0 ? query : Math.min(query, fragment);
            return Matcher.quoteReplacement(suffix < 0 ? url : url.substring(0, suffix + 1) + "***");
        });
        value = XML_SECRET.matcher(value).replaceAll("$1***");
        Matcher secrets = SECRET.matcher(value);
        Matcher coordinates = COORDINATE.matcher(value);
        StringBuilder redacted = new StringBuilder(value.length());
        int copied = 0;
        int coordinateEnd = -1;
        while (secrets.find()) {
            while (coordinateEnd < secrets.start() && coordinates.find()) coordinateEnd = coordinates.end();
            if (coordinateEnd >= secrets.end() && coordinates.start() <= secrets.start()) continue;
            redacted.append(value, copied, secrets.start()).append(secrets.group(1)).append("=***");
            copied = secrets.end();
        }
        return redacted.append(value, copied, value.length()).toString();
    }

    public static String cause(Throwable t) {
        if (t == null) return "unknown";
        try {
            Set<Throwable> seen = Collections.newSetFromMap(new IdentityHashMap<>());
            StringBuilder result = new StringBuilder();
            for (int links = 0; t != null && links < 5 && seen.add(t); links++) {
                if (!result.isEmpty()) result.append(" <- caused by ");
                result.append(t.getClass().getSimpleName());
                String message = t.getMessage();
                if (message != null && !message.isBlank()) {
                    message = text(message);
                    message = WHITESPACE.matcher(message).replaceAll(" ").trim();
                    if (message.length() > 300) message = message.substring(0, 300) + "...";
                    result.append(": ").append(message);
                }
                if (links < 4) t = t.getCause();
            }
            return Guard.safe(result.toString());
        } catch (Throwable ignored) {
            return "unknown";
        }
    }
}
