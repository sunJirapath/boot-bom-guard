"""Real Maven resolution checks. Run `mvn install` first; --offline reuses Maven's cache."""
import hashlib
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from contextlib import contextmanager

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAVEN = shutil.which("mvn.cmd") or shutil.which("mvn")
OFFLINE = "--offline" in sys.argv
if OFFLINE:
    sys.argv.remove("--offline")


@contextmanager
def snapshot_repository(metadata=True, local_copy=False):
    """A file repository resolved by Maven itself; no mutable public snapshots or graph mocks."""
    identity = uuid.uuid4().hex
    group = "guard.fixture.snapshot." + identity
    bom_version = "4.99.0-guard-fixture-" + identity
    latest = "1.0-20261020.120000-2"
    older = "1.0-20261019.120000-1"
    tests = "1.0-20261021.120000-3"
    with tempfile.TemporaryDirectory(prefix="guard-snapshots-") as directory:
        repository = pathlib.Path(directory)

        def publish(group_id, artifact, version, dependencies="", management=""):
            base = "1.0-SNAPSHOT" if version.startswith("1.0-") else version
            folder = repository / group_id.replace(".", "/") / artifact / base
            folder.mkdir(parents=True, exist_ok=True)
            pom = (f'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
                   f'<groupId>{group_id}</groupId><artifactId>{artifact}</artifactId><version>{base}</version>'
                   f'{management}<dependencies>{dependencies}</dependencies></project>')
            (folder / f"{artifact}-{version}.pom").write_text(pom, encoding="utf-8")
            with zipfile.ZipFile(folder / f"{artifact}-{version}.jar", "w"):
                pass
            return folder

        def dependency(artifact, version="1.0-SNAPSHOT", variant=""):
            return (f'<dependency><groupId>{group}</groupId><artifactId>{artifact}</artifactId>'
                    f'<version>{version}</version>{variant}</dependency>')

        variant = '<type>test-jar</type><classifier>tests</classifier>'
        managed = dependency("direct") + dependency("transitive") + dependency("direct", variant=variant)
        publish("org.springframework.boot", "spring-boot-dependencies", bom_version,
                management=f'<dependencyManagement><dependencies>{managed}</dependencies></dependencyManagement>')
        publish(group, "carrier", "1", dependencies=dependency("transitive"))
        for artifact in ("direct", "transitive"):
            folder = publish(group, artifact, older)
            publish(group, artifact, "1.0-SNAPSHOT" if local_copy else latest)
            classifier_version = "1.0-SNAPSHOT" if local_copy else tests
            with zipfile.ZipFile(folder / f"{artifact}-{classifier_version}-tests.jar", "w"):
                pass
            if metadata:
                versions = "".join(
                    f'<snapshotVersion>{classifier}<extension>{extension}</extension>'
                    f'<value>{value}</value><updated>20261021120000</updated></snapshotVersion>'
                    for extension, classifier, value in (
                        ("pom", "", "1.0-SNAPSHOT" if local_copy else latest),
                        ("jar", "", "1.0-SNAPSHOT" if local_copy else latest),
                        ("jar", "<classifier>tests</classifier>", classifier_version)))
                (folder / "maven-metadata.xml").write_text(
                    f'<metadata><groupId>{group}</groupId><artifactId>{artifact}</artifactId><version>1.0-SNAPSHOT</version>'
                    f'<versioning><lastUpdated>20261021120000</lastUpdated><snapshotVersions>{versions}</snapshotVersions>'
                    f'</versioning></metadata>', encoding="utf-8")
        for file in list(repository.rglob("*")):
            if file.is_file():
                file.with_name(file.name + ".sha1").write_text(hashlib.sha1(file.read_bytes()).hexdigest(), encoding="ascii")
        yield (f"-Dsnapshot.repository={repository.as_uri()}", f"-Dsnapshot.group={group}",
               f"-Dsnapshot.bom.version={bom_version}", "--offline", "-Daether.offline.protocols=file"), older


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

    def test_unresolved_dependency_warns_and_fails_ci(self):
        # Warm only the real baseline so a nonexistent dependency fails deterministically without network access.
        self.run_fixture(fail=True)
        out = self.run_fixture(profile="unresolved", extra=("--offline",))
        self.assertIn("UNKNOWN Maven model/dependency resolution failed (DependencyResolutionException)", out)
        self.assertIn("WARN checked=0 drift=0 unknown=1", out)
        self.assertNotIn("PASS checked=", out)
        failure = self.run_fixture(profile="unresolved", fail=True, expected_failure=True, extra=("--offline",))
        self.assertIn("UNKNOWN Maven model/dependency resolution failed", failure)
        self.assertIn("policy failed", failure)

    def test_duplicate_normalized_exception_is_rejected(self):
        self.assertIn("Invalid bootBomGuard exceptions",
                      self.run_fixture(profile="duplicate-exception", expected_failure=True))

    def test_timestamped_snapshots_align_in_warning_and_strict_modes(self):
        with snapshot_repository() as (flags, _):
            for strict in (False, True):
                out = self.run_fixture("snapshot", fail=strict, extra=flags)
                self.assertIn("PASS checked=3 drift=0 unknown=0", out)

    def test_snapshot_identity_without_metadata_is_unknown(self):
        with snapshot_repository(metadata=False, local_copy=True) as (flags, older):
            # Concrete requests resolve without alias metadata; the BOM alias cannot be identified.
            flags += (f"-Dsnapshot.version={older}",)
            for strict in (False, True):
                out = self.run_fixture("snapshot", fail=strict, expected_failure=strict, extra=flags)
                self.assertIn("UNKNOWN Maven model/dependency resolution failed", out)
                self.assertNotIn("DRIFT ", out)
                self.assertNotIn("PASS checked=", out)

    def test_non_unique_snapshot_aliases_still_align(self):
        with snapshot_repository(local_copy=True) as (flags, _):
            out = self.run_fixture("snapshot", fail=True, extra=flags)
            self.assertIn("PASS checked=3 drift=0 unknown=0", out)


class MavenSnapshotIntegrationTest(unittest.TestCase):
    """Frozen file-repository snapshots; native resolution warms the offline guard cases."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="bbg-snapshots-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = pathlib.Path(cls.temporary.name)
        cls.repository = cls.directory / "repository"
        unique = uuid.uuid4().hex
        cls.group = "guard.snapshot.fixture." + unique
        cls.bom = "4.0.0-bbg-" + unique
        cls.old = "1.0-20261024.010203-1"
        cls.current = "1.0-20261025.010203-2"
        cls.other = "2.0-20261025.010203-2"

        def publish(group, name, version, resolved=None, dependencies="", packaging="jar"):
            directory = cls.repository / group.replace(".", "/") / name / version
            directory.mkdir(parents=True, exist_ok=True)
            stem = name + "-" + (resolved or version)
            (directory / (stem + ".pom")).write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
                f'<groupId>{group}</groupId><artifactId>{name}</artifactId><version>{version}</version>'
                f'<packaging>{packaging}</packaging>{dependencies}</project>', encoding="utf-8")
            if packaging == "jar":
                with zipfile.ZipFile(directory / (stem + ".jar"), "w") as jar:
                    jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")

        def dependency(name, version=None, variant=""):
            return (f'<dependency><groupId>{cls.group}</groupId><artifactId>{name}</artifactId>'
                    + (f'<version>{version}</version>' if version else "") + variant + '</dependency>')

        for name, base, current in [("direct", "1.0-SNAPSHOT", cls.current),
                                    ("transitive", "1.0-SNAPSHOT", cls.current),
                                    ("direct", "2.0-SNAPSHOT", cls.other)]:
            for resolved in ([cls.old, current] if base == "1.0-SNAPSHOT" else [current]):
                publish(cls.group, name, base, resolved)
            directory = cls.repository / cls.group.replace(".", "/") / name / base
            entries = ''.join(f'<snapshotVersion><extension>{ext}</extension><value>{current}</value>'
                              '<updated>20261025010203</updated></snapshotVersion>' for ext in ["pom", "jar"])
            (directory / "maven-metadata.xml").write_text(
                f'<metadata><groupId>{cls.group}</groupId><artifactId>{name}</artifactId><version>{base}</version>'
                '<versioning><snapshot><timestamp>20261025.010203</timestamp><buildNumber>2</buildNumber></snapshot>'
                f'<lastUpdated>20261025010203</lastUpdated><snapshotVersions>{entries}</snapshotVersions></versioning></metadata>', encoding="utf-8")
        for version in ["1.0", "2.0"]:
            publish(cls.group, "release", version)
        variants = ['<type>java-source</type>', '<type>ejb-client</type>', '<type>pom</type>', '<type>zip</type>']
        for version in ["1.0", "2.0"]:
            publish(cls.group, "typed", version)
            folder = cls.repository / cls.group.replace(".", "/") / "typed" / version
            for suffix in ["-sources.jar", "-client.jar", ".zip"]:
                with zipfile.ZipFile(folder / ("typed-" + version + suffix), "w"):
                    pass
        (cls.repository / cls.group.replace(".", "/") / "release" / "maven-metadata.xml").write_text(
            '<metadata><groupId>' + cls.group + '</groupId><artifactId>release</artifactId>'
            '<versioning><latest>2.0</latest><release>2.0</release><versions><version>1.0</version><version>2.0</version>'
            '</versions><lastUpdated>20261025010203</lastUpdated></versioning></metadata>', encoding="utf-8")
        publish(cls.group, "relocated", "2.0")
        publish(cls.group, "legacy", "2.0", packaging="pom", dependencies=
                '<distributionManagement><relocation><groupId>' + cls.group
                + '</groupId><artifactId>relocated</artifactId><version>2.0</version></relocation></distributionManagement>')
        publish(cls.group, "bridge", "1.0", dependencies='<dependencies>' + dependency("transitive", "1.0-SNAPSHOT") + '</dependencies>')
        managed = dependency("direct", "1.0-SNAPSHOT") + dependency("transitive", "1.0-SNAPSHOT") + dependency("release", "1.0") + dependency("legacy", "1.0") + "".join(dependency("typed", "1.0", variant) for variant in variants)
        publish("org.springframework.boot", "spring-boot-dependencies", cls.bom,
                dependencies='<dependencyManagement><dependencies>' + managed + '</dependencies></dependencyManagement>', packaging="pom")
        profiles = []
        for name, artifact, version, management in [("older", "direct", cls.old, False),
                                                    ("latest", "direct", cls.current, False),
                                                    ("managed-older", "direct", cls.old, True),
                                                    ("managed-snapshot", "direct", "2.0-SNAPSHOT", True),
                                                    ("mixed", "release", "2.0", False),
                                                    ("relocation", "legacy", "2.0", False)]:
            content = '<dependencies>' + dependency(artifact, version) + '</dependencies>'
            if management:
                content = '<dependencyManagement>' + content + '</dependencyManagement>'
            profiles.append(f'<profile><id>{name}</id>{content}</profile>')
        for profile, version in [("variants-aligned", "1.0"), ("variants-override", "2.0")]:
            profiles.append('<profile><id>' + profile + '</id><dependencies>'
                            + ''.join(dependency("typed", version, variant) for variant in variants) + '</dependencies></profile>')
        system_jar = cls.repository / cls.group.replace(".", "/") / "release" / "2.0" / "release-2.0.jar"
        profiles.append('<profile><id>system</id><dependencies>' + dependency("release", "2.0",
                        '<scope>system</scope><systemPath>' + system_jar.as_posix() + '</systemPath>') + '</dependencies></profile>')
        profiles.append('<profile><id>range</id><dependencies>' + dependency("release", "[1.0,2.0]") + '</dependencies></profile>')
        (cls.directory / "pom.xml").write_text(
            '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
            '<groupId>guard.fixture</groupId><artifactId>snapshot-consumer</artifactId><version>1</version>'
            '<repositories><repository><id>bbg-frozen-snapshots</id>'
            f'<url>{cls.repository.as_uri()}</url><snapshots><enabled>true</enabled></snapshots></repository></repositories>'
            '<dependencyManagement><dependencies><dependency><groupId>org.springframework.boot</groupId>'
            f'<artifactId>spring-boot-dependencies</artifactId><version>{cls.bom}</version><type>pom</type><scope>import</scope>'
            '</dependency></dependencies></dependencyManagement><dependencies>'
            + dependency("direct") + dependency("bridge", "1.0") + dependency("release") + '</dependencies>'
            '<profiles>' + ''.join(profiles) + '</profiles></project>', encoding="utf-8")
        # File repositories still require online Resolver mode once; no public snapshot or wall-clock metadata is used.
        for profile in [None, "older", "latest", "managed-older", "managed-snapshot", "mixed", "relocation", "variants-aligned", "variants-override", "system", "range"]:
            native = cls.maven(["org.apache.maven.plugins:maven-dependency-plugin:3.10.0:resolve"], profile, offline=False)
            if native.returncode:
                raise AssertionError(native.stdout)

    @classmethod
    def maven(cls, goals, profile=None, strict=False, offline=OFFLINE):
        args = [MAVEN, "-B", "-ntp", "-f", str(cls.directory / "pom.xml")] + goals
        if profile:
            args.append("-P" + profile)
        if strict:
            args.append("-DbootBomGuard.failOnDrift=true")
        if offline:
            args.append("--offline")
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace", timeout=180)

    def guard(self, profile=None, strict=False, expected_exit=0):
        run = self.maven(["io.github.bootbomguard:boot-bom-guard-maven-plugin:0.1.0-SNAPSHOT:check"], profile, strict)
        self.assertEqual(run.returncode, expected_exit, run.stdout)
        return run.stdout

    def test_aligned_aliases_include_direct_and_transitive_artifacts(self):
        self.assertIn("PASS checked=3 drift=0 unknown=0", self.guard(strict=True))

    def test_explicit_current_timestamp_is_the_selected_alias(self):
        self.assertIn("PASS checked=3 drift=0 unknown=0", self.guard("latest", strict=True))

    def test_explicit_older_timestamp_remains_direct_drift(self):
        out = self.guard("older")
        self.assertIn(f"expected={self.current} resolved={self.old} classification=DIRECT_OVERRIDE", out)
        self.assertIn("WARN checked=3 drift=1 unknown=0", out)
        self.guard("older", strict=True, expected_exit=1)

    def test_managed_older_timestamp_remains_managed_drift(self):
        out = self.guard("managed-older")
        self.assertIn(f"expected={self.current} resolved={self.old} classification=MANAGED_OVERRIDE", out)
        self.assertIn("WARN checked=3 drift=1 unknown=0", out)
        self.guard("managed-older", strict=True, expected_exit=1)

    def test_managed_snapshot_override_keeps_native_origin(self):
        out = self.guard("managed-snapshot")
        self.assertIn(f"expected={self.current} resolved={self.other} classification=MANAGED_OVERRIDE", out)
        self.assertIn("WARN checked=3 drift=1 unknown=0", out)
        self.guard("managed-snapshot", strict=True, expected_exit=1)

    def test_relocation_cannot_silently_drop_a_managed_coordinate(self):
        out = self.guard("relocation")
        self.assertIn("UNKNOWN Unsupported Maven dependency relocation", out)
        self.assertNotIn("PASS checked=", out)
        self.guard("relocation", strict=True, expected_exit=1)

    def test_native_types_and_implicit_classifiers_align(self):
        self.assertIn("PASS checked=7 drift=0 unknown=0", self.guard("variants-aligned", strict=True))

    def test_native_types_and_implicit_classifiers_detect_overrides(self):
        out = self.guard("variants-override")
        for suffix in ["java-source:sources", "ejb-client:client", "pom:", "zip:"]:
            self.assertIn(f"DRIFT {self.group}:typed:{suffix} expected=1.0 resolved=2.0", out)
        self.assertIn("WARN checked=7 drift=4 unknown=0", out)
        self.guard("variants-override", strict=True, expected_exit=1)

    def test_system_scope_keeps_its_declared_native_version(self):
        out = self.guard("system")
        self.assertIn(f"DRIFT {self.group}:release expected=1.0 resolved=2.0", out)
        self.guard("system", strict=True, expected_exit=1)

    def test_native_bounded_range_is_compared_to_exact_bom(self):
        out = self.guard("range")
        self.assertIn(f"DRIFT {self.group}:release expected=1.0 resolved=2.0", out)
        self.guard("range", strict=True, expected_exit=1)

    def test_mixed_graph_reports_only_genuine_release_drift(self):
        out = self.guard("mixed")
        self.assertIn(f"DRIFT {self.group}:release expected=1.0 resolved=2.0 classification=DIRECT_OVERRIDE", out)
        self.assertIn("WARN checked=3 drift=1 unknown=0", out)
        self.guard("mixed", strict=True, expected_exit=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
