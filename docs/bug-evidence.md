# Bug Evidence Log

Bugs caught by this project's own tests, documented before being fixed
(portfolio principle #4). Each entry: what the test caught, why it mattered.

## #1 — Fixture `coverage.xml` files silently excluded by `.gitignore` (2026-07-10, S1)

- **Caught by:** `tests/test_fixtures.py::TestArtifactsWellFormed::test_all_artifacts_present` — on its very first CI run (PR #1), while the full suite passed locally.
- **What happened:** the root `.gitignore` listed `coverage.xml` to keep the repo's own coverage artifacts out of git. `git add data/samples/` therefore silently skipped the three scenario fixtures named `coverage.xml`. Locally the untracked files still existed on disk, so all 39 tests passed; on CI the checkout had no such files and 7 fixture tests failed.
- **Why it mattered:** without the artifact-presence test, S2 would have been built against fixtures that do not exist in the repository — every clone (recruiter, CI, future machine) would be broken while the author's machine stayed green. This is exactly the failure class ("works on my machine" via untracked files) that fixture-integrity contract tests exist to catch, and it validates running them in CI from the first PR.
- **Fix:** anchor the ignore rules to the repository root (`/coverage.xml`, `/.coverage`) so fixture files under `data/samples/` are trackable, then add the missing files.
