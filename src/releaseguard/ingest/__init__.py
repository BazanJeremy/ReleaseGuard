"""Artifact parsers — one per supported CI artifact dialect.

Each parser maps one file format to one normalized signal model (ADR-001)
and knows nothing about gates or scoring. New signal types plug in here.
"""

from releaseguard.ingest.cobertura import parse_cobertura
from releaseguard.ingest.flakysense import parse_flakysense
from releaseguard.ingest.junit import parse_junit

__all__ = ["parse_cobertura", "parse_flakysense", "parse_junit"]
