# ReleaseGuard

> Release-readiness agent — fuses test results, coverage, and flakiness signals into a single, explainable **go / no-go** recommendation.

**Status: 🚧 S3 — Integration in progress.** Portfolio project P5 of a 6-project AI Test Engineering portfolio.

## The problem

Release managers aggregate quality signals by hand: a test report here, a coverage dashboard there, tribal knowledge about which failures are "the usual flaky ones". The synthesis lives in someone's head — unauditable, unrepeatable, and lost when that person is on leave.

ReleaseGuard turns that synthesis into a deterministic, explainable gate:

- **Ingest** standard CI artifacts: JUnit XML (tests), Cobertura XML (coverage), FlakySense JSON (flakiness).
- **Decide** through hard gates + weighted scoring: `GO` / `CONDITIONAL GO` / `NO GO`.
- **Explain** every verdict: which gate tripped, which signal dragged the score, what conditions apply.

An optional LLM layer (System 2) narrates borderline verdicts; the deterministic core (System 1) never needs an API key.

## Roadmap

- ✅ **S1 — Architecture**: ADR-001 gate model, Pydantic v2 models, fixtures, contract tests
- ✅ **S2 — Implementation**: parsers, scoring engine, env-gated LLM narrative
- **S3 — Integration**: CLI, dogfood CI gate, senior README ⟵ *current*

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m pytest
```

Architecture decisions are recorded in [docs/adr/](docs/adr/).
