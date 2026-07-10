"""FlakySense JSON parser — known-flaky node ids from a P4 report.

Reads the ``flakysense --json`` output: an array of per-test reports, each
carrying a ``detection.is_flaky`` verdict. Only flagged tests matter here;
scores, causes, and narratives stay upstream — ReleaseGuard consumes the
membership list, not the analysis.
"""

from __future__ import annotations

import json
from pathlib import Path

from releaseguard.models import FlakinessSignal


def parse_flakysense(path: str | Path) -> FlakinessSignal:
    """Parse a FlakySense JSON report into a :class:`FlakinessSignal`."""
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(report, list):
        raise ValueError(f"{path}: expected a JSON array of FlakySense reports")
    flaky_test_ids = [
        entry["test_id"] for entry in report if entry["detection"]["is_flaky"]
    ]
    return FlakinessSignal(flaky_test_ids=flaky_test_ids, source="flakysense")
