"""Source-install smoke checks with empty caches and consumers outside the checkout.

Run after the normal suites. Downloads dependencies; retained evidence is under build/.
Use --gradle PATH repeatedly to check additional installed Gradle distributions.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gradle", action="append", help="Gradle executable; defaults to the checked-in wrapper")
    args = parser.parse_args()
    for executable in args.gradle or []:
        if not pathlib.Path(executable).is_file() and not shutil.which(executable):
            parser.error(f"Gradle executable not found: {executable}")
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    evidence = pathlib.Path(tempfile.mkdtemp(prefix="install-smoke-", dir=build))
    # Use an OS temporary directory outside the source checkout.
    consumers = pathlib.Path(tempfile.mkdtemp(prefix="bbg-consumers-"))
    maven = shutil.which("mvn.cmd") or shutil.which("mvn")
    if not maven:
        raise RuntimeError("Maven must be on PATH")
    records = []

    def run(name, command, cwd, expected, fragments=()):
        print(f"Running {name}", flush=True)
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding="utf-8", errors="replace", timeout=900)
        (evidence / (name + ".log")).write_text(result.stdout, encoding="utf-8")
        if result.returncode != expected or any(fragment not in result.stdout for fragment in fragments):
            raise AssertionError(f"{name}: unexpected exit/report; see {evidence / (name + '.log')}")
        records.append(f"{name}: exit={result.returncode}; expected report verified")
        (evidence / "results.txt").write_text("\n".join(records) + "\n", encoding="utf-8")

    print(f"Evidence: {evidence}\nExternal consumers: {consumers}", flush=True)
    repository = evidence / "maven-repository"
    common = [maven, "-B", "-ntp", f"-Dmaven.repo.local={repository}"]
    run("maven-source-install", common + ["install"], ROOT, 0, ["BUILD SUCCESS"])
    consumer = consumers / "maven"
    consumer.mkdir()
    shutil.copy(ROOT / "fixtures/maven/aligned/pom.xml", consumer / "pom.xml")
    scenarios = [("aligned", ["-DbootBomGuard.failOnDrift=true"], 0, "PASS checked=1 drift=0 unknown=0"),
                 ("warning", ["-Pdirect"], 0, "WARN checked=1 drift=1 unknown=0"),
                 ("strict", ["-Pdirect", "-DbootBomGuard.failOnDrift=true"], 1, "policy failed"),
                 ("allowed", ["-Pallowlist", "-DbootBomGuard.failOnDrift=true"], 0, "ALLOWED org.slf4j:slf4j-api")]
    for name, flags, code, report in scenarios:
        run("maven-" + name, common + ["boot-bom-guard:check"] + flags, consumer, code, [report])

    default = ROOT / ("gradlew.bat" if os.name == "nt" else "gradlew")
    for index, executable in enumerate(args.gradle or [str(default)], 1):
        home = evidence / f"gradle-home-{index}"
        common = [executable, "--no-daemon", "--console=plain", "--gradle-user-home", str(home),
                  f"-PguardBuild={ROOT}", "bootBomGuard"]
        for dsl in ("groovy", "kotlin"):
            consumer = consumers / f"gradle-{index}-{dsl}"
            shutil.copytree(ROOT / "fixtures/gradle" / dsl, consumer,
                            ignore=shutil.ignore_patterns("build", ".gradle"))
            scenarios = [("allowed", [], 0, "ALLOWED org.slf4j:slf4j-api")] if dsl == "kotlin" else [
                ("aligned", ["-PfailOnDrift=true"], 0, "PASS checked=1 drift=0 unknown=0"),
                ("warning", ["-Pscenario=direct"], 0, "WARN checked=1 drift=1 unknown=0"),
                ("strict", ["-Pscenario=direct", "-PfailOnDrift=true"], 1, "policy failed"),
                ("allowed", ["-Pscenario=allowlist", "-PfailOnDrift=true"], 0, "ALLOWED org.slf4j:slf4j-api")]
            for name, flags, code, report in scenarios:
                run(f"gradle-{index}-{dsl}-{name}", common + flags, consumer, code, [report])
    print(f"PASS: {len(records)} commands; evidence retained at {evidence}", flush=True)


if __name__ == "__main__":
    main()
