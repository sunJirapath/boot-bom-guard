# Shared-core performance — 2026-10-29

Compared with baseline `78ec45cea6eff504c250e0f6d55e65cd3f324007`, the optimized core preserves report bytes while reducing comparison, coordinate-validation and escaping allocations. Native Maven/Gradle resolution is outside these measurements.

## Changes

- Reuse the compiled coordinate token pattern; each call still uses its own matcher.
- Copy expected versions into a per-comparison hash index, deduplicate exact resolved records, count managed records, and sort only drift findings. The existing coordinate/resolved-version/evidence/origin order is preserved.
- Scan report text once, return unchanged strings directly, and write control-code hex digits without `String.format`. ISO controls and U+2028/U+2029 are still escaped; supplementary and unpaired surrogate code units are preserved.

No runtime dependency, public API, native resolver cache or cross-configuration baseline cache was added.

## Recorded results

Windows 11, Temurin JDK 21.0.11, single-threaded JVMs with `-Xms256m -Xmx256m -XX:+UseSerialGC`. The 20,000-coordinate probe uses five fresh JVMs per version, ten warmups per case/JVM, then 15 measured operations per case/JVM (75 samples). Launch order alternates. Values below are pooled medians per operation. Allocation is measured on the invoking thread using the JDK management counter; it is not retained/peak heap or process RSS.

| Case | Baseline ms | Optimized ms | Baseline allocated bytes | Optimized allocated bytes | Allocation reduction |
| --- | ---: | ---: | ---: | ---: | ---: |
| `compare_all_drift` | 25.035 | 21.627 | 47,552,728 | 25,938,336 | 45.5% |
| `compare_mixed` | 25.549 | 4.994 | 46,361,608 | 3,189,272 | 93.1% |
| `coordinates` | 12.492 | 3.636 | 69,039,960 | 9,519,960 | 86.2% |
| `format_controls` | 2.670 | 0.461 | 5,965,936 | 1,572,496 | 73.6% |
| `format_plain` | 0.847 | 0.547 | 1,791,456 | 855,248 | 52.3% |

The mixed input contains 20,000 unique coordinates: 25% unmanaged, 200 genuine drifts, and repeated exact entries at every seventh position; input order uses seed 729. It checks 15,000 distinct managed resolutions. The all-drift input checks all 20,000 coordinates. Formatting cases contain 1,500 findings; the control case includes escaped versions, evidence, reasons, BOM and diagnostics. Inputs are built outside the timed operations. Coordinate construction is measured separately.

Additional bounded sizes use the same seed and distributions (three fresh JVMs per version):

| Size / case | Baseline ms | Optimized ms | Allocation reduction |
| --- | ---: | ---: | ---: |
| 100 / `compare_mixed` | 0.2558 | 0.1054 | 87.6% |
| 100 / `compare_all_drift` | 0.2393 | 0.2577 | 42.3% |
| 100,000 / `compare_mixed` | 188.9072 | 30.2188 | 93.8% |
| 100,000 / `compare_all_drift` | 195.6083 | 166.2232 | 45.7% |

The 100-coordinate all-drift probe is about 0.018 ms slower in this run despite allocating less. These short timings include JIT/GC and host noise; no claim is made that every graph becomes faster. A hash-index copy adds temporary storage proportional to the BOM size. Sorting still costs O(d log d) for d drift findings; native resolution and coordinate rendering have separate costs.

Every baseline/optimized fork produced the same report SHA-256 for its size. [Recorded summaries](performance-results.json) include all sizes, exact source hashes (UTF-8 with LF line endings), JVM flags and output digests. Full samples and the baseline/working source diff are retained locally under ignored `build/performance/final-*.json`. The recorded working head identifies the parent revision; source hashes identify the measured uncommitted core changes.

## Reproduce

Requires Git with the baseline commit available, Python 3, and JDK 21 with thread allocation counters. No Maven/Gradle installation or external benchmark dependency is needed. Run while other builds are idle.

```sh
python scripts/benchmark_core.py --baseline 78ec45c --forks 5 --samples 15 --output build/performance/final-20000.json
python scripts/benchmark_core.py --baseline 78ec45c --size 100000 --output build/performance/final-100000.json
python scripts/benchmark_core.py --baseline 78ec45c --size 100 --samples 15 --output build/performance/final-100.json
```

The script compiles baseline sources from Git and current working sources into separate temporary directories. Its checks require every fork to produce the same digest and expected sample count. It fails if the policy output differs. Timings are opt-in evidence, not a CI timing threshold or an end-to-end build-speed guarantee.

## Correctness coverage

Six additional tests expand the suite from 89 to 95: 100 seeded differential graph comparisons against the previous policy, full UTF-16 escaping equivalence, exact coordinate grammar, 256 colliding coordinate hashes, native dense transitive conflicts (128 managed modules), and distinct Gradle configurations selecting different Boot BOM versions. Existing strict/exception/incomplete-analysis checks remain part of the full suites. See [VERIFICATION.md](VERIFICATION.md) for matrix results and the limits of earlier corpus replays.
