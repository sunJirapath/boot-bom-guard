"""Compare an immutable Git baseline and the working core, without runtime dependencies.

Requires JDK 21, Git and Python 3. Run outside other builds for useful timing.
This is an opt-in microbenchmark, not a CI timing gate or a native build benchmark.
"""
import argparse
import hashlib
import json
import platform
import pathlib
import statistics
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(*command):
    return subprocess.check_output(command, cwd=ROOT, text=True, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="Git revision to compile alongside working core")
    parser.add_argument("--size", type=int, default=20000)
    parser.add_argument("--forks", type=int, default=3)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "build/performance/results.json")
    args = parser.parse_args()
    if min(args.size, args.forks, args.samples) <= 0:
        parser.error("size, forks and samples must be positive")
    baseline = run("git", "rev-parse", "--verify", args.baseline + "^{commit}").strip()
    source_dir = "core/src/main/java"
    sources = run("git", "ls-tree", "-r", "--name-only", baseline, source_dir).splitlines()
    sources = [name for name in sources if name.endswith(".java")]
    if not sources:
        raise RuntimeError("Baseline has no core Java sources")
    records = {"baseline": [], "working": []}
    digests = set()
    with tempfile.TemporaryDirectory(prefix="guard-performance-") as folder:
        folder = pathlib.Path(folder)
        classes = {}
        for variant in records:
            classes[variant] = folder / variant / "classes"
            classes[variant].mkdir(parents=True)
            files = []
            for name in sources if variant == "baseline" else sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                    for p in (ROOT / source_dir).rglob("*.java")):
                target = folder / variant / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(run("git", "show", baseline + ":" + name) if variant == "baseline"
                                  else (ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
                files.append(str(target))
            run("javac", "--release", "21", "-d", str(classes[variant]), *files,
                str(ROOT / "scripts/PerformanceProbe.java"))
        # Alternate order to reduce systematic warm-machine bias; each invocation is a fresh JVM.
        for fork in range(args.forks):
            for variant in (list(records) if fork % 2 == 0 else list(reversed(records))):
                output = run("java", "-Xms256m", "-Xmx256m", "-XX:+UseSerialGC", "-cp", str(classes[variant]),
                             "PerformanceProbe", str(args.size), str(args.samples))
                rows = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
                digests.add(rows[0]["digest"])
                assert len(rows) == 1 + 5 * args.samples, output
                records[variant].extend(dict(row, fork=fork) for row in rows[1:])
    assert len(digests) == 1, "Baseline and working reports differ: " + repr(digests)
    summary = {}
    for case in sorted({row["case"] for row in records["baseline"]}):
        summary[case] = {}
        for variant, rows in records.items():
            selected = [row for row in rows if row["case"] == case]
            summary[case][variant] = {"median_ms": statistics.median(row["ns"] for row in selected) / 1e6,
                                      "median_allocated_bytes": statistics.median(row["bytes"] for row in selected)}
    result = {"baseline": baseline, "working_head": run("git", "rev-parse", "HEAD").strip(),
              "working_diff": run("git", "diff", "--", source_dir),
              "working_source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                                        for p in sorted((ROOT / source_dir).rglob("*.java"))},
              "source_hash_normalization": "UTF-8 LF",
              "host": platform.platform(), "jvm_flags": ["-Xms256m", "-Xmx256m", "-XX:+UseSerialGC"],
              "java": run("java", "--version"), "size": args.size, "forks": args.forks,
              "samples_per_fork": args.samples, "sha256": next(iter(digests)), "summary": summary, "raw": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("PASS: identical report SHA-256; evidence:", args.output)


if __name__ == "__main__":
    main()
