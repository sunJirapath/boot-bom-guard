import io.github.bootbomguard.core.Coordinates;
import io.github.bootbomguard.core.Guard;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.function.Supplier;

/** Opt-in, single-threaded core probe; native resolver/startup time is excluded. */
public class PerformanceProbe {
    private static volatile Object sink;
    public static void main(String[] args) throws Exception {
        int size = Integer.parseInt(args[0]);
        int samples = Integer.parseInt(args[1]);
        Map<Coordinates, String> expected = new TreeMap<>();
        List<Guard.Resolved> mixed = new ArrayList<>(), allDrift = new ArrayList<>();
        for (int i = 0; i < size; i++) {
            Coordinates key = new Coordinates("org.fixture", "module-" + i, "jar", "");
            if (i % 4 != 0) expected.put(key, "1");
            var resolved = new Guard.Resolved(key, i % 100 == 1 ? "2" : "1",
                    Guard.Origin.TRANSITIVE_DRIFT, "native selection");
            mixed.add(resolved);
            if (i % 7 == 0) mixed.add(resolved);
            allDrift.add(new Guard.Resolved(key, "2", Guard.Origin.DIRECT_OVERRIDE, "declared"));
        }
        Collections.shuffle(mixed, new Random(729));
        Collections.shuffle(allDrift, new Random(729));
        Map<Coordinates, String> fullExpected = new TreeMap<>();
        allDrift.forEach(r -> fullExpected.put(r.coordinates(), "1"));
        var plain = Guard.compare("4", fullExpected, allDrift.subList(0, Math.min(size, 1500)), Map.of(), List.of());
        var escapedFindings = plain.findings().stream().map(f -> new Guard.Finding(f.coordinates(), "1\n", "2\u001b",
                f.origin(), "evidence\u2028next", "reviewed\u0000")).toList();
        var escaped = new Guard.Report("4\n", escapedFindings, List.of("diagnostic\u2029"), plain.checked());
        String proof = Guard.compare("4", expected, mixed, Map.of(), List.of("z", "a", "a")).format()
                + Guard.compare("4", fullExpected, allDrift, Map.of(), List.of()).format()
                + plain.format() + escaped.format();
        System.out.println("{\"digest\":\"" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(proof.getBytes(StandardCharsets.UTF_8))) + "\"}");
        measure("coordinates", samples, () -> {
            List<Coordinates> result = new ArrayList<>(size);
            for (int i = 0; i < size; i++) result.add(new Coordinates("org.fixture", "module-" + i, "jar", ""));
            return result;
        });
        measure("compare_mixed", samples, () -> Guard.compare("4", expected, mixed, Map.of(), List.of()));
        measure("compare_all_drift", samples, () -> Guard.compare("4", fullExpected, allDrift, Map.of(), List.of()));
        measure("format_plain", samples, plain::format);
        measure("format_controls", samples, escaped::format);
    }
    private static void measure(String name, int samples, Supplier<?> action) {
        var bean = ManagementFactory.getPlatformMXBean(com.sun.management.ThreadMXBean.class);
        if (bean == null || !bean.isThreadAllocatedMemorySupported())
            throw new IllegalStateException("Thread allocation counters are required");
        bean.setThreadAllocatedMemoryEnabled(true);
        long thread = Thread.currentThread().threadId();
        for (int i = 0; i < 10; i++) sink = action.get();
        for (int i = 0; i < samples; i++) {
            long bytes = bean.getThreadAllocatedBytes(thread), start = System.nanoTime();
            sink = action.get();
            long elapsed = System.nanoTime() - start;
            long allocated = bean.getThreadAllocatedBytes(thread) - bytes;
            System.out.printf(Locale.ROOT, "{\"case\":\"%s\",\"ns\":%d,\"bytes\":%d}%n", name, elapsed, allocated);
        }
    }
}
