# Complete 100-candidate campaign follow-up

Date: 2026-10-29 UTC

## Outcome

Reconciled all 100 pinned public candidates: 30 aligned, 12 genuine drift, 57 unsupported, one GeoServer external artifact blocker. Revisited all 26 historical blockers; published native evidence, exact coverage, regression recommendations and reactor measurements in reports/real-world-2026-10-26. No additional product defect established beyond fixed BBG-001.

## Verification

PASS: report validator (100 clone contents, 3768 source hashes, 531 coverage observations), Maven offline install (12 core), Python Maven suite (21), Gradle 8.14.3 offline check (12 shared core plus 25 adapter), plugin validation. NOT RUN: new online suite, Maven 4, new Gradle 9/10 run, application runtime tests, single graph above 1500 nodes, production resource budgets, AutoHarness live learning. Historical online/native campaign evidence is explicitly separate.

## Decision

Native artifact availability and pristine BOM oracle define supported outcomes. Use Git core.longpaths on Windows and exact blob comparison for byte-identical stat flags; do not restore unchanged candidate files.

## Next

Update PR #6 and verify persisted head and CI. GeoServer needs upstream gs-main 3.1.0-CLOUD-SNAPSHOT; unsupported candidates and unrun scope remain explicit. Do not merge PR.
