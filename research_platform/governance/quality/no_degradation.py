from __future__ import annotations

from pathlib import Path

from .degradation_config_scan import scan_config_degradation
from .degradation_contracts import (
    BANNED_RUNTIME_IDENTIFIERS,
    DegradationFinding,
    FORBIDDEN_ENABLED_CONFIG_KEYS,
    FORBIDDEN_NONEMPTY_CONFIG_KEYS,
)
from .degradation_python_scan import scan_python_degradation


def scan_no_degradation(root: Path) -> tuple[DegradationFinding, ...]:
    return tuple([*scan_python_degradation(root), *scan_config_degradation(root)])


__all__ = [
    "BANNED_RUNTIME_IDENTIFIERS",
    "DegradationFinding",
    "FORBIDDEN_ENABLED_CONFIG_KEYS",
    "FORBIDDEN_NONEMPTY_CONFIG_KEYS",
    "scan_no_degradation",
]
