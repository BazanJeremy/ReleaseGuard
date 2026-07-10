"""Cobertura XML parser — line coverage only (ADR-001 scope)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from releaseguard.models import CoverageSignal


def parse_cobertura(path: str | Path) -> CoverageSignal:
    """Parse a Cobertura XML report into a :class:`CoverageSignal`."""
    root = ET.parse(path).getroot()
    if root.tag != "coverage":
        raise ValueError(f"{path}: expected <coverage> root, got <{root.tag}>")
    line_rate = root.get("line-rate")
    if line_rate is None:
        raise ValueError(f"{path}: <coverage> element has no line-rate attribute")
    return CoverageSignal(line_rate=float(line_rate))
