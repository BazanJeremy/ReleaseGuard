"""Integrity tests for the three canonical release scenarios.

The S2 evaluator tests will assert verdicts against these fixtures; the
invariants pinned here (which failures are flaky-excused, which are real)
are what make those future assertions meaningful. Comparison joins on the
bare test name (JUnit `name` attribute vs the last `::` segment of a
FlakySense node id) so no parser logic is duplicated here.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SAMPLES = Path(__file__).parent.parent / "data" / "samples"
SCENARIOS = ["scenario_go", "scenario_no_go", "scenario_conditional"]
ARTIFACTS = ["junit.xml", "coverage.xml", "flakysense-report.json"]


def load_junit(scenario: str) -> ET.Element:
    return ET.parse(SAMPLES / scenario / "junit.xml").getroot()


def failed_names(suite: ET.Element) -> set[str]:
    return {
        case.get("name")
        for case in suite.iter("testcase")
        if case.find("failure") is not None or case.find("error") is not None
    }


def flaky_names(scenario: str) -> set[str]:
    report = json.loads((SAMPLES / scenario / "flakysense-report.json").read_text())
    return {
        entry["test_id"].rsplit("::", 1)[-1]
        for entry in report
        if entry["detection"]["is_flaky"]
    }


@pytest.mark.parametrize("scenario", SCENARIOS)
class TestArtifactsWellFormed:
    def test_all_artifacts_present(self, scenario):
        for artifact in ARTIFACTS:
            assert (SAMPLES / scenario / artifact).is_file(), f"{scenario}/{artifact} missing"

    def test_junit_counts_match_testcases(self, scenario):
        suite = load_junit(scenario).find("testsuite")
        cases = suite.findall("testcase")
        assert len(cases) == int(suite.get("tests"))
        assert len(failed_names(suite)) == int(suite.get("failures")) + int(suite.get("errors"))

    def test_coverage_line_rate_in_bounds(self, scenario):
        root = ET.parse(SAMPLES / scenario / "coverage.xml").getroot()
        assert 0.0 <= float(root.get("line-rate")) <= 1.0

    def test_flaky_report_entries_have_detection_flag(self, scenario):
        report = json.loads((SAMPLES / scenario / "flakysense-report.json").read_text())
        assert isinstance(report, list)
        for entry in report:
            assert isinstance(entry["detection"]["is_flaky"], bool)


class TestScenarioDesignInvariants:
    """The cross-signal relationships each scenario exists to exercise (ADR-001)."""

    def test_go_has_no_failures(self):
        assert failed_names(load_junit("scenario_go")) == set()

    def test_no_go_failures_are_all_real(self):
        """G1 must trip: no failing test appears in the flaky list."""
        failures = failed_names(load_junit("scenario_no_go"))
        assert failures, "scenario_no_go must contain at least one failure"
        assert failures & flaky_names("scenario_no_go") == set()

    def test_no_go_flaky_list_is_nonempty(self):
        """The flaky signal must be present-but-irrelevant, so the scenario
        proves G1 checks membership rather than mere existence of a report."""
        assert flaky_names("scenario_no_go") != set()

    def test_conditional_failures_are_all_excused(self):
        """G1 must not trip: every failing test appears in the flaky list."""
        failures = failed_names(load_junit("scenario_conditional"))
        assert failures, "scenario_conditional must contain at least one failure"
        assert failures <= flaky_names("scenario_conditional")

    def test_conditional_coverage_between_floor_and_target(self):
        """Coverage must pass G2 but drag the score below the GO threshold."""
        from releaseguard import policy

        root = ET.parse(SAMPLES / "scenario_conditional" / "coverage.xml").getroot()
        assert policy.COVERAGE_FLOOR < float(root.get("line-rate")) < policy.COVERAGE_TARGET


class TestDialectFixtureIntegrity:
    """`dialect_playwright` carries real Playwright bytes (ADR-004, bug
    evidence #4). These properties are what make it evidence rather than
    decoration: lose any of them and the fixture stops reproducing the defect
    while the tests around it stay green.

    It deliberately ships no `coverage.xml` — it exists to exercise the
    identity join, and the coverage signal is optional (ADR-001).
    """

    DIALECT = "dialect_playwright"

    def cases(self) -> list[ET.Element]:
        root = ET.parse(SAMPLES / self.DIALECT / "junit.xml").getroot()
        return list(root.iter("testcase"))

    def test_artifacts_present(self):
        for artifact in ["junit.xml", "flakysense-report.json"]:
            assert (SAMPLES / self.DIALECT / artifact).is_file()

    def test_no_file_attribute(self):
        """FlakySense prefers a `file` attribute over `classname`; Playwright
        emits none, which is why the classname carries the path at all."""
        assert [c for c in self.cases() if c.get("file")] == []

    def test_classnames_are_paths_not_dotted_modules(self):
        for case in self.cases():
            classname = case.get("classname")
            assert classname
            assert "/" in classname or "\\" in classname, classname
            # No CapWords segment: the pytest heuristic finds no class chain
            # and consumes the whole thing as a module path.
            assert not any(p[:1].isupper() for p in classname.split(".")), classname

    def test_single_failure_is_listed_flaky_under_the_path_identity(self):
        """The scenario's reason to exist: the only failure IS known-flaky, so
        a working join must excuse it and a broken one must block."""
        failing = [
            c
            for c in self.cases()
            if c.find("failure") is not None or c.find("error") is not None
        ]
        assert len(failing) == 1
        identity = f"{failing[0].get('classname')}::{failing[0].get('name')}"
        report = json.loads(
            (SAMPLES / self.DIALECT / "flakysense-report.json").read_text(
                encoding="utf-8"
            )
        )
        flaky = {e["test_id"] for e in report if e["detection"]["is_flaky"]}
        assert identity in flaky
