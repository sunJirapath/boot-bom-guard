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

- Candidate checks (unverified; confirm, then edit): `./gradlew test`, `cd core && mvn test`, `cd maven-plugin && mvn test`, `mvn test`
- CI workflows (the commands CI really runs): `.github/workflows/ci.yml`
- Existing guidance to follow first: none
