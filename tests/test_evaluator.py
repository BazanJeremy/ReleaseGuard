"""Evaluator tests — the three canonical scenarios end to end (parsers
included), then each ADR-001 rule in isolation on crafted signals."""

import pytest

from releaseguard import policy
from releaseguard.evaluator import NoTestEvidenceError, ReleaseEvaluator
from releaseguard.ingest import parse_cobertura, parse_flakysense, parse_junit
from releaseguard.models import (
    CoverageSignal,
    FlakinessSignal,
    ReleaseSignals,
    SignalKind,
    TestResultsSignal,
    Verdict,
)


def load_scenario(samples, name: str) -> ReleaseSignals:
    base = samples / name
    return ReleaseSignals(
        tests=parse_junit(base / "junit.xml"),
        coverage=parse_cobertura(base / "coverage.xml"),
        flakiness=parse_flakysense(base / "flakysense-report.json"),
    )


class TestCanonicalScenarios:
    def test_go(self, samples):
        rec = ReleaseEvaluator().evaluate(load_scenario(samples, "scenario_go"))
        assert rec.verdict is Verdict.GO
        assert rec.score == 1.0
        assert rec.conditions == []
        assert not any(g.tripped for g in rec.gates)

    def test_no_go_real_failures_trip_g1(self, samples):
        rec = ReleaseEvaluator().evaluate(load_scenario(samples, "scenario_no_go"))
        assert rec.verdict is Verdict.NO_GO
        assert rec.score is None
        g1 = next(g for g in rec.gates if g.gate_id == "G1")
        assert g1.tripped
        assert "test_refund_idempotency" in g1.detail
        # The flaky list existed but was irrelevant: membership, not existence.
        assert "excused" not in " ".join(rec.conditions)

    def test_conditional_flaky_excused_failure(self, samples):
        rec = ReleaseEvaluator().evaluate(load_scenario(samples, "scenario_conditional"))
        assert rec.verdict is Verdict.CONDITIONAL_GO
        assert rec.score == pytest.approx(0.62, abs=0.001)
        assert not any(g.tripped for g in rec.gates)
        assert any(
            "excused flaky failure: tests/test_search.py::test_search_pagination" in c
            for c in rec.conditions
        )
        assert rec.generated_by == "system1"


class TestGateRules:
    def make_signals(self, **overrides) -> ReleaseSignals:
        defaults = dict(
            tests=TestResultsSignal(total=10, passed=10, failed=0, skipped=0),
            coverage=CoverageSignal(line_rate=0.9),
            flakiness=FlakinessSignal(flaky_test_ids=[]),
        )
        defaults.update(overrides)
        return ReleaseSignals(**defaults)

    def test_g2_coverage_below_floor_blocks(self):
        signals = self.make_signals(coverage=CoverageSignal(line_rate=0.55))
        rec = ReleaseEvaluator().evaluate(signals)
        assert rec.verdict is Verdict.NO_GO
        assert next(g for g in rec.gates if g.gate_id == "G2").tripped

    def test_excused_failure_caps_go_even_with_high_score(self):
        """Score would clear the GO threshold; the excused failure still caps."""
        signals = self.make_signals(
            tests=TestResultsSignal(
                total=50,
                passed=49,
                failed=1,
                skipped=0,
                failed_test_ids=["tests/test_x.py::test_a"],
            ),
            flakiness=FlakinessSignal(flaky_test_ids=["tests/test_x.py::test_a"]),
        )
        rec = ReleaseEvaluator().evaluate(signals)
        assert rec.score >= policy.GO_THRESHOLD
        assert rec.verdict is Verdict.CONDITIONAL_GO

    def test_missing_flakiness_signal_makes_all_failures_real(self):
        signals = self.make_signals(
            tests=TestResultsSignal(
                total=10,
                passed=9,
                failed=1,
                skipped=0,
                failed_test_ids=["tests/test_x.py::test_a"],
            ),
            flakiness=None,
        )
        rec = ReleaseEvaluator().evaluate(signals)
        assert rec.verdict is Verdict.NO_GO

    def test_missing_coverage_renormalizes_weights_and_adds_condition(self):
        signals = self.make_signals(coverage=None)
        rec = ReleaseEvaluator().evaluate(signals)
        assert rec.verdict is Verdict.GO
        assert sum(s.weight for s in rec.signals) == pytest.approx(1.0)
        weights = {s.kind: s.weight for s in rec.signals}
        assert weights[SignalKind.TESTS] == pytest.approx(2 / 3, abs=0.001)
        assert any("coverage signal missing" in c for c in rec.conditions)

    def test_zero_executed_tests_is_an_error_not_a_verdict(self):
        signals = self.make_signals(
            tests=TestResultsSignal(total=3, passed=0, failed=0, skipped=3)
        )
        with pytest.raises(NoTestEvidenceError):
            ReleaseEvaluator().evaluate(signals)

    def test_conditional_names_weakest_signal(self):
        signals = self.make_signals(coverage=CoverageSignal(line_rate=0.63))
        rec = ReleaseEvaluator().evaluate(signals)
        assert rec.verdict is Verdict.CONDITIONAL_GO
        assert any(c.startswith("weakest signal: coverage") for c in rec.conditions)


class FakeLLMClient:
    def __init__(self, response: str = "Narrated rationale.", error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        return self.response


class TestSystem2Narration:
    def test_conditional_uses_llm_when_available(self, samples):
        client = FakeLLMClient()
        rec = ReleaseEvaluator(llm_client=client).evaluate(
            load_scenario(samples, "scenario_conditional")
        )
        assert rec.generated_by == "system2_llm"
        assert rec.rationale == "Narrated rationale."
        assert len(client.calls) == 1

    def test_llm_never_alters_verdict_score_or_conditions(self, samples):
        signals = load_scenario(samples, "scenario_conditional")
        baseline = ReleaseEvaluator().evaluate(signals)
        narrated = ReleaseEvaluator(llm_client=FakeLLMClient()).evaluate(signals)
        assert narrated.verdict == baseline.verdict
        assert narrated.score == baseline.score
        assert narrated.conditions == baseline.conditions

    def test_llm_failure_degrades_to_system1(self, samples):
        client = FakeLLMClient(error=RuntimeError("api down"))
        rec = ReleaseEvaluator(llm_client=client).evaluate(
            load_scenario(samples, "scenario_conditional")
        )
        assert rec.generated_by == "system1"
        assert rec.rationale.startswith("No blocker;")

    def test_go_verdict_never_calls_llm(self, samples):
        client = FakeLLMClient()
        rec = ReleaseEvaluator(llm_client=client).evaluate(
            load_scenario(samples, "scenario_go")
        )
        assert rec.generated_by == "system1"
        assert client.calls == []

    def test_no_go_verdict_never_calls_llm(self, samples):
        client = FakeLLMClient()
        rec = ReleaseEvaluator(llm_client=client).evaluate(
            load_scenario(samples, "scenario_no_go")
        )
        assert rec.generated_by == "system1"
        assert client.calls == []


class TestClientFromEnv:
    def test_none_without_api_key(self):
        from releaseguard.llm import client_from_env

        assert client_from_env() is None
