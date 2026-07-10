"""Command-line interface — ADR-003.

Exit codes map the verdict (ADR-001): 0 GO, 1 CONDITIONAL GO, 2 NO GO,
3 error. argparse's default usage-error exit code of 2 would collide with
NO GO — a CI script could mistake a typo for a blocked release — so the
parser is overridden to exit 3 on usage errors. Output is ASCII-only
(legacy Windows consoles garble anything else).
"""

from __future__ import annotations

import argparse
import json
import sys

from releaseguard import __version__, policy
from releaseguard.evaluator import ReleaseEvaluator
from releaseguard.ingest import parse_cobertura, parse_flakysense, parse_junit
from releaseguard.llm import client_from_env
from releaseguard.models import ReleaseRecommendation, ReleaseSignals, Verdict

EXIT_BY_VERDICT = {Verdict.GO: 0, Verdict.CONDITIONAL_GO: 1, Verdict.NO_GO: 2}
EXIT_ERROR = 3

_VERDICT_LABELS = {
    Verdict.GO: "GO",
    Verdict.CONDITIONAL_GO: "CONDITIONAL GO",
    Verdict.NO_GO: "NO GO",
}


class _Parser(argparse.ArgumentParser):
    """Usage errors exit 3: argparse's default 2 collides with NO GO."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="releaseguard",
        description="Fuse test, coverage, and flakiness signals into an "
        "explainable go/no-go release recommendation.",
        epilog="Exit codes: 0 GO, 1 CONDITIONAL GO, 2 NO GO, 3 error.",
    )
    parser.add_argument("--version", action="version", version=f"releaseguard {__version__}")
    parser.add_argument(
        "--junit", required=True, metavar="PATH", help="JUnit XML test report (required)"
    )
    parser.add_argument(
        "--coverage", metavar="PATH", help="Cobertura XML coverage report (optional)"
    )
    parser.add_argument(
        "--flaky", metavar="PATH", help="FlakySense JSON report (optional)"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit the full recommendation as JSON"
    )
    tuning = parser.add_argument_group(
        "policy overrides (defaults per ADR-001; weights are not tunable)"
    )
    tuning.add_argument(
        "--coverage-floor", type=float, default=policy.COVERAGE_FLOOR, metavar="RATE"
    )
    tuning.add_argument(
        "--coverage-target", type=float, default=policy.COVERAGE_TARGET, metavar="RATE"
    )
    tuning.add_argument(
        "--go-threshold", type=float, default=policy.GO_THRESHOLD, metavar="SCORE"
    )
    tuning.add_argument(
        "--flaky-penalty", type=float, default=policy.FLAKY_PENALTY, metavar="FACTOR"
    )
    return parser


def render_text(rec: ReleaseRecommendation) -> str:
    lines = [f"ReleaseGuard verdict: {_VERDICT_LABELS[rec.verdict]}"]
    if rec.score is not None:
        lines[0] += f" (score {rec.score:.2f})"
    lines += ["", "Gates:"]
    for gate in rec.gates:
        status = "BLOCK" if gate.tripped else "pass "
        lines.append(f"  [{status}] {gate.gate_id} {gate.name}: {gate.detail}")
    lines += ["", "Signals:"]
    for signal in rec.signals:
        lines.append(
            f"  {signal.kind.value:<10} {signal.score:.2f} "
            f"(weight {signal.weight:.2f}) {signal.detail}"
        )
    if rec.conditions:
        lines += ["", "Conditions:"]
        lines += [f"  - {condition}" for condition in rec.conditions]
    lines += ["", f"Rationale ({rec.generated_by}):", f"  {rec.rationale}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        signals = ReleaseSignals(
            tests=parse_junit(args.junit),
            coverage=parse_cobertura(args.coverage) if args.coverage else None,
            flakiness=parse_flakysense(args.flaky) if args.flaky else None,
        )
        evaluator = ReleaseEvaluator(
            client_from_env(),
            coverage_floor=args.coverage_floor,
            coverage_target=args.coverage_target,
            go_threshold=args.go_threshold,
            flaky_penalty=args.flaky_penalty,
        )
        recommendation = evaluator.evaluate(signals)
    except (OSError, ValueError, SyntaxError) as exc:
        # Covers missing files, malformed XML (ParseError is a SyntaxError),
        # bad JSON (JSONDecodeError is a ValueError), dialect violations,
        # NoTestEvidenceError, and invalid threshold combinations.
        print(f"releaseguard: error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(json.dumps(recommendation.model_dump(mode="json"), indent=2))
    else:
        print(render_text(recommendation))
    return EXIT_BY_VERDICT[recommendation.verdict]


if __name__ == "__main__":
    sys.exit(main())
