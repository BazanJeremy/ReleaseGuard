# ADR-004: Test identity join — JUnit dialect declared, not guessed

- **Status:** Accepted — supersedes [ADR-002](ADR-002-test-identity-join.md)
- **Date:** 2026-10-12
- **Deciders:** Jérémy Bazan

## Context

The ADR-001 cross-signal rule (a failing test listed as flaky does not trip G1) requires joining test identities across two artifact dialects. ADR-002 settled that join by **reconstructing pytest node ids** from `classname`/`name`, and closed with a follow-up clause: if a real-world JUnit dialect broke the heuristic, the evidence would go to `docs/bug-evidence.md` and to a superseding ADR, not into a silent patch. This is that ADR.

The dialect that broke it is the one JavaScript test runners emit. Playwright — and `jest-junit`, Vitest and other JS emitters — put a **file path** in `classname` and no `file` attribute at all. The ADR-002 heuristic splits `classname` on dots, finds no CapWords segment, and consumes the whole string as a module path: `invariants/zero-js.spec.ts` becomes `invariants/zero-js/spec/ts.py`. FlakySense, reading the same file, prefers a `file` attribute and falls back to `classname` verbatim, deriving `invariants/zero-js.spec.ts::<name>`. The two keys can never be equal.

Measured on a real 204-test Playwright report (`bazanjeremy.github.io`, 12.10.2026): **0 attributes named `file`, and 0 of 204 identities agree**. The break is total, not partial — no test in such a report can ever be excused. The failure mode is on the safe side, exactly as ADR-002 predicted: a join miss makes the gate *stricter*, so the tool was blocking releases it should have shipped conditionally, never the reverse. That is why it stayed invisible — nothing goes wrong until a known-flaky test fails, and then the verdict merely looks conservative.

Reconstruction cannot simply be replaced, because the pytest dialect is equally real: `classname="tests.test_search"` carries a dotted module path with no separator to key on. Both conventions must be served, and the measured evidence is that they cannot be told apart from the bytes alone by any rule a release gate should trust.

## Decision

`parse_junit` takes a **declared** `dialect`, exposed as `--junit-dialect`:

- **`pytest`** (the default, carried over from ADR-002) — dotted `classname` segments are module path components until the first CapWords segment, which starts the class chain: `tests.test_api.TestLogin` + `test_ok` gives `tests/test_api.py::TestLogin::test_ok`.
- **`path`** — `classname` is already a file path; the identity is `classname::name`, taken verbatim.

Carried over from ADR-002 and still in force:

- **All counts derive from `<testcase>` elements**, never from suite attributes (real-world artifacts drift).
- **Safety property: misses are conservative.** A failing test whose identity finds no flaky-list match counts as a *real* failure, so a join miss can only make the verdict stricter, never excuse a failure it should not. The unsafe direction (false GO) would require a false *positive* match, which exact equality on a full, file-prefixed key makes implausible — under `path` as under `pytest`, and pinned by a test in both.
- **Fixture integrity tests keep their bare-name comparison**; they pin scenario design rather than duplicate parser logic.

Two further points are part of this decision, not implementation detail:

- **Nothing is normalized.** Separators, case and extension stay the artifact's own bytes. A Windows-emitted report says `invariants\zero-js.spec.ts`, and so does the FlakySense report read from it, so the join holds — but ReleaseGuard does not produce the flakiness report and must not rewrite one side of a key it does not own. Normalizing would fix a mismatch nobody has measured and break the one case that currently works.
- **The dialect is a declaration about the artifact, not a threshold.** ADR-003 narrowed the CLI to threshold flags because the signal weighting *is* the gate's identity. `--junit-dialect` cannot move that: it says what the input bytes mean, and no value of it makes a failing test pass. It widens the ADR-003 surface by one flag, and this is where that is recorded.

## Options Considered

1. **Declared dialect, `pytest` by default** — one flag, no inference, every existing invocation unchanged. **Accepted.**
2. **Auto-detect the dialect** (a `classname` holding `/`, `\` or `.spec.`/`.test.` is a path) — nothing to pass, and it would have fixed the measured report. Rejected: ADR-002 already paid for one heuristic, and a second one deciding *which* heuristic applies compounds the risk instead of bounding it. A gate that infers what it could be told is a gate whose join key silently changes when a filename does.
3. **Normalize both sides to a canonical form** (slashes, lowercase, strip extension) — more joins would match. Rejected: it rewrites identities ReleaseGuard does not own, and a canonicalization collision is a false *GO*, the one direction ADR-001 forbids.
4. **Bare-name join** (compare only the `name` attribute) — no heuristic and dialect-blind, so it would have worked here too. Rejected in ADR-002 and still rejected: two same-named tests in different files collide, and a collision can wrongly excuse a real failure. Verified counterfactual, [bug evidence #2](../bug-evidence.md).
5. **Require producers to emit node ids** — zero heuristics, but standard JUnit emitters (Maven, Gradle, Jenkins) never produce that format, and here it would mean asking an upstream tool to misname a file path. Rejected.

## Consequences

- A JS-runner report now needs `--junit-dialect path`. Forgetting it is still safe (strict), which is why the defect survived unnoticed; the READMEs and `--help` name the flag, and [bug evidence #4](../bug-evidence.md) records the measurement.
- The `pytest` heuristic keeps its documented limitation: it assumes snake_case modules and CapWords classes, and a CamelCase module name would mis-split. Acceptable for that ecosystem, and now avoidable by declaring `path` instead.
- An empty `classname` under `path` yields the bare `name`. FlakySense would emit `unknown::name` there, so that one degenerate case does not join. Fabricating an `unknown` prefix to match would be inventing a path; a miss stays strict, so the honest form is kept. **Unmeasured in the wild** — no observed report has an empty classname.
- A report mixing both conventions in one file cannot be served by one invocation. Not observed; no provision is made for it.
- The dialect list is the single place a third convention would be added, with its own evidence entry.
