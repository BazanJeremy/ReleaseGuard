"""Parser tests — one dialect each, plus the ADR-002 node-id reconstruction
and the ADR-004 declared JUnit dialect."""

import pytest

from releaseguard.ingest import parse_cobertura, parse_flakysense, parse_junit
from releaseguard.ingest.junit import case_identity, node_id


class TestNodeIdReconstruction:
    """ADR-002: dotted classname segments are module path until the first
    CapWords segment, which starts the class chain."""

    @pytest.mark.parametrize(
        ("classname", "name", "expected"),
        [
            (
                "tests.test_payment",
                "test_refund_idempotency",
                "tests/test_payment.py::test_refund_idempotency",
            ),
            (
                "tests.test_api.TestLogin",
                "test_ok",
                "tests/test_api.py::TestLogin::test_ok",
            ),
            (
                "tests.integration.test_api.TestLogin.TestNested",
                "test_ok",
                "tests/integration/test_api.py::TestLogin::TestNested::test_ok",
            ),
            ("", "test_orphan", "test_orphan"),
            ("TestBare", "test_ok", "TestBare::test_ok"),
        ],
    )
    def test_reconstruction(self, classname, name, expected):
        assert node_id(classname, name) == expected


class TestParseJunit:
    def test_go_scenario_counts(self, samples):
        signal = parse_junit(samples / "scenario_go" / "junit.xml")
        assert (signal.total, signal.passed, signal.failed, signal.skipped) == (8, 8, 0, 0)

    def test_no_go_scenario_failed_ids_are_node_ids(self, samples):
        signal = parse_junit(samples / "scenario_no_go" / "junit.xml")
        assert signal.failed == 2
        assert signal.failed_test_ids == [
            "tests/test_payment.py::test_refund_idempotency",
            "tests/test_payment.py::test_currency_rounding",
        ]

    def test_bare_testsuite_root_accepted(self, tmp_path):
        report = tmp_path / "junit.xml"
        report.write_text(
            '<testsuite tests="1"><testcase classname="tests.test_x" name="test_a"/></testsuite>'
        )
        assert parse_junit(report).passed == 1

    def test_error_element_counts_as_failed(self, tmp_path):
        report = tmp_path / "junit.xml"
        report.write_text(
            '<testsuite><testcase classname="tests.test_x" name="test_a">'
            "<error message='boom'/></testcase></testsuite>"
        )
        signal = parse_junit(report)
        assert signal.failed == 1
        assert signal.failed_test_ids == ["tests/test_x.py::test_a"]

    def test_skipped_counted_separately(self, tmp_path):
        report = tmp_path / "junit.xml"
        report.write_text(
            '<testsuite><testcase classname="tests.test_x" name="test_a">'
            "<skipped/></testcase></testsuite>"
        )
        signal = parse_junit(report)
        assert (signal.total, signal.skipped, signal.passed) == (1, 1, 0)

    def test_counts_derive_from_testcases_not_attributes(self, tmp_path):
        """Suite attributes lie (drifted artifact); elements are ground truth."""
        report = tmp_path / "junit.xml"
        report.write_text(
            '<testsuite tests="99" failures="99">'
            '<testcase classname="tests.test_x" name="test_a"/></testsuite>'
        )
        signal = parse_junit(report)
        assert (signal.total, signal.failed) == (1, 0)

    def test_wrong_root_rejected(self, tmp_path):
        report = tmp_path / "junit.xml"
        report.write_text("<html/>")
        with pytest.raises(ValueError, match="expected <testsuites>"):
            parse_junit(report)


class TestJUnitDialect:
    """ADR-004: the dialect is declared, never guessed. The `path` dialect
    takes a path-shaped classname verbatim; `pytest` stays the default."""

    def test_default_dialect_is_pytest_reconstruction(self):
        assert case_identity("tests.test_api", "test_ok") == node_id(
            "tests.test_api", "test_ok"
        )

    @pytest.mark.parametrize(
        ("classname", "name", "expected"),
        [
            (
                "invariants/zero-js.spec.ts",
                "[gate] no js",
                "invariants/zero-js.spec.ts::[gate] no js",
            ),
            # Windows-emitted separators are the artifact's own bytes: nothing
            # is normalized, because the flakiness report is not ours to rewrite.
            (
                "invariants\\zero-js.spec.ts",
                "[gate] no js",
                "invariants\\zero-js.spec.ts::[gate] no js",
            ),
            # Dots are not separators in this dialect; `.spec.ts` survives.
            ("a11y/axe.spec.ts", "home", "a11y/axe.spec.ts::home"),
            # No classname leaves nothing to prefix - same fallback as pytest.
            ("", "orphan", "orphan"),
        ],
    )
    def test_path_dialect_joins_verbatim(self, classname, name, expected):
        assert case_identity(classname, name, dialect="path") == expected

    def test_pytest_dialect_mangles_a_path_classname(self):
        """Why the dialect exists (bug evidence #4): a path-shaped classname
        run through the pytest heuristic yields an id that can never match."""
        assert (
            case_identity("invariants/zero-js.spec.ts", "[gate] no js")
            == "invariants/zero-js/spec/ts.py::[gate] no js"
        )

    def test_unknown_dialect_rejected_by_identity(self):
        with pytest.raises(ValueError, match="unknown JUnit dialect"):
            case_identity("a.b", "test_x", dialect="maven")

    def test_unknown_dialect_rejected_before_reading_the_report(self, tmp_path):
        """Validated up front: an empty report must not mask a bad dialect."""
        report = tmp_path / "junit.xml"
        report.write_text("<testsuite></testsuite>")
        with pytest.raises(ValueError, match="unknown JUnit dialect"):
            parse_junit(report, dialect="maven")

    def test_parse_junit_path_dialect_on_the_real_fixture(self, samples):
        signal = parse_junit(
            samples / "dialect_playwright" / "junit.xml", dialect="path"
        )
        assert (signal.total, signal.failed) == (6, 1)
        assert signal.failed_test_ids == [
            "invariants\\zero-js.spec.ts::[invariants-gate] Invariant 0-JS "
            "› aucun fichier JavaScript dans dist/"
        ]

    def test_parse_junit_default_dialect_breaks_the_real_fixture(self, samples):
        """The same bytes under the default dialect: the join key is mangled."""
        signal = parse_junit(samples / "dialect_playwright" / "junit.xml")
        assert signal.failed_test_ids[0].startswith("invariants\\zero-js/spec/ts.py::")


class TestParseCobertura:
    @pytest.mark.parametrize(
        ("scenario", "expected"),
        [("scenario_go", 0.88), ("scenario_no_go", 0.75), ("scenario_conditional", 0.72)],
    )
    def test_fixture_line_rates(self, samples, scenario, expected):
        assert parse_cobertura(samples / scenario / "coverage.xml").line_rate == expected

    def test_missing_line_rate_rejected(self, tmp_path):
        report = tmp_path / "coverage.xml"
        report.write_text("<coverage/>")
        with pytest.raises(ValueError, match="line-rate"):
            parse_cobertura(report)

    def test_wrong_root_rejected(self, tmp_path):
        report = tmp_path / "coverage.xml"
        report.write_text('<report line-rate="0.5"/>')
        with pytest.raises(ValueError, match="expected <coverage>"):
            parse_cobertura(report)


class TestParseFlakysense:
    def test_conditional_scenario_flaky_ids(self, samples):
        signal = parse_flakysense(samples / "scenario_conditional" / "flakysense-report.json")
        assert signal.flaky_test_ids == [
            "tests/test_search.py::test_search_pagination",
            "tests/test_cache.py::test_cache_eviction",
        ]
        assert signal.source == "flakysense"

    def test_empty_report(self, samples):
        signal = parse_flakysense(samples / "scenario_go" / "flakysense-report.json")
        assert signal.flaky_test_ids == []

    def test_non_flaky_entries_filtered(self, tmp_path):
        report = tmp_path / "report.json"
        report.write_text(
            '[{"test_id": "tests/test_x.py::test_a", "detection": {"is_flaky": false}}]'
        )
        assert parse_flakysense(report).flaky_test_ids == []

    def test_non_array_rejected(self, tmp_path):
        report = tmp_path / "report.json"
        report.write_text('{"test_id": "x"}')
        with pytest.raises(ValueError, match="JSON array"):
            parse_flakysense(report)
