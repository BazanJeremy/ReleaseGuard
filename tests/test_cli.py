"""CLI contract tests — ADR-003: exit codes, output surfaces, overrides."""

import json

import pytest

from releaseguard.cli import main
from releaseguard.models import ReleaseRecommendation


def run_cli(samples, scenario: str, *extra: str, capsys=None) -> tuple[int, str]:
    base = samples / scenario
    argv = [
        "--junit", str(base / "junit.xml"),
        "--coverage", str(base / "coverage.xml"),
        "--flaky", str(base / "flakysense-report.json"),
        *extra,
    ]
    code = main(argv)
    out = capsys.readouterr().out if capsys else ""
    return code, out


class TestExitCodes:
    """0 GO / 1 CONDITIONAL GO / 2 NO GO / 3 error (ADR-001)."""

    @pytest.mark.parametrize(
        ("scenario", "expected"),
        [("scenario_go", 0), ("scenario_conditional", 1), ("scenario_no_go", 2)],
    )
    def test_verdict_exit_codes(self, samples, capsys, scenario, expected):
        code, _ = run_cli(samples, scenario, capsys=capsys)
        assert code == expected

    def test_missing_file_exits_3(self, capsys):
        assert main(["--junit", "does/not/exist.xml"]) == 3
        assert "error" in capsys.readouterr().err

    def test_usage_error_exits_3_not_argparses_2(self, capsys):
        """argparse's default exit 2 would collide with NO GO (ADR-003)."""
        with pytest.raises(SystemExit) as excinfo:
            main([])  # --junit is required
        assert excinfo.value.code == 3

    def test_zero_executed_tests_exits_3(self, tmp_path, capsys):
        report = tmp_path / "junit.xml"
        report.write_text(
            '<testsuite><testcase classname="tests.test_x" name="test_a">'
            "<skipped/></testcase></testsuite>"
        )
        assert main(["--junit", str(report)]) == 3
        assert "no executed test" in capsys.readouterr().err

    def test_invalid_threshold_combination_exits_3(self, samples, capsys):
        code, _ = run_cli(
            samples, "scenario_go", "--coverage-floor", "0.9",
            "--coverage-target", "0.8", capsys=capsys,
        )
        assert code == 3


class TestOutputs:
    def test_text_output_shows_verdict_gates_and_conditions(self, samples, capsys):
        _, out = run_cli(samples, "scenario_conditional", capsys=capsys)
        assert "ReleaseGuard verdict: CONDITIONAL GO (score 0.62)" in out
        assert "[pass ] G1" in out
        assert "excused flaky failure" in out
        assert out.isascii()

    def test_no_go_text_shows_block_and_no_score(self, samples, capsys):
        _, out = run_cli(samples, "scenario_no_go", capsys=capsys)
        assert "ReleaseGuard verdict: NO GO" in out
        assert "score" not in out.splitlines()[0]
        assert "[BLOCK] G1" in out

    def test_json_output_round_trips(self, samples, capsys):
        _, out = run_cli(samples, "scenario_conditional", "--json", capsys=capsys)
        rec = ReleaseRecommendation.model_validate(json.loads(out))
        assert rec.score == pytest.approx(0.62, abs=0.001)

    def test_junit_only_invocation(self, samples, capsys):
        code = main(["--junit", str(samples / "scenario_go" / "junit.xml")])
        out = capsys.readouterr().out
        assert code == 0
        assert "coverage signal missing" in out
        # ASCII on the missing-signal path too — the conditional-scenario
        # check missed the em-dash the first dogfood run garbled
        # (docs/bug-evidence.md #3).
        assert out.isascii()


class TestPolicyOverrides:
    def test_raised_floor_turns_conditional_into_no_go(self, samples, capsys):
        code, out = run_cli(
            samples, "scenario_conditional", "--coverage-floor", "0.75", capsys=capsys
        )
        assert code == 2
        assert "[BLOCK] G2" in out

    def test_lowered_go_threshold_cannot_uncap_excused_failures(self, samples, capsys):
        """The CONDITIONAL cap is structural, not a threshold effect."""
        code, _ = run_cli(
            samples, "scenario_conditional", "--go-threshold", "0.1", capsys=capsys
        )
        assert code == 1
