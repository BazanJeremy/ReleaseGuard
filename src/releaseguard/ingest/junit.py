"""JUnit XML parser — test results with reconstructed pytest node ids (ADR-002).

Counts are derived from ``<testcase>`` elements, never from suite attributes:
real-world artifacts drift, the elements are the ground truth. Failures and
errors both count as failed; a failing test's identity is reconstructed as a
pytest node id so the evaluator can join it against the flakiness signal.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from releaseguard.models import TestResultsSignal


def node_id(classname: str, name: str) -> str:
    """Reconstruct a pytest node id from JUnit classname/name (ADR-002).

    Dotted classname segments are module path components until the first
    CapWords segment, which starts the class chain:
    ``tests.test_api.TestLogin`` + ``test_ok`` ⇒
    ``tests/test_api.py::TestLogin::test_ok``.
    """
    if not classname:
        return name
    parts = classname.split(".")
    module_parts: list[str] = []
    class_parts: list[str] = []
    for index, part in enumerate(parts):
        if part[:1].isupper():
            class_parts = parts[index:]
            break
        module_parts.append(part)
    if not module_parts:
        # Classname carries no module path; fall back to the raw chain.
        return "::".join([*class_parts, name])
    return "::".join(["/".join(module_parts) + ".py", *class_parts, name])


def parse_junit(path: str | Path) -> TestResultsSignal:
    """Parse a JUnit XML report into a :class:`TestResultsSignal`.

    Accepts either a ``<testsuites>`` root or a bare ``<testsuite>``;
    aggregates across all suites.
    """
    root = ET.parse(path).getroot()
    if root.tag not in ("testsuites", "testsuite"):
        raise ValueError(f"{path}: expected <testsuites> or <testsuite> root, got <{root.tag}>")

    passed = failed = skipped = 0
    failed_test_ids: list[str] = []
    for case in root.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            failed += 1
            failed_test_ids.append(node_id(case.get("classname", ""), case.get("name", "")))
        elif case.find("skipped") is not None:
            skipped += 1
        else:
            passed += 1

    return TestResultsSignal(
        total=passed + failed + skipped,
        passed=passed,
        failed=failed,
        skipped=skipped,
        failed_test_ids=failed_test_ids,
    )
