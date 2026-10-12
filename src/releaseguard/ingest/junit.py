"""JUnit XML parser — test results with a dialect-aware test identity (ADR-004).

Counts are derived from ``<testcase>`` elements, never from suite attributes:
real-world artifacts drift, the elements are the ground truth. Failures and
errors both count as failed; a failing test's identity is derived so the
evaluator can join it against the flakiness signal.

Two ``classname`` conventions exist in the wild and cannot be told apart
safely, so the dialect is declared, never guessed (ADR-004): ``pytest``
reconstructs a node id from a dotted classname (ADR-002, the default), while
``path`` takes an already-path-shaped classname verbatim.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal, get_args

from releaseguard.models import TestResultsSignal

JUnitDialect = Literal["pytest", "path"]
DIALECTS: tuple[str, ...] = get_args(JUnitDialect)
DEFAULT_DIALECT: JUnitDialect = "pytest"


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


def case_identity(
    classname: str, name: str, *, dialect: JUnitDialect = DEFAULT_DIALECT
) -> str:
    """Derive the join key for one ``<testcase>`` in the declared dialect.

    ``pytest`` reconstructs a node id (ADR-002). ``path`` treats ``classname``
    as the file path it already is and joins verbatim:
    ``invariants/zero-js.spec.ts`` + ``[gate] no js`` ⇒
    ``invariants/zero-js.spec.ts::[gate] no js``. Nothing is normalized —
    separators and case are the artifact's own bytes, because the producer of
    the flakiness report is not ours to rewrite (ADR-004).
    """
    if dialect == "pytest":
        return node_id(classname, name)
    if dialect == "path":
        # An empty classname leaves nothing to prefix; the bare name is the
        # same fallback the pytest dialect takes, and a miss stays strict.
        return f"{classname}::{name}" if classname else name
    raise ValueError(
        f"unknown JUnit dialect {dialect!r}; expected one of {', '.join(DIALECTS)}"
    )


def parse_junit(
    path: str | Path, *, dialect: JUnitDialect = DEFAULT_DIALECT
) -> TestResultsSignal:
    """Parse a JUnit XML report into a :class:`TestResultsSignal`.

    Accepts either a ``<testsuites>`` root or a bare ``<testsuite>``;
    aggregates across all suites. ``dialect`` selects how a failing test's
    identity is derived (ADR-004); it is validated before any element is read,
    so a bad value fails on an empty report too.
    """
    if dialect not in DIALECTS:
        raise ValueError(
            f"unknown JUnit dialect {dialect!r}; expected one of {', '.join(DIALECTS)}"
        )
    root = ET.parse(path).getroot()
    if root.tag not in ("testsuites", "testsuite"):
        raise ValueError(f"{path}: expected <testsuites> or <testsuite> root, got <{root.tag}>")

    passed = failed = skipped = 0
    failed_test_ids: list[str] = []
    for case in root.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            failed += 1
            failed_test_ids.append(
                case_identity(
                    case.get("classname", ""), case.get("name", ""), dialect=dialect
                )
            )
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
