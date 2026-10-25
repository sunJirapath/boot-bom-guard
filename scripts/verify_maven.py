"""Real Maven resolution checks. Run `mvn install` first; --offline reuses Maven's cache."""
import pathlib
import shutil
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAVEN = shutil.which("mvn.cmd") or shutil.which("mvn")
OFFLINE = "--offline" in sys.argv
if OFFLINE:
    sys.argv.remove("--offline")


class MavenIntegrationTest(unittest.TestCase):
    def run_fixture(self, fixture="aligned", profile=None, fail=False, expected_failure=False, extra=()):
        self.assertIsNotNone(MAVEN, "Maven must be on PATH")
        args = [MAVEN, "-B", "-ntp", "-f", str(ROOT / "fixtures/maven" / fixture / "pom.xml"), "boot-bom-guard:check"]
        if OFFLINE:
            args.append("--offline")
        if profile:
            args.append("-P" + profile)
        if fail:
            args.append("-DbootBomGuard.failOnDrift=true")
        args.extend(extra)
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(result.returncode != 0, expected_failure, result.stdout)
        return result.stdout

    def test_aligned(self):
        self.assertIn("PASS checked=1 drift=0 unknown=0", self.run_fixture(fail=True))

    def test_explicit_override_warning(self):
        out = self.run_fixture(profile="direct")
        self.assertIn("expected=2.0.17 resolved=2.0.18 classification=DIRECT_OVERRIDE", out)
        self.assertIn("WARN checked=1 drift=1 unknown=0", out)

    def test_managed_override(self):
        self.assertIn("classification=MANAGED_OVERRIDE", self.run_fixture(profile="managed"))

    def test_transitive_override(self):
        out = self.run_fixture(fixture="transitive")
        self.assertIn("org.slf4j:slf4j-api expected=2.0.17 resolved=2.0.18", out)
        self.assertIn("classification=MANAGED_OVERRIDE", out)
        self.assertIn("path=transitive", out)

    def test_boot_parent_property_override_uses_pristine_bom(self):
        self.assertIn("expected=2.0.17 resolved=2.0.18 classification=MANAGED_OVERRIDE", self.run_fixture(fixture="parent"))

    def test_intentional_exception(self):
        out = self.run_fixture(profile="allowlist", fail=True)
        self.assertIn("ALLOWED org.slf4j:slf4j-api", out)
        self.assertIn("reason=Reviewed logging upgrade", out)
        self.assertIn("PASS checked=1 drift=1 unknown=0", out)

    def test_missing_bom(self):
        self.assertIn("UNKNOWN Missing Spring Boot BOM", self.run_fixture(fixture="missing"))

    def test_profile_override_selects_effective_bom(self):
        out = self.run_fixture(profile="profile-override", fail=True)
        self.assertIn("BOM=org.springframework.boot:spring-boot-dependencies:4.0.1", out)
        self.assertIn("PASS", out)

    def test_ambiguous_effective_sources(self):
        self.assertIn("Ambiguous Spring Boot BOM", self.run_fixture(fixture="ambiguous"))

    def test_ci_failure(self):
        self.assertIn("policy failed", self.run_fixture(profile="direct", fail=True, expected_failure=True))

    def test_unknown_fails_ci(self):
        self.assertIn("policy failed", self.run_fixture(fixture="missing", fail=True, expected_failure=True))

    def test_blank_reason_rejected(self):
        self.assertIn("Invalid bootBomGuard exceptions", self.run_fixture(profile="invalid-exception", expected_failure=True))

    def test_verbose_graph_omits_conflict_losers(self):
        out = self.run_fixture(profile="verbose-conflict", extra=("-Daether.conflictResolver.verbose=true",))
        self.assertIn("WARN checked=2 drift=1 unknown=0", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
