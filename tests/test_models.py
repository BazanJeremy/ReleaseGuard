"""Contract tests for the ADR-001 data models.

These pin the model invariants the S2 evaluator will rely on: count
consistency, bounded scores, optional signals, and lossless JSON round-trips.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from releaseguard.models import (
    CoverageSignal,
    FlakinessSignal,
    GateResult,
    ReleaseRecommendation,
    ReleaseSignals,
    SignalKind,
    SignalScore,
    TestResultsSignal,
    Verdict,
)


def make_tests_signal(**overrides) -> TestResultsSignal:
    defaults = dict(total=8, passed=8, failed=0, skipped=0, failed_test_ids=[])
    defaults.update(overrides)
    return TestResultsSignal(**defaults)


class TestTestResultsSignal:
    def test_counts_must_sum_to_total(self):
        with pytest.raises(ValidationError, match="!= total"):
            make_tests_signal(total=8, passed=5, failed=1, skipped=0)

    def test_failed_ids_must_match_failed_count(self):
        with pytest.raises(ValidationError, match="failed_test_ids"):
            make_tests_signal(total=8, passed=7, failed=1, skipped=0, failed_test_ids=[])

    def test_valid_signal_with_failures(self):
        signal = make_tests_signal(
            total=8,
            passed=6,
            failed=2,
            skipped=0,
            failed_test_ids=[
                "tests/test_payment.py::test_refund_idempotency",
                "tests/test_payment.py::test_currency_rounding",
            ],
        )
        assert signal.failed == 2

    def test_negative_counts_rejected(self):
        with pytest.raises(ValidationError):
            make_tests_signal(total=-1, passed=-1)

    def test_frozen(self):
        signal = make_tests_signal()
        with pytest.raises(ValidationError):
            signal.total = 99


class TestCoverageSignal:
    @pytest.mark.parametrize("rate", [-0.01, 1.01])
    def test_line_rate_out_of_bounds_rejected(self, rate):
        with pytest.raises(ValidationError):
            CoverageSignal(line_rate=rate)

    @pytest.mark.parametrize("rate", [0.0, 0.6, 1.0])
    def test_line_rate_bounds_accepted(self, rate):
        assert CoverageSignal(line_rate=rate).line_rate == rate


class TestReleaseSignals:
    def test_tests_signal_is_mandatory(self):
        with pytest.raises(ValidationError):
            ReleaseSignals(coverage=CoverageSignal(line_rate=0.9))

    def test_coverage_and_flakiness_default_to_absent(self):
        signals = ReleaseSignals(tests=make_tests_signal())
        assert signals.coverage is None
        assert signals.flakiness is None

    def test_full_bundle(self):
        signals = ReleaseSignals(
            tests=make_tests_signal(),
            coverage=CoverageSignal(line_rate=0.88),
            flakiness=FlakinessSignal(
                flaky_test_ids=["tests/test_search.py::test_search_pagination"]
            ),
        )
        assert signals.flakiness.source == "flakysense"


class TestReleaseRecommendation:
    def make_recommendation(self, **overrides) -> ReleaseRecommendation:
        defaults = dict(
            verdict=Verdict.CONDITIONAL_GO,
            score=0.62,
            gates=[
                GateResult(
                    gate_id="G1",
                    name="real failure",
                    tripped=False,
                    detail="1 failure excused as flaky",
                )
            ],
            signals=[
                SignalScore(
                    kind=SignalKind.TESTS,
                    score=1.0,
                    weight=0.5,
                    detail="9/9 non-excused tests passed",
                )
            ],
            conditions=["excused flaky failure: tests/test_search.py::test_search_pagination"],
            rationale="No blocker; score 0.62 below GO threshold 0.80.",
            generated_by="system1",
            created_at=datetime(2026, 7, 10, 10, 5, tzinfo=timezone.utc),
        )
        defaults.update(overrides)
        return ReleaseRecommendation(**defaults)

    def test_score_none_allowed_for_gated_verdicts(self):
        rec = self.make_recommendation(verdict=Verdict.NO_GO, score=None)
        assert rec.score is None

    def test_score_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            self.make_recommendation(score=1.2)

    def test_generated_by_restricted(self):
        with pytest.raises(ValidationError):
            self.make_recommendation(generated_by="system3")

    def test_json_round_trip_is_lossless(self):
        rec = self.make_recommendation()
        restored = ReleaseRecommendation.model_validate(rec.model_dump(mode="json"))
        assert restored == rec

    def test_verdict_serialized_values(self):
        assert Verdict.GO.value == "go"
        assert Verdict.CONDITIONAL_GO.value == "conditional_go"
        assert Verdict.NO_GO.value == "no_go"
