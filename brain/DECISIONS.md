# Decisions

Record only decisions that influence future work: date, choice, why, and a linked task/evidence note. Keep this file brief; detailed research belongs in separate notes.

See [[PROJECT]] for the project goal.

<!-- harness:decisions:start -->

- 2026-10-25: Resolve comparable Maven snapshot identities natively before exact comparison and managed-origin classification; never strip timestamps or equate every build of a snapshot. (evidence: [[tasks/20261025-164859-fix-maven-snapshot-identity-comparison]])

- 2026-10-29: Native artifact availability and pristine BOM oracle define supported outcomes. Use Git core.longpaths on Windows and exact blob comparison for byte-identical stat flags; do not restore unchanged candidate files. (evidence: [[tasks/20261029-074321-complete-100-candidate-campaign-follow-up]])
