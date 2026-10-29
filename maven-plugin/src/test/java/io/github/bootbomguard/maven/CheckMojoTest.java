package io.github.bootbomguard.maven;

import io.github.bootbomguard.core.Coordinates;
import io.github.bootbomguard.core.Guard;
import org.eclipse.aether.artifact.DefaultArtifact;
import org.eclipse.aether.graph.DefaultDependencyNode;
import org.eclipse.aether.graph.Dependency;
import org.eclipse.aether.graph.DependencyNode;
import org.eclipse.aether.util.graph.transformer.ConflictResolver;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class CheckMojoTest {
    private static DefaultDependencyNode node(String name) {
        return new DefaultDependencyNode(new Dependency(new DefaultArtifact("guard.fixture", name, "jar", "1"), "compile"));
    }

    private static List<Guard.Resolved> collect(DependencyNode root) throws Exception {
        var actual = new ArrayList<Guard.Resolved>();
        var method = CheckMojo.class.getDeclaredMethod("collect", DependencyNode.class, int.class,
                Map.class, Map.class, List.class, java.util.Set.class, List.class);
        method.setAccessible(true);
        method.invoke(new CheckMojo(), root, 0, Map.of(), Map.of(), actual, new HashSet<>(), new ArrayList<>());
        return actual;
    }

    @Test void deepNativeGraphDoesNotOverflowTheJavaStack() {
        var root = node("root");
        var parent = root;
        for (int i = 0; i < 20000; i++) {
            var child = node("module-" + i);
            parent.getChildren().add(child);
            parent = child;
        }
        var actual = assertDoesNotThrow(() -> collect(root));
        assertEquals(20000, actual.size());
        assertEquals(Guard.Origin.TRANSITIVE_DRIFT, actual.getLast().origin());
    }

    @Test void sharedDirectNodeKeepsItsShortestRootPath() throws Exception {
        var root = node("root");
        var bridge = node("bridge");
        var direct = node("direct");
        root.getChildren().addAll(List.of(bridge, direct));
        bridge.getChildren().add(direct);
        var actual = collect(root);
        assertEquals(2, actual.size());
        assertEquals(Guard.Origin.DIRECT_OVERRIDE, actual.stream()
                .filter(item -> item.coordinates().equals(Coordinates.parse("guard.fixture:direct"))).findFirst().orElseThrow().origin());
    }

    @Test void cyclicAndVerboseLosingNodesAreNotTraversedAgain() throws Exception {
        var root = node("root");
        var selected = node("selected");
        var loser = node("loser");
        loser.setData(ConflictResolver.NODE_DATA_WINNER, selected);
        loser.getChildren().add(node("loser-child"));
        root.getChildren().addAll(List.of(selected, loser));
        selected.getChildren().add(root);
        var actual = collect(root);
        assertEquals(1, actual.size());
        assertEquals("selected", actual.getFirst().coordinates().artifact());
    }
}
