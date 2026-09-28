"""The release gate — ADR-001 implemented end to end.

Layer 1: hard gates (G1 real failure, G2 coverage floor); any trip means
NO GO, no score. Layer 2: weighted score over the present signals, choosing
between GO and CONDITIONAL GO. System 2 (optional LLM) narrates CONDITIONAL
verdicts only; it may rewrite the rationale but never the verdict, the score,
or the conditions list — those stay deterministic and auditable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from releaseguard import policy
from releaseguard.llm import LLMClient
from releaseguard.models import (
    GateResult,
    GenerationPath,
    ReleaseRecommendation,
    ReleaseSignals,
    SignalKind,
    SignalScore,
    Verdict,
)

_NARRATOR_SYSTEM_PROMPT = (
    "You are the narrator of a release-readiness gate. You receive the "
    "deterministic verdict of the gate as JSON: verdict, weighted score, "
    "gate results, per-signal scores, and a list of conditions. Write a "
    "short rationale paragraph for a release manager: why the release "
    "is a conditional go, which signal drags it down, and what the listed "
    "conditions mean in practice. Never contradict the verdict or invent "
    "signals. Plain text, no markdown."
)


class NoTestEvidenceError(ValueError):
    """Raised when the test signal contains no executed test — no evidence,
    no verdict (ADR-001: an error, never a NO GO)."""


class ReleaseEvaluator:
    """Fuses the signals into a :class:`ReleaseRecommendation` (ADR-001).

    Thresholds are per-run tunable (CLI flags, ADR-003); the signal weights
    are deliberately not — changing the weighting is a governance decision
    that goes through a superseding ADR, not a command-line flag.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        *,
        coverage_floor: float = policy.COVERAGE_FLOOR,
        coverage_target: float = policy.COVERAGE_TARGET,
        go_threshold: float = policy.GO_THRESHOLD,
        flaky_penalty: float = policy.FLAKY_PENALTY,
    ) -> None:
        if not coverage_floor < coverage_target:
            raise ValueError(
                f"coverage_floor ({coverage_floor}) must be below "
                f"coverage_target ({coverage_target})"
            )
        self._llm_client = llm_client
        self._coverage_floor = coverage_floor
        self._coverage_target = coverage_target
        self._go_threshold = go_threshold
        self._flaky_penalty = flaky_penalty

    def evaluate(self, signals: ReleaseSignals) -> ReleaseRecommendation:
        executed = signals.tests.total - signals.tests.skipped
        if executed == 0:
            raise NoTestEvidenceError(
                "the test report contains no executed test - cannot evaluate a release"
            )

        flaky_ids = set(signals.flakiness.flaky_test_ids) if signals.flakiness else set()
        real_failures = [t for t in signals.tests.failed_test_ids if t not in flaky_ids]
        excused = [t for t in signals.tests.failed_test_ids if t in flaky_ids]

        gates = self._run_gates(signals, real_failures)
        signal_scores = self._score_signals(signals, real_failures, executed)
        conditions = self._collect_conditions(signals, excused)

        if any(gate.tripped for gate in gates):
            return self._recommend(
                verdict=Verdict.NO_GO,
                score=None,
                gates=gates,
                signals=signal_scores,
                conditions=conditions,
                rationale=self._rationale_no_go(gates),
            )

        score = round(sum(s.score * s.weight for s in signal_scores), 4)
        if score >= self._go_threshold and not excused:
            return self._recommend(
                verdict=Verdict.GO,
                score=score,
                gates=gates,
                signals=signal_scores,
                conditions=conditions,
                rationale=f"All gates passed; score {score:.2f} meets the "
                f"GO threshold {self._go_threshold:.2f}.",
            )

        # Excused failures cap the verdict at CONDITIONAL GO (ADR-001).
        conditions = conditions + self._weak_spot_conditions(signal_scores, score)
        rationale, generated_by = self._narrate_conditional(
            gates, signal_scores, conditions, score
        )
        return self._recommend(
            verdict=Verdict.CONDITIONAL_GO,
            score=score,
            gates=gates,
            signals=signal_scores,
            conditions=conditions,
            rationale=rationale,
            generated_by=generated_by,
        )

    # ------------------------------------------------------------------ gates

    def _run_gates(
        self, signals: ReleaseSignals, real_failures: list[str]
    ) -> list[GateResult]:
        g1 = GateResult(
            gate_id="G1",
            name="real failure",
            tripped=bool(real_failures),
            detail=(
                f"{len(real_failures)} non-flaky failure(s): "
                + ", ".join(real_failures)
                if real_failures
                else "no non-flaky failure"
            ),
        )
        if signals.coverage is None:
            g2 = GateResult(
                gate_id="G2",
                name="coverage floor",
                tripped=False,
                detail="coverage signal absent - gate not evaluated",
            )
        else:
            below = signals.coverage.line_rate < self._coverage_floor
            g2 = GateResult(
                gate_id="G2",
                name="coverage floor",
                tripped=below,
                detail=f"line coverage {signals.coverage.line_rate:.0%} vs "
                f"floor {self._coverage_floor:.0%}",
            )
        return [g1, g2]

    # ----------------------------------------------------------------- scores

    def _score_signals(
        self, signals: ReleaseSignals, real_failures: list[str], executed: int
    ) -> list[SignalScore]:
        raw: list[tuple[SignalKind, float, float, str]] = []

        considered = signals.tests.passed + len(real_failures)
        tests_score = signals.tests.passed / considered if considered else 1.0
        raw.append(
            (
                SignalKind.TESTS,
                tests_score,
                policy.WEIGHT_TESTS,
                f"{signals.tests.passed}/{considered} non-excused tests passed",
            )
        )

        if signals.coverage is not None:
            ramp = (signals.coverage.line_rate - self._coverage_floor) / (
                self._coverage_target - self._coverage_floor
            )
            raw.append(
                (
                    SignalKind.COVERAGE,
                    min(1.0, max(0.0, ramp)),
                    policy.WEIGHT_COVERAGE,
                    f"line coverage {signals.coverage.line_rate:.0%} on the "
                    f"{self._coverage_floor:.0%}-{self._coverage_target:.0%} ramp",
                )
            )

        if signals.flakiness is not None:
            ratio = len(signals.flakiness.flaky_test_ids) / executed
            raw.append(
                (
                    SignalKind.FLAKINESS,
                    max(0.0, 1.0 - self._flaky_penalty * ratio),
                    policy.WEIGHT_FLAKINESS,
                    f"{len(signals.flakiness.flaky_test_ids)} flaky of "
                    f"{executed} executed tests",
                )
            )

        # Absent signals renormalize the remaining weights (ADR-001).
        total_weight = sum(weight for _, _, weight, _ in raw)
        return [
            SignalScore(
                kind=kind,
                score=round(score, 4),
                weight=round(weight / total_weight, 4),
                detail=detail,
            )
            for kind, score, weight, detail in raw
        ]

    # ------------------------------------------------------------- conditions

    def _collect_conditions(
        self, signals: ReleaseSignals, excused: list[str]
    ) -> list[str]:
        # excused can only be non-empty when a flakiness signal exists
        source = signals.flakiness.source if signals.flakiness else "unknown"
        conditions = [
            f"excused flaky failure: {test_id} (source: {source})"
            for test_id in excused
        ]
        if signals.coverage is None:
            conditions.append("coverage signal missing - weights renormalized")
        if signals.flakiness is None:
            conditions.append(
                "flakiness signal missing - all failures treated as real, "
                "weights renormalized"
            )
        return conditions

    def _weak_spot_conditions(
        self, signal_scores: list[SignalScore], score: float
    ) -> list[str]:
        if score >= self._go_threshold:
            return []
        weakest = min(signal_scores, key=lambda s: s.score)
        return [
            f"weakest signal: {weakest.kind.value} at {weakest.score:.2f} "
            f"({weakest.detail})"
        ]

    # -------------------------------------------------------------- rationale

    def _rationale_no_go(self, gates: list[GateResult]) -> str:
        tripped = [g for g in gates if g.tripped]
        return "Blocked by " + "; ".join(
            f"{g.gate_id} ({g.name}): {g.detail}" for g in tripped
        )

    def _narrate_conditional(
        self,
        gates: list[GateResult],
        signal_scores: list[SignalScore],
        conditions: list[str],
        score: float,
    ) -> tuple[str, GenerationPath]:
        fallback = (
            f"No blocker; score {score:.2f} below GO threshold "
            f"{self._go_threshold:.2f}. Conditions: "
            + ("; ".join(conditions) if conditions else "none")
        )
        if self._llm_client is None:
            return fallback, "system1"
        payload = json.dumps(
            {
                "verdict": Verdict.CONDITIONAL_GO.value,
                "score": score,
                "gates": [g.model_dump() for g in gates],
                "signals": [s.model_dump() for s in signal_scores],
                "conditions": conditions,
            }
        )
        try:
            return self._llm_client.complete(_NARRATOR_SYSTEM_PROMPT, payload), "system2_llm"
        except Exception:
            return fallback, "system1"

    def _recommend(
        self,
        *,
        verdict: Verdict,
        score: float | None,
        gates: list[GateResult],
        signals: list[SignalScore],
        conditions: list[str],
        rationale: str,
        generated_by: GenerationPath = "system1",
    ) -> ReleaseRecommendation:
        return ReleaseRecommendation(
            verdict=verdict,
            score=score,
            gates=gates,
            signals=signals,
            conditions=conditions,
            rationale=rationale,
            generated_by=generated_by,
            created_at=datetime.now(timezone.utc),
        )
