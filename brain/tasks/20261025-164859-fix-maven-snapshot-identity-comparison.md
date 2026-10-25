# Fix Maven SNAPSHOT identity comparison

Date: 2026-10-25 UTC

## Outcome

Fixed BBG-001 by resolving pristine expected and effective managed snapshot artifact identities through the existing Maven Resolver session. Added six frozen local-repository regressions and documented native verification; release comparison and the Gradle adapter are unchanged.

## Verification

Maven offline install: 12 core tests. Python Maven suite: 21 tests online and offline. Gradle 8.14.3 check online and warmed offline: 12 core plus 25 TestKit tests, plugin validation, zero failures/errors/skips. Six new tests failed before the fix. Five pinned public repository leaves: identical native graphs, 202 false findings removed, all three genuine Gateway drifts retained, correct warning/strict exits and deterministic repeats. Minimal Boot-starter reproduction now passes strict mode. Diff whitespace check passed. Hosted CI not yet run.

## Decision

Resolve comparable Maven snapshot identities natively before exact comparison and managed-origin classification; never strip timestamps or equate every build of a snapshot.

## Next

Publish and review the focused fix PR. The separate campaign still has 26 blocked candidates and no complete Huge-graph benchmark; those are not certified by this fix.
