"""Data models for the release gate — ADR-001.

Input side: three normalized signals parsed from standard CI artifacts
(JUnit XML, Cobertura XML, FlakySense JSON). Output side: an explainable
recommendation carrying every gate and signal that shaped the verdict.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Mirrors the FlakySense convention ("system1_fallback" / "system2_llm") so
# both tools read the same way side by side; here System 1 is the
# primary path, not a fallback.
GenerationPath = Literal["system1", "system2_llm"]


class Verdict(str, Enum):
    """Release decision. NO_GO requires a tripped gate, never a low score."""

    GO = "go"
    CONDITIONAL_GO = "conditional_go"
    NO_GO = "no_go"


class SignalKind(str, Enum):
    """The three fused signal families of ADR-001."""

    TESTS = "tests"
    COVERAGE = "coverage"
    FLAKINESS = "flakiness"


class TestResultsSignal(BaseModel):
    """Aggregated outcome of one test run (from a JUnit XML report)."""

    # Tell pytest this is domain vocabulary, not a collectable test class.
    __test__ = False

    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0, description="Failures and errors combined")
    skipped: int = Field(ge=0)
    failed_test_ids: list[str] = Field(
        default_factory=list,
        description="Node ids of failing tests, e.g. 'tests/test_api.py::test_login'",
    )

    @model_validator(mode="after")
    def _counts_consistent(self) -> "TestResultsSignal":
        if self.passed + self.failed + self.skipped != self.total:
            raise ValueError(
                f"passed({self.passed}) + failed({self.failed}) + "
                f"skipped({self.skipped}) != total({self.total})"
            )
        if len(self.failed_test_ids) != self.failed:
            raise ValueError(
                f"failed_test_ids has {len(self.failed_test_ids)} entries "
                f"but failed={self.failed}"
            )
        return self


class CoverageSignal(BaseModel):
    """Line coverage of the build under evaluation (from a Cobertura XML report)."""

    model_config = ConfigDict(frozen=True)

    line_rate: float = Field(ge=0, le=1)


class FlakinessSignal(BaseModel):
    """Known-flaky tests for this suite (from a FlakySense JSON report)."""

    model_config = ConfigDict(frozen=True)

    flaky_test_ids: list[str] = Field(
        default_factory=list,
        description="Node ids flagged is_flaky by the upstream detector",
    )
    source: str = Field(
        default="flakysense",
        min_length=1,
        description="Provenance label for the audit trail",
    )


class ReleaseSignals(BaseModel):
    """Everything the evaluator sees. Tests are mandatory (no evidence, no
    verdict); coverage and flakiness are optional — absent signals renormalize
    the remaining weights and land in the conditions list (ADR-001)."""

    model_config = ConfigDict(frozen=True)

    tests: TestResultsSignal
    coverage: CoverageSignal | None = None
    flakiness: FlakinessSignal | None = None


class GateResult(BaseModel):
    """Outcome of one hard gate — recorded even when it does not trip."""

    model_config = ConfigDict(frozen=True)

    gate_id: str = Field(min_length=1, description="'G1' or 'G2'")
    name: str = Field(min_length=1)
    tripped: bool
    detail: str = Field(min_length=1)


class SignalScore(BaseModel):
    """One normalized signal with the weight it carried in the final score."""

    model_config = ConfigDict(frozen=True)

    kind: SignalKind
    score: float = Field(ge=0, le=1)
    weight: float = Field(ge=0, le=1)
    detail: str = Field(min_length=1)


class ReleaseRecommendation(BaseModel):
    """Final verdict for a release manager — self-contained and auditable."""

    verdict: Verdict
    score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Weighted score; None when a hard gate already decided",
    )
    gates: list[GateResult]
    signals: list[SignalScore]
    conditions: list[str] = Field(
        default_factory=list,
        description="Named risks: excused flaky failures, missing signals, weak spots",
    )
    rationale: str = Field(min_length=1)
    generated_by: GenerationPath
    created_at: datetime
