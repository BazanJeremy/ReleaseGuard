# ADR-005: The default JUnit dialect is `path`

- **Status:** Accepted — supersedes the default chosen in [ADR-004](ADR-004-junit-dialect-declared.md); the rest of ADR-004 stays in force
- **Date:** 2026-11-14
- **Deciders:** Jérémy Bazan

## Context

ADR-004 made the JUnit dialect a declaration and kept `pytest` as the default, "carried over from ADR-002". That default rested on an assumption nobody had measured: that the flakiness report names tests by pytest node id, so that reconstructing a node id from `classname` would meet it.

Measured on 2026-11-14, wiring the two tools back to back on reports written by a real pytest 9.1.1 run (three tests, two of them failing every other run, one of those inside a class, six runs):

- pytest's default JUnit report carries **no `file` attribute**. FlakySense therefore reports `tests.test_api.TestLogin::test_ok` and `tests.test_api::test_plain` — `classname::name`, verbatim.
- Under the default dialect, ReleaseGuard derives `tests/test_api.py::TestLogin::test_ok` and `tests/test_api.py::test_plain`. **0 of 2** failures join. Verdict: NO GO, exit 2.
- Under `--junit-dialect path`, on the same bytes, **2 of 2** join. Verdict: CONDITIONAL GO, exit 1.

So the dialect named `pytest` did not join a pytest report against the only flakiness producer this tool reads. ADR-004 measured the same total break on a Playwright report and fixed it by adding `path`; it did not re-measure the pytest side.

Why the suite never saw it: the canonical scenarios paired a JUnit report without `file` with a hand-written flakiness report using `tests/test_search.py::…` identities — a pairing no real run produces.

The failure direction was again the safe one (ADR-002's conservative-on-miss property): a dead join blocks, it never ships. That is why it produced no complaint.

On the producer side, FlakySense has settled its identity as `classname::name` in every case (its ADR-008), dropping the `file`-first rule that also merged same-named tests from different classes.

## Decision

`path` is the default dialect: the identity is `classname::name`, verbatim. `--junit-dialect pytest` remains available and unchanged for a flakiness producer that names tests by pytest node id.

The flag keeps its name and its two values. Nothing is normalized, as in ADR-004.

## Options Considered

1. **Default `path`** — joins FlakySense output for every runner measured so far (pytest, Playwright) with no option to remember. The default now matches what the producer emits instead of what a node id ought to look like. **Chosen.**
2. **Keep `pytest` as default, document "use `path` with FlakySense"** — no behaviour change, but the first command a reader copies from the README then blocks on real data, silently and in the safe direction. A default that requires the documentation to be read in order to work is the trap ADR-003 removed for exit codes.
3. **Detect the dialect from the report** — rejected by ADR-004 for a reason that still holds: a release gate must not infer what it can be told.
4. **Make FlakySense emit pytest node ids** — moves the reconstruction heuristic into the producer, where it breaks on Playwright reports exactly as it did here (bug evidence #4).

## Consequences

- **Behaviour change for anyone relying on the old default** with a producer of pytest node ids: they must now pass `--junit-dialect pytest`. With FlakySense there is nothing to pass.
- The verdict text shows identities as the report carries them (`tests.test_search::test_search_pagination`), no longer as reconstructed node ids.
- The canonical scenarios' flakiness reports now carry the identities FlakySense really emits for their JUnit reports. A new fixture, `data/samples/contract_pytest/`, holds real bytes: the JUnit report of one pytest run and the FlakySense report built from six such runs. Only the `hostname` attribute of the JUnit report was replaced; line endings are whatever git checks out.
- Pinned by the pair on those bytes — CONDITIONAL GO / exit 1 by default, NO GO / exit 2 under `--junit-dialect pytest` — and by the Playwright fixture now shipping conditionally with no flag.
- ADR-002's safety property is untouched: a miss still counts as a real failure.
- Not covered: a JUnit report and a flakiness report produced on different operating systems. Separators are the report's own bytes in both tools, so a path-shaped `classname` written with `\` will not join one written with `/`. No such pair was observed.
