# Project

Name: **boot-bom-guard**

Purpose: Spring Boot 4 BOM drift checks for Maven and Gradle, using native dependency resolution.

## Scope

- User and problem: TODO
- MVP: TODO
- Acceptance criteria: TODO
- Out of scope: TODO

## Constraints

- Public by default only after a secret, copyright, data, and license check.
- Favor stdlib/native and the fewest safe dependencies.
- Prefer runnable examples, explicit failures, evidence, and simple maintenance.

See [[STATE]] and [[DECISIONS]].

## Found in the existing repo

- Verified 2026-10-29: `mvn -B -ntp --offline install`, `python scripts/verify_maven.py --offline`, `gradlew.bat --offline --no-daemon --console=plain check -PtestOffline=true --rerun-tasks`: 58 distinct tests, zero failures/skips. [Campaign and scope limits](../reports/real-world-2026-10-26/summary.md).
- CI workflows (the commands CI really runs): `.github/workflows/ci.yml`
- Existing guidance to follow first: none
