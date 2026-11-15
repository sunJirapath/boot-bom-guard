"""Opt-in, offline checks on temporary copies of MANIFEST.json projects.

Install the Maven plugin and warm native dependency/plugin caches separately first.
Only installed executables are used; project wrappers are never executed.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[1]
COORDINATE = "org.slf4j:slf4j-api"
OVERRIDE = "2.0.0"  # Published leaf module; Boot 3.5/4.x manage a different version.
URL_SECRET = "bbg-planted-url-credential-39e71"
TOKEN_SECRET = "bbg-planted-token-credential-48b62"
PROBE_URL = f"https://user:{URL_SECRET}@bbg-probe.invalid/repository?token={TOKEN_SECRET}"
EXPECTED = {
    "spring-petclinic": ("maven", "gradle"),
    "spring-petclinic-boot35": ("maven", "gradle"),
    "spring-petclinic-rest": ("maven",),
    "spring-petclinic-microservices": ("maven",),
    "piggymetrics": ("maven",),
}
IGNORED = {".git", ".github", ".gradle", "build", "target", "node_modules"}
OPTIONS = argparse.Namespace(maven=None, gradle=None, maven_cache=None, gradle_cache=None)


def excluded(path):
    name = path.name.lower()
    return (name in {".env", ".secrets", ".ssh", "private_key"} or name.startswith(".env.") or name.endswith("_ssh.env")
            or name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
            or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".jks", ".ppk", ".asc", ".der", ".keystore"})


def is_link(path):
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def files_under(source, project=True):
    """Reject links/junctions instead of following them into a source tree or cache."""
    source = pathlib.Path(source)
    if is_link(source):
        raise ValueError("Linked source directories are unsupported")
    for folder, directories, files in os.walk(source, followlinks=False):
        base = pathlib.Path(folder)
        directories[:] = sorted(name for name in directories
                                if (not project or name not in IGNORED) and not excluded(base / name))
        for name in directories:
            if is_link(base / name):
                raise ValueError("Linked directories are unsupported")
        for name in sorted(files):
            path = base / name
            if excluded(path) or name.endswith(".lock") or (project and name in IGNORED):
                continue
            if is_link(path) or not stat.S_ISREG(path.stat().st_mode):
                raise ValueError("Linked or special files are unsupported")
            yield path


def copy_tree(source, target, project=True):
    if not source.is_dir():
        raise ValueError("Source checkout/cache directory is missing")
    target.mkdir(parents=True, exist_ok=True)
    for path in files_under(source, project):
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)  # Copy bytes, never permissions or links.


def fingerprint(source):
    return {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files_under(source)}


def inside(root, path):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Project/module path escapes its root")
    return resolved


def manifest_projects(directory):
    path = inside(directory, directory / "MANIFEST.json")
    if path.stat().st_size > 2_000_000:
        raise ValueError("Oversized manifest")
    data = json.loads(path.read_text(encoding="utf-8"))
    projects = data["projects"] if isinstance(data, dict) else data
    if not isinstance(projects, list) or len(projects) > 1_000:
        raise ValueError("Manifest must contain a bounded project list")
    result = {}
    for project in projects:
        name = project["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+", name) or name in result:
            raise ValueError("Invalid or duplicate manifest project name")
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", project["sha"]):
            raise ValueError("Manifest must supply a pinned SHA")
        if not re.fullmatch(r"[0-9A-Za-z.-]+", project["bootVersion"]):
            raise ValueError("Invalid manifest Boot version")
        raw = pathlib.Path(project["path"])
        source = raw if raw.is_absolute() else directory / raw
        inside(directory, source)
        result[name] = dict(project, source=source)
    return result


def pom(path):
    data = path.read_bytes()
    if len(data) > 8_000_000 or re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I):
        raise ValueError("Oversized POM or forbidden XML declaration")
    root = ET.fromstring(data, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    namespace = root.tag.partition("}")[0] + "}" if root.tag.startswith("{") else ""
    return root, namespace


def child(parent, name, namespace):
    found = parent.find(namespace + name)
    return found if found is not None else ET.SubElement(parent, namespace + name)


def write_pom(path, root, namespace):
    if namespace:
        ET.register_namespace("", namespace[1:-1])
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def maven_modules(project):
    result, visited = {}, set()

    def visit(path):
        path = inside(project, path)
        if path in visited:
            raise ValueError("Cyclic or repeated Maven module path")
        visited.add(path)
        root, ns = pom(path)
        name = root.findtext(ns + "artifactId")
        if name in result:
            raise ValueError("Duplicate Maven module artifactId")
        result[name] = path
        for module in root.findall(ns + "modules/" + ns + "module"):
            target = path.parent / module.text.strip()
            visit(target if target.suffix == ".xml" else target / "pom.xml")

    visit(project / "pom.xml")
    return result


def inject_maven(project):
    parent, ns = pom(ROOT / "pom.xml")
    adapter, ans = pom(ROOT / "maven-plugin/pom.xml")
    group, version = parent.findtext(ns + "groupId"), parent.findtext(ns + "version")
    artifact = adapter.findtext(ans + "artifactId")
    path = project / "pom.xml"
    root, ns = pom(path)
    plugins = child(child(root, "build", ns), "plugins", ns)
    plugin = ET.SubElement(plugins, ns + "plugin")
    for name, value in (("groupId", group), ("artifactId", artifact), ("version", version)):
        ET.SubElement(plugin, ns + name).text = value
    write_pom(path, root, ns)
    return f"{group}:{artifact}:{version}:check"


def mutate_maven(path, probe=False):
    root, ns = pom(path)
    dependencies = child(root, "dependencies", ns)
    if probe:
        dependency = ET.SubElement(dependencies, ns + "dependency")
        fields = (("groupId", "bbg.real.security"), ("artifactId", "deliberately-missing"), ("version", "1"))
        repositories = child(root, "repositories", ns)
        repository = ET.Element(ns + "repository")
        repositories.insert(0, repository)
        ET.SubElement(repository, ns + "id").text = "bbg-credential-probe"
        ET.SubElement(repository, ns + "url").text = PROBE_URL
    else:
        dependency = next((item for item in dependencies if item.findtext(ns + "groupId") == "org.slf4j"
                           and item.findtext(ns + "artifactId") == "slf4j-api"), None)
        if dependency is None:
            dependency = ET.SubElement(dependencies, ns + "dependency")
        fields = (("groupId", "org.slf4j"), ("artifactId", "slf4j-api"), ("version", OVERRIDE))
    for name, value in fields:
        child(dependency, name, ns).text = value
    write_pom(path, root, ns)


def inject_gradle(project, guard, boot):
    build = project / "build.gradle"
    settings = project / "settings.gradle"
    if not build.is_file() or not settings.is_file():
        raise ValueError("Expected manifest Gradle projects use Groovy build/settings files")
    text = build.read_text(encoding="utf-8")
    # Replace implicit rule-based BOM management only in this copy; the guard supports native platforms.
    text = re.sub(r"(?m)^\s*id\s+['\"]io\.spring\.dependency-management['\"]\s+version\s+['\"][^'\"]+['\"]\s*$", "", text)
    text, count = re.subn(r"\bplugins\s*\{", "plugins {\n  id 'io.github.sunjirapath.bootbomguard'", text, count=1)
    if count != 1:
        raise ValueError("Missing Gradle plugins block")
    include = "includeBuild(" + json.dumps(guard.as_posix()) + ")"
    original = settings.read_text(encoding="utf-8")
    if re.search(r"\bpluginManagement\s*\{", original):
        original = re.sub(r"\bpluginManagement\s*\{", "pluginManagement {\n" + include, original, count=1)
    else:
        original = "pluginManagement { " + include + " }\n" + original
    settings.write_text(original, encoding="utf-8")
    # Keep the real dependency declarations, with the same Boot version supplied by a native platform.
    text += "\n" + f"""
dependencies {{ implementation platform('org.springframework.boot:spring-boot-dependencies:{boot}') }}
bootBomGuard {{
    configurations = ['runtimeClasspath']
    failOnDrift = providers.gradleProperty('bbgStrict').isPresent()
}}
if (providers.gradleProperty('bbgOverride').isPresent()) {{
    dependencies {{ implementation('org.slf4j:slf4j-api') {{ version {{ strictly '{OVERRIDE}' }} }} }}
}}
repositories {{ maven {{ name = 'bbg-credential-probe'; url = uri('{PROBE_URL}') }} }}
configurations.runtimeClasspath.incoming.beforeResolve {{
    if (providers.gradleProperty('bbgCredentialProbe').isPresent())
        throw new GradleException('repository={PROBE_URL} Authorization: Bearer {TOKEN_SECRET}')
}}
"""
    build.write_text(text, encoding="utf-8")


def repository_secrets(project):
    result = {URL_SECRET, TOKEN_SECRET}
    for path in files_under(project):
        if path.name != "pom.xml" and not path.name.startswith(("settings", "build.gradle", "gradle.properties")):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"https?://([^/\s:@]+):([^/\s@]+)@", text, re.I):
            result.update((match[2], urllib.parse.unquote(match[2])))
        for match in re.finditer(r"(?i)(?:password|token|secret|api[-_]?key)[\w.-]*\s*[=:>]\s*[\"']?([^\s<\"']+)", text):
            value = match[1]
            if len(value) >= 8 and not any(c in value for c in "${}()"):
                result.add(value)
    return result


@dataclass(frozen=True)
class Report:
    module: str
    configuration: str
    lines: tuple

    @property
    def violation(self):
        return self.lines[-1].startswith("WARN ")


def reports(output, tool):
    result, current, configuration, block = [], "", "", None
    for raw in output.splitlines():
        line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw)
        line = re.sub(r"^\[(?:INFO|WARNING|WARN|ERROR|DEBUG)\]\s*", "", line).strip()
        module = re.search(r"--- .*?:check .*? @ (\S+) ---", line)
        task = re.fullmatch(r"> Task (\S*):bootBomGuard(?: FAILED)?", line)
        if tool == "maven" and module:
            current = module[1]
        if tool == "gradle" and task:
            current = task[1] or ":"
        if line.startswith("configuration="):
            configuration = line[len("configuration="):]
        if line.startswith("boot-bom-guard BOM="):
            if block is not None:
                raise AssertionError("Unterminated report")
            block = [line]
        elif block is not None and (line.startswith(("UNKNOWN ", "DRIFT ", "ALLOWED "))
                                    or re.fullmatch(r"(?:PASS|WARN) checked=\d+ drift=\d+ unknown=\d+", line)):
            block.append(line)
            if line.startswith(("PASS ", "WARN ")):
                if not current:
                    raise AssertionError("Report has no module/task attribution")
                result.append(Report(current, configuration, tuple(block)))
                block = None
    if block is not None or not result:
        raise AssertionError("Missing or incomplete console report; check offline prerequisites")
    return tuple(result)


def without_override(items):
    return tuple((item.module, item.configuration, tuple(line for line in item.lines[:-1]
                  if not line.startswith(("DRIFT " + COORDINATE + " ", "ALLOWED " + COORDINATE + " ")))) for item in items)


class RealProjectTest(unittest.TestCase):
    def exercise(self, name, tool):
        value = os.environ.get("REAL_PROJECTS_DIR")
        if not value:
            self.skipTest("REAL_PROJECTS_DIR unset; opt-in real-project checks skipped")
        directory = pathlib.Path(value).resolve()
        if not (directory / "MANIFEST.json").is_file():
            self.skipTest("REAL_PROJECTS_DIR manifest missing; real projects unavailable")
        project = manifest_projects(directory).get(name)
        if project is None or not project["source"].is_dir():
            self.skipTest(f"{name} missing from manifest or checkout")
        if tool not in project["buildTool"].split("+"):
            self.skipTest(f"{name}: {tool} build missing from manifest")
        build_file = "pom.xml" if tool == "maven" else "build.gradle"
        if not (project["source"] / build_file).is_file():
            self.skipTest(f"{name}: {build_file} missing from checkout")
        executable = (OPTIONS.maven or shutil.which("mvn.cmd") or shutil.which("mvn")) if tool == "maven" else (
            OPTIONS.gradle or shutil.which("gradle.bat") or shutil.which("gradle"))
        self.assertIsNotNone(executable, f"Install {tool} on PATH, or supply --{tool}")
        before = fingerprint(project["source"])
        workspace = tempfile.TemporaryDirectory(prefix="bbg-real-")
        self.addCleanup(workspace.cleanup)
        temporary = pathlib.Path(workspace.name)
        consumer, output = temporary / "consumer", temporary / "output"
        output.mkdir()
        copy_tree(project["source"], consumer)
        self.addCleanup(lambda: self.assertEqual(before, fingerprint(project["source"]), "Original project changed"))
        environment = os.environ.copy()
        for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "MAVEN_OPTS", "MAVEN_ARGS", "GRADLE_OPTS"):
            environment.pop(key, None)
        home = temporary / "home"
        home.mkdir()
        for key in ("TMP", "TEMP", "TMPDIR"):
            environment[key] = str(temporary)
        if tool == "maven":
            cache = pathlib.Path(OPTIONS.maven_cache or pathlib.Path.home() / ".m2/repository")
            copy_tree(cache, temporary / "maven-repository", project=False)
            settings = temporary / "settings.xml"
            settings.write_text("<settings/>", encoding="utf-8")
            environment["MAVEN_USER_HOME"] = str(home)
            goal = inject_maven(consumer)
            modules = maven_modules(consumer)
            leaves = []
            for module, path in modules.items():
                model, ns = pom(path)
                if not model.findall(ns + "modules/" + ns + "module"):
                    leaves.append((module, path))
            target_module, target = sorted(leaves)[0]
            original = target.read_bytes()
            common = [executable, "-B", "-ntp", "--offline", "-N", "-s", str(settings), "-gs", str(settings),
                      f"-Dmaven.repo.local={temporary / 'maven-repository'}", f"-Duser.home={home}"]
        else:
            guard = temporary / "guard"
            copy_tree(ROOT, guard)
            cache = pathlib.Path(OPTIONS.gradle_cache or os.environ.get("GRADLE_USER_HOME", pathlib.Path.home() / ".gradle"))
            if (cache / "caches").is_dir():
                copy_tree(cache / "caches", home / "caches", project=False)
            environment["GRADLE_USER_HOME"] = str(home)
            inject_gradle(consumer, guard, project["bootVersion"])
            modules, target_module = {":": consumer / "build.gradle"}, ":"
            common = [executable, "--no-daemon", "--offline", "--console=plain", "--no-watch-fs", "bootBomGuard"]
        secrets = repository_secrets(consumer)

        def run(stage, strict=False, flags=()):
            combined = []
            for module, path in sorted(modules.items()):
                if tool == "maven":
                    command = common + ["-f", str(path), goal, "-DbootBomGuard.failOnDrift=" + str(strict).lower()]
                else:
                    command = common + list(flags) + (["-PbbgStrict"] if strict else [])
                process = subprocess.run(command, cwd=consumer, env=environment, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, encoding="utf-8", errors="replace", timeout=900)
                self.assertFalse(any(secret in process.stdout for secret in secrets), f"Repository credential leaked in {stage}")
                parsed = reports(process.stdout, tool)
                self.assertEqual({module}, {report.module for report in parsed}, "Wrong module attribution")
                self.assertTrue(path.is_file(), "Reported module location must exist")
                self.assertEqual(int(strict and any(report.violation for report in parsed)), process.returncode,
                                 f"{stage}: exit violates documented warning/strict policy")
                index = len(combined)
                (output / f"{stage}-{index}.log").write_text(process.stdout, encoding="utf-8")
                capture = output / f"{stage}-{index}.report.txt"
                capture.write_text("\n\n".join("\n".join(report.lines) for report in parsed), encoding="utf-8")
                self.assertGreater(capture.stat().st_size, 0)
                combined.extend(parsed)
            return tuple(combined)

        baseline = run("baseline")
        self.assertEqual(baseline, run("repeat"), "Console reports must be deterministic")
        self.assertEqual(baseline, run("baseline-strict", strict=True))
        if project["bootVersion"].startswith("2."):
            for report in baseline:
                self.assertTrue(report.violation)
                self.assertTrue(any("UNKNOWN Unsupported Spring Boot BOM " + project["bootVersion"] in line for line in report.lines))
                self.assertFalse(any(line.startswith("PASS ") for line in report.lines))
            return
        self.assertTrue(all(any(project["bootVersion"] in line for line in item.lines[:1]) for item in baseline))
        if tool == "maven":
            mutate_maven(target)
        flags = ("-PbbgOverride",) if tool == "gradle" else ()
        drift = run("drift", flags=flags)
        self.assertEqual(drift, run("drift-strict", strict=True, flags=flags))
        findings = [(item, line) for item in drift for line in item.lines if line.startswith("DRIFT " + COORDINATE + " ")]
        self.assertTrue(findings, "Deliberate managed override must be reported")
        for item, line in findings:
            self.assertEqual(target_module, item.module, "Drift attributed to the wrong module")
            match = re.search(r" expected=(\S+) resolved=(\S+) classification=", line)
            self.assertIsNotNone(match)
            self.assertNotEqual(OVERRIDE, match[1], "Expected version must come from pristine Boot BOM")
            self.assertEqual(OVERRIDE, match[2])
        self.assertEqual(without_override(baseline), without_override(drift), "Override changed unrelated findings")
        if tool == "maven":
            target.write_bytes(original)
        self.assertEqual(baseline, run("removed"), "Removing override must restore the complete baseline report")
        if tool == "maven":
            mutate_maven(target, probe=True)
        probe_flags = ("-PbbgCredentialProbe",) if tool == "gradle" else ()
        probe = run("credential-probe", flags=probe_flags)
        self.assertEqual(probe, run("credential-probe-strict", strict=True, flags=probe_flags))
        affected = [item for item in probe if item.module == target_module]
        self.assertTrue(affected and all(item.violation for item in affected))
        text = "\n".join(line for item in affected for line in item.lines)
        self.assertIn("UNKNOWN ", text)
        self.assertIn("***", text, "Probe must actually exercise redaction, not merely store an unused repository URL")


def real_project_case(name, tool):
    def test(self):
        self.exercise(name, tool)
    test.__doc__ = f"Offline {name}/{tool}: policy, drift/removal, determinism, attribution and credentials."
    return test


for _name, _tools in EXPECTED.items():
    for _tool in _tools:
        setattr(RealProjectTest, "test_" + _name.replace("-", "_") + "_" + _tool, real_project_case(_name, _tool))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maven", help="Installed Maven executable")
    parser.add_argument("--gradle", help="Installed Gradle executable; no wrapper downloads")
    parser.add_argument("--maven-cache", help="Read-only, prewarmed Maven repository to copy")
    parser.add_argument("--gradle-cache", help="Read-only, prewarmed Gradle user home to copy")
    OPTIONS, remaining = parser.parse_known_args()
    unittest.main(argv=[__file__] + remaining, verbosity=2)
