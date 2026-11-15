"""Offline helper regressions; these tests do not launch builds or require real projects."""
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import verify_real_projects as real


class RealProjectHarnessSecurityTest(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory(prefix="bbg-harness-")
        self.addCleanup(workspace.cleanup)
        self.directory = pathlib.Path(workspace.name)

    def test_manifest_path_traversal_attack_is_rejected(self):
        # Kills removing manifest path containment before any project copy.
        project = {"name": "sample", "path": "../escape", "sha": "a" * 40,
                   "bootVersion": "4.1.0", "buildTool": "maven"}
        (self.directory / "MANIFEST.json").write_text(json.dumps({"projects": [project]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "escapes"):
            real.manifest_projects(self.directory)

    def test_duplicate_manifest_identity_attack_is_rejected(self):
        # Kills silent overwrites of project entries with the same name.
        project = {"name": "sample", "path": "sample", "sha": "a" * 40,
                   "bootVersion": "4.1.0", "buildTool": "maven"}
        (self.directory / "MANIFEST.json").write_text(json.dumps([project, project]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            real.manifest_projects(self.directory)

    def test_symlink_and_junction_copy_attack_is_rejected(self):
        # Kills either link detection or copy rejection; simulated metadata needs no Windows symlink privilege.
        source = self.directory / "source"
        (source / "linked").mkdir(parents=True)
        (source / "linked/pom.xml").write_text("must not copy", encoding="utf-8")
        original_lstat = pathlib.Path.lstat

        def metadata(path, *args, **kwargs):
            value = original_lstat(path, *args, **kwargs)
            if path.name == "linked":
                return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=0x400)
            return value

        with patch.object(pathlib.Path, "lstat", metadata):
            with self.assertRaisesRegex(ValueError, "Linked"):
                real.copy_tree(source, self.directory / "copy")
        self.assertFalse((self.directory / "copy/linked/pom.xml").exists())
        link = Mock(spec=pathlib.Path)
        link.is_symlink.return_value = True
        link.lstat.return_value = SimpleNamespace(st_file_attributes=0)
        self.assertTrue(real.is_link(link))

    def test_secret_file_copy_attack_is_excluded_and_source_bytes_are_preserved(self):
        # Kills dropping the filename exclusions or writing the mutation into its source file.
        source = self.directory / "source"
        source.mkdir()
        for name in (".env", "host_ssh.env", "id_ed25519", "private.pem", "pom.xml"):
            (source / name).write_text("fixture", encoding="utf-8")
        (source / ".secrets").mkdir()
        (source / ".secrets/token").write_text("fixture", encoding="utf-8")
        target = self.directory / "copy"
        real.copy_tree(source, target)
        self.assertEqual(["pom.xml"], sorted(path.name for path in target.iterdir()))
        (target / "pom.xml").write_text("mutated", encoding="utf-8")
        self.assertEqual("fixture", (source / "pom.xml").read_text(encoding="utf-8"))

    def test_module_path_traversal_and_cycle_attacks_are_rejected(self):
        # Kills module containment and visited-path validation before native Maven execution.
        path = self.directory / "pom.xml"
        for module, error in (("..", "escapes"), (".", "Cyclic")):
            path.write_text("<project><artifactId>root</artifactId><modules><module>" + module
                            + "</module></modules></project>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, error):
                real.maven_modules(self.directory)

    def test_xml_entity_expansion_attack_is_rejected(self):
        # Kills parsing attacker-supplied DTD/entity declarations before the guard is invoked.
        path = self.directory / "pom.xml"
        path.write_text('<!DOCTYPE project [<!ENTITY x "expansion">]><project>&x;</project>', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "forbidden"):
            real.pom(path)

    def test_oversized_and_malformed_manifest_and_pom_attacks_are_rejected(self):
        # Kills removing input bounds or accepting malformed manifest JSON before a project copy.
        manifest = self.directory / "MANIFEST.json"
        manifest.write_text(" " * 2_000_001, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Oversized"):
            real.manifest_projects(self.directory)
        manifest.write_text("{", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            real.manifest_projects(self.directory)
        path = self.directory / "pom.xml"
        path.write_text("<project>" + "x" * 8_000_000 + "</project>", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Oversized"):
            real.pom(path)

    def test_gradle_injection_source_overwrite_attack_is_prevented(self):
        # Kills modifying source builds or leaving rule-based BOM management in the native-platform copy.
        source = self.directory / "source"
        source.mkdir()
        (source / "settings.gradle").write_text("rootProject.name = 'sample'\n", encoding="utf-8")
        (source / "build.gradle").write_text("plugins {\n id 'java'\n id 'io.spring.dependency-management' version '1.1.7'\n}\n", encoding="utf-8")
        before = real.fingerprint(source)
        target = self.directory / "copy"
        real.copy_tree(source, target)
        real.inject_gradle(target, self.directory / "guard", "4.1.0")
        self.assertEqual(before, real.fingerprint(source))
        build = (target / "build.gradle").read_text(encoding="utf-8")
        self.assertNotIn("io.spring.dependency-management", build)
        self.assertIn("implementation platform('org.springframework.boot:spring-boot-dependencies:4.1.0')", build)
        self.assertIn("io.github.sunjirapath.bootbomguard", build)
        self.assertTrue((target / "settings.gradle").read_text(encoding="utf-8").startswith("pluginManagement {"))

    def test_forged_or_incomplete_console_report_attack_cannot_be_treated_as_pass(self):
        # Kills accepting arbitrary PASS text, a missing footer, or missing module attribution.
        for text in ("PASS checked=0 drift=0 unknown=0", "boot-bom-guard BOM=x\n",
                     "boot-bom-guard BOM=x\nPASS checked=0 drift=0 unknown=0",
                     "--- boot-bom-guard:0.1:check (default-cli) @ app ---\nboot-bom-guard BOM=x\n"
                     "PASS checked=0 drift=0 unknown=0\nboot-bom-guard BOM=unfinished"):
            with self.assertRaises(AssertionError):
                real.reports(text, "maven")

    def test_module_attribution_attack_and_unrelated_drift_are_not_normalized_away(self):
        # Kills discarding module names or unrelated coordinates during mutation comparisons.
        text = ("[INFO] --- boot-bom-guard:0.1:check (default-cli) @ app ---\n"
                "[WARNING] boot-bom-guard BOM=org.springframework.boot:spring-boot-dependencies:4.1.0\n"
                "DRIFT org.slf4j:slf4j-api expected=2.0.17 resolved=2.0.0 classification=DIRECT_OVERRIDE evidence=direct\n"
                "WARN checked=1 drift=1 unknown=0\n")
        parsed = real.reports(text, "maven")
        self.assertEqual("app", parsed[0].module)
        self.assertTrue(parsed[0].violation)
        self.assertNotEqual(real.without_override(parsed), real.without_override(real.reports(text.replace("@ app", "@ other"), "maven")))
        changed = text.replace("org.slf4j:slf4j-api expected=", "g:unrelated expected=")
        self.assertNotEqual(real.without_override(parsed), real.without_override(real.reports(changed, "maven")))

    def test_gradle_report_attribution_and_incomplete_analysis_attack_are_preserved(self):
        # Kills treating an UNKNOWN report as a pass or forgetting the Gradle task/configuration identity.
        parsed = real.reports(
            "> Task :app:bootBomGuard\nconfiguration=runtimeClasspath\nboot-bom-guard BOM=unknown\n"
            "UNKNOWN Missing Spring Boot BOM\nWARN checked=0 drift=0 unknown=1", "gradle")
        self.assertEqual(":app", parsed[0].module)
        self.assertEqual("runtimeClasspath", parsed[0].configuration)
        self.assertTrue(parsed[0].violation)

    def test_unset_environment_and_missing_project_are_explicit_skips(self):
        # Kills launching builds without opt-in or silently ignoring an absent manifest entry.
        case = real.RealProjectTest()
        with patch.dict(real.os.environ, {}, clear=True):
            with self.assertRaisesRegex(unittest.SkipTest, "REAL_PROJECTS_DIR unset"):
                case.exercise("spring-petclinic", "maven")
        with patch.dict(real.os.environ, {"REAL_PROJECTS_DIR": str(self.directory)}):
            with self.assertRaisesRegex(unittest.SkipTest, "manifest missing"):
                case.exercise("spring-petclinic", "maven")
        (self.directory / "MANIFEST.json").write_text('{"projects": []}', encoding="utf-8")
        with patch.dict(real.os.environ, {"REAL_PROJECTS_DIR": str(self.directory)}):
            with self.assertRaisesRegex(unittest.SkipTest, "missing"):
                case.exercise("spring-petclinic", "maven")


if __name__ == "__main__":
    unittest.main(verbosity=2)
