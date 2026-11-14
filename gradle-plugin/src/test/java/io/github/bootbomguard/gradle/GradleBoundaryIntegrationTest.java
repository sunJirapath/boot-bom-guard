package io.github.bootbomguard.gradle;

import com.sun.net.httpserver.BasicAuthenticator;
import com.sun.net.httpserver.HttpServer;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

class GradleBoundaryIntegrationTest {
    @TempDir Path directory;
    private String bootVersion = "4.0.0-boundary";

    private static String dependency(String name, String version) {
        return "<dependency><groupId>guard.boundary</groupId><artifactId>" + name + "</artifactId><version>" + version + "</version></dependency>";
    }

    private void publish(String group, String name, String version, String content) throws IOException {
        Path release = Files.createDirectories(directory.resolve("repository/" + group.replace('.', '/') + "/" + name + "/" + version));
        String pom = "<project><modelVersion>4.0.0</modelVersion><groupId>" + group + "</groupId><artifactId>" + name + "</artifactId><version>" + version + "</version>" + content + "</project>";
        Files.writeString(release.resolve(name + "-" + version + ".pom"), pom.replace("><", ">\n<"));
    }

    private void consumer(String declarations, String extra, String repository) throws IOException {
        Files.writeString(directory.resolve("settings.gradle"), "rootProject.name = 'boundary-consumer'\n");
        Files.writeString(directory.resolve("build.gradle"), """
                plugins { id 'java'; id 'io.github.sunjirapath.bootbomguard' }
                repositories { maven { %s } }
                dependencies {
                    implementation platform('org.springframework.boot:spring-boot-dependencies:4.0.0-boundary')
                    %s
                }
                bootBomGuard { configurations = ['runtimeClasspath']; failOnDrift = providers.gradleProperty('strict').isPresent() }
                tasks.named('bootBomGuard') { doFirst {
                    def graph = configurations.runtimeClasspath.incoming.resolutionResult
                    println 'NATIVE_COMPONENT_COUNT=' + graph.allComponents.size()
                    println 'NATIVE_UNRESOLVED_COUNT=' + graph.allDependencies.count { it instanceof org.gradle.api.artifacts.result.UnresolvedDependencyResult }
                    graph.allDependencies.findAll { it instanceof org.gradle.api.artifacts.result.UnresolvedDependencyResult }.each { def cause = it.failure; while (cause != null) { println 'NATIVE_ERROR=' + cause.message; cause = cause.cause } }
                } }
                %s
                """.formatted(repository, declarations, extra).replace("4.0.0-boundary", bootVersion));
    }

    private void platform(String management) throws IOException {
        publish("org.springframework.boot", "spring-boot-dependencies", bootVersion,
                "<packaging>pom</packaging><dependencyManagement><dependencies>" + management + "</dependencies></dependencyManagement>");
    }

    @ParameterizedTest
    @ValueSource(strings = {"2.7.18", "5.0.0", "4.invalid", "3.5.x"})
    void unsupportedBomVersionsWarnAndFailStrictPolicy(String version) throws Exception {
        bootVersion = version;
        platform(dependency("library", "1"));
        publish("guard.boundary", "library", "1", "");
        consumer("implementation 'guard.boundary:library:1'", "", "url = uri('repository')");
        String warning = run(false, false);
        assertTrue(warning.contains("UNKNOWN Unsupported Spring Boot BOM " + version), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        String failure = run(true, false, "-Pstrict");
        assertTrue(failure.contains("UNKNOWN Unsupported Spring Boot BOM " + version), failure);
        assertTrue(failure.contains("policy failed"), failure);
    }

    private String run(boolean failure, boolean localHttp, String... flags) {
        return runTask("bootBomGuard", failure, localHttp, flags);
    }

    private String runTask(String task, boolean failure, boolean localHttp, String... flags) {
        var args = new ArrayList<>(List.of(task, "--console=plain", "--stacktrace"));
        if (Boolean.getBoolean("guard.test.offline") && !localHttp) args.add("--offline");
        args.addAll(List.of(flags));
        var runner = GradleRunner.create().withProjectDir(directory.toFile()).withPluginClasspath().withArguments(args);
        return (failure ? runner.buildAndFail() : runner.build()).getOutput();
    }

    @ParameterizedTest
    @ValueSource(strings = {"java-first", "guard-first"})
    void checkRunsGuardAndEnforcesStrictPolicyInEitherPluginOrder(String order) throws Exception {
        platform(dependency("library", "1"));
        for (String version : List.of("1", "2")) {
            publish("guard.boundary", "library", version, "");
            Path jar = directory.resolve("repository/guard/boundary/library/" + version + "/library-" + version + ".jar");
            try (var zip = new java.util.zip.ZipOutputStream(Files.newOutputStream(jar))) { zip.finish(); }
        }
        consumer("implementation 'guard.boundary:library:1'", "", "url = uri('repository')");
        Path build = directory.resolve("build.gradle");
        if (order.equals("guard-first"))
            Files.writeString(build, Files.readString(build).replace("id 'java'; id 'io.github.sunjirapath.bootbomguard'",
                    "id 'io.github.sunjirapath.bootbomguard'; id 'java'"));
        String aligned = runTask("check", false, false, "-Pstrict");
        assertTrue(aligned.contains("> Task :bootBomGuard"), aligned);
        assertTrue(aligned.contains("PASS checked=1 drift=0 unknown=0"), aligned);
        Files.writeString(build, Files.readString(build).replace("guard.boundary:library:1", "guard.boundary:library:2"));
        String failure = runTask("check", true, false, "-Pstrict");
        assertTrue(failure.contains("DRIFT guard.boundary:library expected=1 resolved=2"), failure);
        assertTrue(failure.contains("policy failed"), failure);
    }

    @Test void unmatchedExceptionWarnsAndFailsStrictPolicy() throws Exception {
        platform(dependency("library", "1"));
        publish("guard.boundary", "library", "1", "");
        consumer("implementation 'guard.boundary:library:1'",
                "bootBomGuard { exceptions.put('guard.boundary:deleted', 'Old exemption') }", "url = uri('repository')");
        String warning = run(false, false);
        assertTrue(warning.contains("UNKNOWN Unmatched exception (no resolved managed coordinate): guard.boundary:deleted"), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        String failure = run(true, false, "-Pstrict");
        assertTrue(failure.contains("Unmatched exception"), failure);
        assertTrue(failure.contains("policy failed"), failure);
    }

    @Test void springDependencyManagementOnlyIsUnknown() throws Exception {
        platform(dependency("library", "1"));
        publish("guard.boundary", "library", "1", "");
        consumer("implementation 'guard.boundary:library'", """
                dependencyManagement {
                    imports { mavenBom 'org.springframework.boot:spring-boot-dependencies:4.0.0-boundary' }
                }
                """, "url = uri('repository')");
        Path build = directory.resolve("build.gradle");
        Files.writeString(build, Files.readString(build)
                .replace("id 'java';", "id 'java'; id 'io.spring.dependency-management' version '1.1.7';")
                .replace("implementation platform('org.springframework.boot:spring-boot-dependencies:4.0.0-boundary')", ""));
        String warning = run(false, false);
        assertTrue(warning.contains("NATIVE_UNRESOLVED_COUNT=0"), warning);
        assertTrue(warning.contains("UNKNOWN Missing Spring Boot BOM"), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        String failure = run(true, false, "-Pstrict");
        assertTrue(failure.contains("UNKNOWN Missing Spring Boot BOM"), failure);
        assertTrue(failure.contains("policy failed"), failure);
    }

    @Test void broadDeepDiamondGraphRetainsOneRealOverride() throws Exception {
        int count = 2048;
        var management = new StringBuilder();
        for (int i = 0; i < count; i++) {
            management.append(dependency("module-" + i, "1"));
            var children = new StringBuilder();
            if (i < 127) children.append(dependency("module-" + (i + 1), "1"));
            if (i == 0) for (int j = 128; j < count; j++) children.append(dependency("module-" + j, "1"));
            if (i >= 128) children.append(dependency("module-127", "1"));
            publish("guard.boundary", "module-" + i, "1", "<dependencies>" + children + "</dependencies>");
        }
        publish("guard.boundary", "module-2047", "2", "<dependencies>" + dependency("module-127", "1") + "</dependencies>");
        platform(management.toString());
        consumer("implementation 'guard.boundary:module-0:1'; implementation 'guard.boundary:module-2047:2'", "", "url = uri('repository')");
        String out = run(true, false, "-Pstrict");
        assertTrue(out.contains("NATIVE_COMPONENT_COUNT=2050"), out);
        assertTrue(out.contains("NATIVE_UNRESOLVED_COUNT=0"), out);
        assertTrue(out.contains("DRIFT guard.boundary:module-2047 expected=1 resolved=2"), out);
        assertTrue(out.contains("WARN checked=2048 drift=1 unknown=0"), out);
    }

    @Test void exactPreferredOnlyPublishedConstraintIsComparable() throws Exception {
        platform("");
        Path release = directory.resolve("repository/org/springframework/boot/spring-boot-dependencies/4.0.0-boundary");
        Path pom = release.resolve("spring-boot-dependencies-4.0.0-boundary.pom");
        Files.writeString(pom, Files.readString(pom).replace("<modelVersion>", "<!-- do_not_remove: published-with-gradle-metadata --><modelVersion>"));
        Files.writeString(release.resolve("spring-boot-dependencies-4.0.0-boundary.module"), """
                {"formatVersion":"1.1","component":{"group":"org.springframework.boot","module":"spring-boot-dependencies","version":"4.0.0-boundary"},
                "variants":[{"name":"runtimeElements","attributes":{"org.gradle.category":"platform","org.gradle.usage":"java-runtime"},
                "dependencyConstraints":[{"group":"guard.boundary","module":"library","version":{"prefers":"1"}}]}]}
                """);
        for (String version : List.of("1", "2")) publish("guard.boundary", "library", version, "");
        consumer("implementation 'guard.boundary:library:2'", "", "url = uri('repository')");
        String out = run(true, false, "-Pstrict");
        assertTrue(out.contains("DRIFT guard.boundary:library expected=1 resolved=2"), out);
        assertTrue(out.contains("WARN checked=1 drift=1 unknown=0"), out);
    }

    @ParameterizedTest
    @ValueSource(strings = {"[4.0.0-boundary,5.0)", "4.+", "latest.release"})
    void rangeRequestedBomHasExplicitContract(String selector) throws Exception {
        platform(dependency("library", "1"));
        publish("guard.boundary", "library", "1", "");
        Files.writeString(directory.resolve("repository/org/springframework/boot/spring-boot-dependencies/maven-metadata.xml"), """
                <metadata><groupId>org.springframework.boot</groupId><artifactId>spring-boot-dependencies</artifactId>
                <versioning><latest>4.0.0-boundary</latest><release>4.0.0-boundary</release>
                <versions><version>4.0.0-boundary</version></versions></versioning></metadata>
                """);
        consumer("implementation 'guard.boundary:library:1'", "", "url = uri('repository')");
        Path build = directory.resolve("build.gradle");
        Files.writeString(build, Files.readString(build).replace("spring-boot-dependencies:4.0.0-boundary",
                "spring-boot-dependencies:" + selector));
        String warning = run(false, false);
        assertTrue(warning.contains("NATIVE_UNRESOLVED_COUNT=0"), warning);
        assertTrue(warning.contains("BOM=org.springframework.boot:spring-boot-dependencies:4.0.0-boundary"), warning);
        assertTrue(warning.contains("UNKNOWN Unsupported non-exact Spring Boot BOM request:"), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        String failure = run(true, false, "-Pstrict");
        assertTrue(failure.contains("UNKNOWN Unsupported non-exact Spring Boot BOM request:"), failure);
        assertTrue(failure.contains("policy failed"), failure);
    }

    @Test void sameModuleVersionSubstitutionCannotPassAnAlignedGraph() throws Exception {
        platform(dependency("library", "1"));
        for (String version : List.of("1", "2")) publish("guard.boundary", "library", version, "");
        consumer("implementation 'guard.boundary:library:2'", """
                configurations.runtimeClasspath.resolutionStrategy.dependencySubstitution {
                    substitute module('guard.boundary:library:2') using module('guard.boundary:library:1')
                }
                """, "url = uri('repository')");
        String warning = run(false, false);
        assertTrue(warning.contains("NATIVE_UNRESOLVED_COUNT=0"), warning);
        assertTrue(warning.contains("UNKNOWN Unsupported dependency substitution or selection rule:"), warning);
        assertFalse(warning.contains("DRIFT "), warning);
        assertFalse(warning.contains("PASS checked="), warning);
        String failure = run(true, false, "-Pstrict");
        assertTrue(failure.contains("UNKNOWN Unsupported dependency substitution or selection rule:"), failure);
        assertTrue(failure.contains("policy failed"), failure);
    }

    @Test void libraryMetadataRuleCannotContaminatePublishedPlatformBaseline() throws Exception {
        platform(dependency("library", "1"));
        publish("guard.boundary", "bridge", "1", "");
        for (String version : List.of("1", "2")) publish("guard.boundary", "library", version, "");
        consumer("implementation 'guard.boundary:bridge:1'", """
                dependencies.components.withModule('guard.boundary:bridge') {
                    allVariants { withDependencies { add('guard.boundary:library:2') } }
                }
                """, "url = uri('repository')");
        String out = run(true, false, "-Pstrict");
        assertTrue(out.contains("NATIVE_COMPONENT_COUNT=4"), out);
        assertTrue(out.contains("expected=1 resolved=2 classification=TRANSITIVE_DRIFT"), out);
        assertTrue(out.contains("WARN checked=1 drift=1 unknown=0"), out);
    }

    @Test void authenticatedRepositorySuccessAndDeniedAccessPreservePolicy() throws Exception {
        platform(dependency("library", "1"));
        for (String version : List.of("1", "2")) publish("guard.boundary", "library", version, "");
        var requests = new AtomicInteger();
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        var context = server.createContext("/", exchange -> {
            requests.incrementAndGet();
            Path file = directory.resolve("repository").resolve(exchange.getRequestURI().getPath().substring(1)).normalize();
            if (!file.startsWith(directory.resolve("repository")) || !Files.isRegularFile(file)) {
                exchange.sendResponseHeaders(404, -1);
            } else {
                byte[] content = Files.readAllBytes(file);
                if (exchange.getRequestMethod().equals("HEAD")) exchange.sendResponseHeaders(200, -1);
                else { exchange.sendResponseHeaders(200, content.length); exchange.getResponseBody().write(content); }
            }
            exchange.close();
        });
        context.setAuthenticator(new BasicAuthenticator("boundary") {
            @Override public boolean checkCredentials(String username, String password) {
                return username.equals("fixture-user") && password.equals("fixture-password");
            }
        });
        server.start();
        try {
            String endpoint = "url = uri('http://127.0.0.1:" + server.getAddress().getPort() + "/'); allowInsecureProtocol = true; credentials { username = 'fixture-user'; password = providers.gradleProperty('denied').isPresent() ? 'wrong-password' : 'fixture-password' }";
            consumer("implementation 'guard.boundary:library:2'", "", endpoint);
            String warning = run(false, true);
            assertTrue(requests.get() > 0, "Native resolver did not use authenticated fixture repository");
            assertTrue(warning.contains("WARN checked=1 drift=1 unknown=0"), warning);
            assertTrue(run(true, true, "-Pstrict").contains("policy failed"));
            // Refresh prevents warmed metadata from masking denied access.
            String denied = run(true, true, "-Pstrict", "-Pdenied", "--refresh-dependencies");
            assertTrue(denied.contains("UNKNOWN Unresolved Gradle dependencies"), denied);
            assertFalse(denied.contains("PASS checked="), denied);
            assertFalse(denied.contains("fixture-password"), denied);
            assertFalse(denied.contains("wrong-password"), denied);
        } finally { server.stop(0); }
    }

    @Test void denseConflictingGraphChecksEachSelectedModuleOnce() throws Exception {
        int width = 8, levels = 16;
        var management = new StringBuilder();
        for (int level = 0; level < levels; level++) {
            for (int column = 0; column < width; column++) {
                String name = "dense-" + level + "-" + column;
                management.append(dependency(name, "1"));
                var children = new StringBuilder();
                if (level + 1 < levels) for (int next = 0; next < width; next++)
                    children.append(dependency("dense-" + (level + 1) + "-" + next,
                            level == levels - 2 && column % 2 == 0 && next == 0 ? "2" : "1"));
                publish("guard.boundary", name, "1", "<dependencies>" + children + "</dependencies>");
            }
        }
        publish("guard.boundary", "dense-15-0", "2", "");
        platform(management.toString());
        var roots = new StringBuilder();
        for (int column = 0; column < width; column++) roots.append("implementation 'guard.boundary:dense-0-" + column + ":1';\n");
        consumer(roots.toString(), "", "url = uri('repository')");
        String out = run(true, false, "-Pstrict");
        assertTrue(out.contains("NATIVE_COMPONENT_COUNT=130"), out);
        assertTrue(out.contains("NATIVE_UNRESOLVED_COUNT=0"), out);
        assertTrue(out.contains("DRIFT guard.boundary:dense-15-0 expected=1 resolved=2 classification=TRANSITIVE_DRIFT"), out);
        assertTrue(out.contains("WARN checked=128 drift=1 unknown=0"), out);
    }

    @Test void separateConfigurationsKeepTheirOwnSelectedBomAndPolicy() throws Exception {
        platform(dependency("library", "1"));
        publish("org.springframework.boot", "spring-boot-dependencies", "4.1.0-boundary",
                "<packaging>pom</packaging><dependencyManagement><dependencies>" + dependency("library", "2") + "</dependencies></dependencyManagement>");
        for (String version : List.of("1", "2")) publish("guard.boundary", "library", version, "");
        consumer("implementation 'guard.boundary:library:2'", """
                configurations { independent { canBeResolved = true; canBeConsumed = false } }
                dependencies {
                    independent platform('org.springframework.boot:spring-boot-dependencies:4.1.0-boundary')
                    independent 'guard.boundary:library:2'
                }
                bootBomGuard { configurations = ['runtimeClasspath', 'independent', 'independent'] }
                """, "url = uri('repository')");
        String out = run(true, false, "-Pstrict");
        assertTrue(out.contains("BOM=org.springframework.boot:spring-boot-dependencies:4.1.0-boundary"), out);
        assertTrue(out.contains("PASS checked=1 drift=0 unknown=0"), out);
        assertTrue(out.contains("BOM=org.springframework.boot:spring-boot-dependencies:4.0.0-boundary"), out);
        assertTrue(out.contains("WARN checked=1 drift=1 unknown=0"), out);
        assertEquals(1, out.lines().filter(line -> line.equals("configuration=independent")).count(), out);
        assertTrue(out.contains("policy failed"), out);
    }
}
