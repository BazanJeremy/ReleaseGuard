# Agent code review vs documented evidence — PR #2 (2026-07-23)

Retrospective evaluation of the `code-review` command from
`anthropics/claude-plugins-official`, run against
[PR #2 — S2 Implementation](https://github.com/BazanJeremy/ReleaseGuard/pull/2)
(parsers, release evaluator, System 2 narration; merged 2026-07-10,
+844/-4 across 12 files).

## Method and adaptations

The plugin's protocol was followed as specified — 5 parallel Sonnet review
agents (CLAUDE.md compliance, shallow diff bug scan, git-history context,
prior-PR feedback, code-comment contracts), then one Haiku confidence-scoring
agent per raised issue (0–100 rubric, issues below 80 dropped) — with three
deliberate adaptations:

1. **Eligibility check skipped** — the protocol declines closed PRs; reviewing
   this merged PR retrospectively was the point of the exercise.
2. **No PR comment posted** — the protocol's final step comments on the PR;
   findings were delivered as this report instead (standing rule: no public,
   outward-facing action without an explicit human GO).
3. **Baseline substituted** — no PR in this repository has human review
   comments (verified: 0 reviews, 0 comments on PRs #1–#4), so the comparison
   baseline is the repository's own documented evidence:
   [bug-evidence.md](bug-evidence.md), the accepted ADRs, and the README's
   known limitations. Ground truth for PR #2: exactly one defect is documented
   as introduced by it and fixed later — bug-evidence #3 (em-dashes garbled on
   a real Windows console, fixed in S3 by `0afebab`).

## Raw agent findings

| Agent (angle) | Raised | Confidence score | Retained (≥ 80) |
|---|---|---|---|
| #1 CLAUDE.md compliance | Em-dashes in 4 user-facing evaluator strings | — (deduplicated into A) | — |
| #2 Shallow diff bug scan | FlakySense parser: no per-entry validation → opaque `KeyError`/`TypeError` | 55 | No |
| #3 Git-history context | Em-dashes (traced rule to first commit, fix to `0afebab`) | — (deduplicated into A) | — |
| #4 Prior-PR feedback | Em-dashes (via "a later PR had to fix this") | 100 (issue A, scored once) | **Yes** |
| #5 Code-comment contracts | Nothing — all stated invariants verified honored | n/a | n/a |

Final protocol output: **1 issue** — the em-dash defect, scored 100 after
independent re-verification (byte-level check of the U+2014 sequences and the
strings' path to stdout/stderr through `cli.py`).

## Comparison against the documented baseline

**Found (1/1 — the full known ground truth).** The em-dash defect was raised
independently by 3 of 5 agents. The human process caught it one sprint late,
in S3's first dogfood run; the agent protocol run at PR time would plausibly
have blocked it pre-merge — agent #1's angle (diff vs the CLAUDE.md ASCII-only
rule, in force since the first commit) requires no hindsight.

**Missed: nothing.** The other documented entries are not PR #2 defects and
were correctly left alone: bug-evidence #1 predates the PR (S1), and
bug-evidence #2 is a *verified counterfactual* — agents #3 and #5 both
re-verified that the ADR-002 node-id join's conservative direction holds in
the PR's code, and correctly declined to flag it.

**False positives retained: zero.** The known limitations (three parsers only,
weights not CLI-tunable, no containerization, key-gated narration) are
deliberate, ADR-documented cuts; no agent flagged any of them. Two agents
independently noticed the `DEFAULT_MODEL` string in `llm.py` looked unusual
and explicitly declined to flag it without evidence — correct restraint (it is
a valid model identifier).

**Filtered as designed.** The one sub-threshold finding (FlakySense per-entry
validation, 55/100) is a real but minor defensive-programming gap: the scorer
verified the crash reproduces, then correctly weighed that it cannot corrupt a
verdict (loud failure, not a false GO), is unlikely given the upstream tool's
stable output contract, and is not required by any project rule. A human
senior reviewer might mention it as a nit; the protocol's own false-positive
guidance ("general code quality issues, unless explicitly required") says to
drop it. Reasonable either way — recorded here so the observation is not lost.

## Assessment of the plugin

- **Precision 1/1, recall 1/1** against the documented ground truth. Small
  sample (one PR, one known defect) — indicative, not statistical.
- **The redundancy is the strength.** Three independent angles converged on
  the real defect; the confidence-scoring pass then filtered the weaker
  finding. The diff-only agent (#2) missed the em-dashes — the catch came from
  the agents with access to project rules and history. A repo with a
  substantive CLAUDE.md and ADR trail gets materially better reviews from
  this plugin than a bare diff would.
- **Honesty caveat:** agents #3 and #4 found the defect partly via the repo's
  own paper trail (bug-evidence #3, the S3 fix commit) — unavailable in a true
  pre-merge review. Agent #1's catch is the one that generalizes.
- **Cost:** 7 sub-agent runs, ≈ 440k sub-agent tokens, ~6 minutes wall-clock
  (agents run in parallel). Proportionate for a gate on substantial PRs;
  oversized for one-line changes (the protocol's own eligibility check
  addresses this).

## Verdict

Adopted for substantial PRs in this repository (project-scoped command in
`.claude/commands/`, installed 2026-07-23). Standing rule: the review runs
read-only; posting any comment to a PR requires an explicit human GO.
