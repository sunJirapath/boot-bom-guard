# Actual scenario coverage

Historical and fixed-guard scenarios are separate. Counts are repository/scenario observations, not test classes or classpath log lines. Native baseline completion and unsupported guard boundaries remain distinct.

| Scenario | Recorded status | Repositories |
| --- | --- | --- |
| native-resolution-baseline | RESOLUTION_COMPLETED: 74; BLOCKED: 20; METADATA_ONLY: 6 | 100 |
| direct | VERIFIED: 25 | 25 |
| managed | VERIFIED: 25 | 25 |
| allowed | VERIFIED: 25 | 25 |
| incomplete | VERIFIED: 25 | 25 |
| determinism | VERIFIED: 25 | 25 |
| offline | VERIFIED: 25 | 25 |
| original-warning-strict | VERIFIED: 69; INCOMPLETE: 6; BUG_CONFIRMED: 5 | 80 |
| property-override | VERIFIED: 1 | 1 |
| type-boundary | VERIFIED: 1 | 1 |
| synthetic-credentials | VERIFIED: 1 | 1 |
| native-platform/platform | VERIFIED: 2 | 2 |
| native-platform/direct | VERIFIED: 2 | 2 |
| native-platform/constraint | VERIFIED: 1 | 1 |
| native-platform/dsl-managed | VERIFIED: 1 | 1 |
| native-platform/allowed | VERIFIED: 1 | 1 |
| native-platform/forced | VERIFIED: 1 | 1 |
| native-platform/incomplete | VERIFIED: 1 | 1 |
| controlled-subproject/direct | VERIFIED: 1 | 1 |
| controlled-subproject/constraint | VERIFIED: 1 | 1 |
| controlled-subproject/transitive | VERIFIED: 1 | 1 |
| controlled-subproject/enforced | VERIFIED: 1 | 1 |
| controlled-subproject/forced | VERIFIED: 1 | 1 |
| controlled-subproject/configuration-boundary | VERIFIED: 1 | 1 |
| missing-native-BOM | VERIFIED: 10 | 10 |
| unsupported-Boot-major | VERIFIED: 34 | 34 |
| import-precedence | VERIFIED: 1 | 1 |
| reactor-pl-am-T2 | VERIFIED: 1; EXPECTED_BOUNDARY: 1 | 2 |
| matched-offline-performance | VERIFIED: 3 | 3 |
| original-build-revisit | EXPECTED_UNSUPPORTED: 13; PASS_EXPECTED: 5; DRIFT_DETECTED_CORRECTLY: 7; ENV_BLOCKED: 1 | 26 |
| revisit/native-metadata-and-artifacts | VERIFIED: 25 | 25 |
| revisit/independent-native-oracle | VERIFIED: 12 | 12 |
| revisit/offline-determinism | VERIFIED: 21 | 21 |
| fixed-guard/direct | VERIFIED: 5 | 5 |
| fixed-guard/managed | VERIFIED: 5 | 5 |
| fixed-guard/allowed | VERIFIED: 5 | 5 |
| fixed-guard/incomplete | VERIFIED: 5 | 5 |
| fixed-guard/determinism | VERIFIED: 5 | 5 |
| fixed-guard/offline | VERIFIED: 5 | 5 |
| revisit/warning-strict-unsupported-boundary | VERIFIED: 9 | 9 |
| snapshot-fix-native-graph-parity | VERIFIED: 5 | 5 |
| complete-default-reactor | VERIFIED 15 modules; 14 Boot model comparisons: 1; VERIFIED 50 modules; 49 Boot model comparisons: 1; VERIFIED 12 modules; 11 Boot model comparisons: 1 | 3 |
| selected-reactor-pl-am | VERIFIED 4 modules; 4 Boot model comparisons: 1 | 1 |
| whole-reactor-matched-offline-performance | VERIFIED: 1 | 1 |

See [coverage.csv](coverage.csv) for exact repositories and evidence. New wrapper versions include 2.10, 2.13, 7.4, 8.5, 8.14.1, 8.14.5, 9.1.0, 9.3.1, 9.8.1 and 9.8.2; wrapper execution alone does not imply supported guard integration. No Boot migration was attempted.
