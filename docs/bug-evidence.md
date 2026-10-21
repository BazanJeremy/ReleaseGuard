# Bug Evidence Log

Bugs caught by this project's own tests and demo runs, documented before
being fixed (series-wide principle #4). Each entry: what was caught, why it
mattered.

## #1 — Fixture `coverage.xml` files silently excluded by `.gitignore` (2026-07-10, S1)

- **Caught by:** `tests/test_fixtures.py::TestArtifactsWellFormed::test_all_artifacts_present` — on its very first CI run (PR #1), while the full suite passed locally.
- **What happened:** the root `.gitignore` listed `coverage.xml` to keep the repo's own coverage artifacts out of git. `git add data/samples/` therefore silently skipped the three scenario fixtures named `coverage.xml`. Locally the untracked files still existed on disk, so all 39 tests passed; on CI the checkout had no such files and 7 fixture tests failed.
- **Why it mattered:** without the artifact-presence test, S2 would have been built against fixtures that do not exist in the repository — every clone (a reader's, CI, a future machine) would be broken while the author's machine stayed green. This is exactly the failure class ("works on my machine" via untracked files) that fixture-integrity contract tests exist to catch, and it validates running them in CI from the first PR.
- **Fix:** anchor the ignore rules to the repository root (`/coverage.xml`, `/.coverage`) so fixture files under `data/samples/` are trackable, then add the missing files.

## #2 — Bare-name join would excuse a real failure (2026-07-10, S3) — verified counterfactual

- **Pinned by:** `tests/test_evaluator.py::TestGateRules::test_name_collision_does_not_excuse_real_failure`.
- **The counterfactual, verified live before documenting:** take a real failure `tests/test_upload_api.py::test_upload` and a *different* flaky test that happens to share its bare name, `tests/test_upload_ui.py::test_upload`. Under the accepted ADR-002 join (full node ids) the verdict is **NO GO** — the failure finds no flaky match. Simulating the rejected bare-name join (collapsing both ids to `test_upload`) flips the same inputs to **CONDITIONAL GO, score 0.875**, with the condition `excused flaky failure: test_upload` — a real payment-of-attention failure waved through as "the usual flaky one".
- **Why it mattered:** this is the one direction a release gate must never fail toward (false GO), and it is exactly why ADR-002 rejected the simpler bare-name option. The counterfactual turns a design argument into reproducible evidence, and the regression test keeps the safety property from eroding silently.
- **Fix:** none needed — the accepted design already prevents it; the test pins it.

## #3 — Em-dashes in verdict output garbled on a real console (2026-07-10, S3)

- **Caught by:** the first local dogfood run (`releaseguard --junit reports/junit.xml --coverage coverage.xml` on this repo's own artifacts) — the condition line rendered as `flakiness signal missing �` on the Windows console.
- **What happened:** four user-facing strings in the evaluator (missing-signal conditions, the G2 absent-signal detail, the no-evidence error) contained typographic em-dashes, violating the project's ASCII-only output convention. The CLI test asserting `out.isascii()` ran only the conditional scenario, whose conditions happen to be pure ASCII — the missing-signal code path was never checked.
- **Why it mattered:** the exact failure mode the convention exists for (legacy Windows consoles garble non-ASCII), surfaced by the tool's own deployment story on its first run. A test can only protect the paths it exercises: the assertion existed, the coverage of it didn't.
- **Fix:** ASCII hyphens in all user-facing strings; the junit-only CLI test (which exercises the missing-signal path) now asserts `isascii()` too.

## #4 — The identity join was dead on JS-runner reports (2026-10-12, ADR-004)

- **Caught by:** wiring FlakySense and ReleaseGuard back to back on a real JUnit report from another repository (`bazanjeremy.github.io`, a 204-test Playwright suite) — not by this project's own tests, which only ever saw pytest artifacts.
- **What happened:** Playwright puts a **file path** in `classname` and emits no `file` attribute. The ADR-002 reconstruction splits `classname` on dots, finds no CapWords segment, and consumes the whole string as a module path, so `invariants\zero-js.spec.ts` became `invariants\zero-js/spec/ts.py`. FlakySense, reading the same file, falls back to `classname` verbatim. The two keys cannot be equal, so no failure in such a report can ever be matched against the flaky list.
- **Measured, not inferred:** on that report, **0 of 204** identities agree and **0** testcases carry a `file` attribute — the join is not degraded, it is dead for every test. End to end on the fixture added with ADR-004 (`data/samples/dialect_playwright/`, whose `classname`/`name` pairs are copied from those real bytes; only the `<failure>` element is constructed), the single failing test *is* in the flaky list, and the CLI returns **NO GO, exit 2, G1 tripped**. With `--junit-dialect path`, the same bytes return **CONDITIONAL GO 0.72, exit 1**, the failure appearing as `excused flaky failure:`. On the full 204-test report the counterfactual is **CONDITIONAL GO 0.9837** against NO GO.
- **Why it mattered, and why it hid:** the failure direction was the *safe* one. ADR-002's conservative-on-miss property held, so a dead join never waved a failure through — it blocked releases that should have shipped conditionally, and the verdict looked merely strict. A defect whose symptom is excess caution produces no complaint, which is exactly why it needed a measurement rather than a report. It also means the cross-signal rule — the one behavior no single parser can produce, and the project's whole argument — was silently absent on an entire family of artifacts.
- **Fix:** the dialect is declared rather than guessed ([ADR-004](adr/ADR-004-junit-dialect-declared.md)); `pytest` stays the default, `path` joins verbatim. Pinned by the fixture-integrity properties that keep it reproducing the defect, by the NO GO / CONDITIONAL GO pair on the same bytes, and by a no-false-GO test under the new dialect.
- **Left unfixed, deliberately:** a test name carrying non-ASCII characters still reaches the verdict text through `G1 detail` and the excused-failure conditions, so `isascii()` is **False** on that output — measured on the same report, where **204 of 204** names are non-ASCII (`›`, `é`, `×`). This is bug #3's convention failing on *input* data rather than on the project's own strings, it is independent of the join (repairing the join only moves the id from `G1` to the conditions), and whether the ASCII-only rule should hold over data the tool does not author is a decision, not an oversight. Reported rather than patched.
