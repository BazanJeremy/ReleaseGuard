# Bug Evidence Log

Bugs caught by this project's own tests and demo runs, documented before
being fixed (series-wide principle #4). Each entry: what was caught, why it
mattered.

## #1 — Fixture `coverage.xml` files silently excluded by `.gitignore` (2026-07-10, S1)

- **Caught by:** `tests/test_fixtures.py::TestArtifactsWellFormed::test_all_artifacts_present` — on its very first CI run (PR #1), while the full suite passed locally.
- **What happened:** the root `.gitignore` listed `coverage.xml` to keep the repo's own coverage artifacts out of git. `git add data/samples/` therefore silently skipped the three scenario fixtures named `coverage.xml`. Locally the untracked files still existed on disk, so all 39 tests passed; on CI the checkout had no such files and 7 fixture tests failed.
- **Why it mattered:** without the artifact-presence test, S2 would have been built against fixtures that do not exist in the repository — every clone (recruiter, CI, future machine) would be broken while the author's machine stayed green. This is exactly the failure class ("works on my machine" via untracked files) that fixture-integrity contract tests exist to catch, and it validates running them in CI from the first PR.
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
