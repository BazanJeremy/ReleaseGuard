"""FlakySense JSON parser — known-flaky node ids from a FlakySense report.

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
        test_id
        for index, entry in enumerate(report)
        for test_id, is_flaky in [_entry_fields(entry, index, path)]
        if is_flaky
    ]
    return FlakinessSignal(flaky_test_ids=flaky_test_ids, source="flakysense")


def _entry_fields(entry: object, index: int, path: str | Path) -> tuple[str, bool]:
    """Return ``(test_id, is_flaky)`` or raise ``ValueError`` naming the entry.

    A malformed entry must surface as a ``ValueError``: the CLI maps that to
    exit 3, whereas a stray ``KeyError`` would exit 1 — CONDITIONAL GO.
    """
    detection = entry.get("detection") if isinstance(entry, dict) else None
    test_id = entry.get("test_id") if isinstance(entry, dict) else None
    is_flaky = detection.get("is_flaky") if isinstance(detection, dict) else None
    if not isinstance(test_id, str) or not isinstance(is_flaky, bool):
        raise ValueError(
            f"{path}: entry {index} is not a FlakySense report "
            "(expected a string 'test_id' and a boolean 'detection.is_flaky')"
        )
    return test_id, is_flaky
