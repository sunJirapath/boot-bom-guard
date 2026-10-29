# 100-repository investigation — 2026-10-26

All 100 catalog repositories were pinned, inspected and given a native dependency-resolution attempt. The 26 previously blocked candidates were revisited using original wrappers, matching JDKs and native sibling-module bootstraps. No target upstream was modified or pushed; no Spring Boot migration was attempted.

Current candidate outcomes: **30 aligned**, **12 genuine drift**, **57 expected unsupported**, **1 baseline/artifact blocked**. Unsupported and blocked candidates are not successful integrations. [One row per candidate](results.csv), [actual scenario coverage](coverage-matrix.md), [remaining blockers](blocked-candidates.md).

**BBG-001 is fixed:** all 202 false SNAPSHOT findings disappeared across the five affected repositories; their native graphs were unchanged and all three genuine Gateway drifts remained. The six frozen SNAPSHOT regressions fail before the fix and pass after it. Product verification passed 58 distinct tests (12 core, 21 Maven, 25 Gradle), online and with the warmed offline cache. [Defect, reproduction and proof](bugs.md).

| Catalog tier | Selected tool | Candidates | Aligned | Genuine drift | Unsupported | Blocked |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Small | Maven | 19 | 7 | 1 | 11 | 0 |
| Small | Gradle | 6 | 0 | 0 | 6 | 0 |
| Medium | Maven | 13 | 6 | 0 | 7 | 0 |
| Medium | Gradle | 12 | 0 | 1 | 11 | 0 |
| Large | Maven | 22 | 9 | 1 | 12 | 0 |
| Large | Gradle | 3 | 0 | 2 | 1 | 0 |
| Huge | Maven | 24 | 8 | 7 | 8 | 1 |
| Huge | Gradle | 1 | 0 | 0 | 1 | 0 |

## Provenance and method

Original guard: `137b0026e3fd24952a0aa5eccc8a89b448196e16` (`0.1.0-SNAPSHOT`). The source-equivalent upstream update was `0c5888db559e174ee8f70d99969730ba1e6bcef0`. Fixed guard: `f961d07815c68afea08d63aada9baf754b771b65`. Each CSV row identifies its actual guard pin; this does not claim all 100 original baselines were rerun with the fix. [Source/test provenance](evidence/provenance.json).

The pilot selected four repositories per catalog tier before scaling. Independent Maven truth uses effective models, resolved JSON trees and actual artifact resolution. The expected model comes from a separately built pristine Boot BOM, without consumer property overrides. Gradle truth uses original wrapper resolution of all four classpaths; a separate plain Java Gradle project validates the platform expected versions. A metadata-only tree is never treated as proof that required JARs exist.

Public third-party builds ran only in resource-limited containers (3 GiB, 2 CPUs, 512 PIDs, dropped capabilities). No host credentials, personal Maven/Gradle settings, Docker socket, databases or application services were mounted. Caches and toolchains were isolated. Bootstraps used the unchanged native source and `install -DskipTests`; that is prerequisite preparation, not an application-test pass. Exact image digests, full command arrays, exits and timings are included in the evidence bundles.

Original proof is under `evidence/baseline/NNN.json` with its adjacent `.log`. New attempts are under `evidence/revisit/NNN.json`; fixed-bug repeats are under `evidence/fix/NNN.json`. A JSON bundle is keyed by the original relative evidence filename, including every recorded command. XML models are represented by their original SHA-256 and normalized dependency-management entries. Logs and patches are consolidated in the adjacent text file; cookie header noise is omitted and trailing whitespace is trimmed. [Source hashes and bundle keys](source-manifest.json). Raw XML, frozen caches and disposable clones remain local. The supplied catalog is [test-plan.md](test-plan.md).

## Coverage boundaries

Final follow-up on 2026-10-29: Maven offline install, all 21 Maven integration tests and Gradle 8.14.3 offline check passed again on merge commit `51aa970` (58 distinct tests, no failures or skips). [Current-run metadata and counts](evidence/final-validation-20261029.json), [logs](evidence/final-validation-20261029.log). The native GeoServer resolver was refreshed with `-U` and still could not find `org.geoserver:gs-main:3.1.0-CLOUD-SNAPSHOT`; the guard was not invoked for that blocked attempt.

The report validator checks all 100 pinned clone contents, source hashes, evidence links and supported-outcome oracles/exits. It enables Git long-path support on Windows. Six GeoServer status flags refer to files whose bytes exactly match their pinned blobs; no candidate source was restored or changed during this follow-up. Historical runners under `harness/` retain their original local paths, Docker cache names and toolchain assumptions; they require explicit path/cache setup on another machine and are not a portable one-command rerun.

Catalog tiers retain 25 candidates each. Measured sizes describe the selected module, not repository popularity or build-file counts. Whole-reactor measurements report each module graph separately and the aggregate workload; none establishes a single graph above 1,500 nodes. Default reactors also contain BOM/aggregation modules without a Boot BOM: their UNKNOWN result is expected and is not counted as a supported module pass. Strict root-reactor checks can therefore fail before reaching consumers; use consumer-only execution when that is the intended scope.

Every reported executed scenario has direct evidence in [coverage.csv](coverage.csv). No candidate completed every possible requested scenario. Existing product tests are distinct from external coverage. Application tests/services, Boot migrations, cold-cache offline reliability, production memory, comprehensive mirror/proxy behavior and exhaustive configuration-cache/constraint/substitution permutations were not tested. The credential sentinel probes do not establish universal exception-message redaction. Mutable public SNAPSHOT repositories can prevent exact historical downloads; frozen repository fixtures make the product regressions repeatable.

## Matched offline reactor performance

A warm-up pair is excluded; three measured pairs alternate native-first/guard-first. Each run has an identical per-module graph fingerprint. Elapsed includes process/container startup. Peak RSS is sampled from the Maven JVM VmHWM every 50 ms, not whole-container or host memory.

| Repo | Module graphs | Sum selected nodes | Largest module | Native median s | Guard median s | Native RSS MiB | Guard RSS MiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| #100 | 12 | 977 | 176 | 2.985 | 3.609 | 173.16 | 222.02 |

These are local overhead observations on the measured default reactors, without a production performance guarantee. Per-run data and graph hashes are in the corresponding revisit bundle.
