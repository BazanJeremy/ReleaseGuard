"""Shared fixtures. The API-key scrub is suite-wide and autouse (FlakySense
ADR-004 pattern): no test may accidentally exercise a live LLM — System 2
behavior is tested through injected fakes only."""

from pathlib import Path

import pytest

SAMPLES = Path(__file__).parent.parent / "data" / "samples"


@pytest.fixture(autouse=True)
def scrub_anthropic_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def samples() -> Path:
    return SAMPLES
