package io.github.bootbomguard.core;

import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;
import java.util.regex.Pattern;

public final class Redact {
    private static final Pattern URL_USERINFO = Pattern.compile("://[^/@\\s]+@");
    private static final Pattern SECRET = Pattern.compile(
            "(?i)((?:password|passwd|token|secret|authorization|bearer|api[-_]?key)[\\w-]*)\\s*[=:]?\\s*(?:bearer\\s+)?\\S+");
    private static final Pattern WHITESPACE = Pattern.compile("(?U)\\s+");

    private Redact() {}

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
                    message = URL_USERINFO.matcher(message).replaceAll("://***@");
                    message = SECRET.matcher(message).replaceAll("$1=***");
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
