# ADR-002: Test identity join — reconstructed pytest node ids, conservative on miss

- **Status:** Accepted
- **Date:** 2026-07-10
- **Deciders:** Jérémy Bazan

## Context

The ADR-001 cross-signal rule (a failing test listed as flaky does not trip G1) requires joining test identities across two artifact dialects: JUnit XML identifies a test by `classname="tests.test_search"` + `name="test_search_pagination"`, while FlakySense reports use pytest node ids (`tests/test_search.py::test_search_pagination`). The join key *is* the mechanism that carries the core signal-fusion behavior — getting it wrong either excuses real failures (false GO) or blocks releases needlessly (false NO GO). Those two failure directions are not symmetric for a release gate.

## Decision

The JUnit parser **reconstructs pytest node ids** from `classname`/`name`: dotted `classname` segments are module path components until the first CapWords segment, which starts the class chain (`tests.test_api.TestLogin` + `test_ok` ⇒ `tests/test_api.py::TestLogin::test_ok`). All counts are derived from `<testcase>` elements, never from suite attributes (real-world artifacts drift).

**Safety property — misses are conservative.** A failing test whose reconstructed id finds no flaky-list match counts as a *real* failure. A join miss can therefore only make the verdict stricter (toward NO GO), never excuse a failure it should not. The unsafe direction (false GO) would require a false *positive* match, which exact node-id equality makes implausible.

## Options Considered

1. **Bare-name join** (compare only `test_search_pagination`) — no heuristic, but two same-named tests in different files collide, and a collision can wrongly excuse a real failure: a false GO. The one direction a release gate must never fail toward. Rejected.
2. **Reconstructed node ids, exact match** — CapWords heuristic is pytest-calibrated and documented; misses fail strict. **Accepted.**
3. **Require producers to emit node ids** — zero heuristics, but standard JUnit emitters (Maven, Gradle, Jenkins) never produce that format; the tool would stop being plug-and-play. Rejected.

## Consequences

- The heuristic assumes pytest conventions (snake_case modules, CapWords classes). A CamelCase module name would mis-split; documented limitation, acceptable for the target ecosystem.
- Fixture integrity tests (S1) keep their bare-name comparison — they exist to pin scenario design, not to duplicate parser logic.
- Follow-up: if a real-world JUnit dialect breaks the heuristic, evidence goes to `docs/bug-evidence.md` and a superseding ADR — not a silent patch.
