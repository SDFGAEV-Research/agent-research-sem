from __future__ import annotations

from pathlib import Path


_AUDIT_IMPLEMENTATION_FILES = {
    "research_platform/quality/degradation_contracts.py",
    "research_platform/quality/degradation_paths.py",
    "research_platform/quality/degradation_python_scan.py",
    "research_platform/quality/degradation_config_scan.py",
    "research_platform/quality/no_degradation.py",
}


def is_excluded_path(rel: Path) -> bool:
    return (
        rel.as_posix() in _AUDIT_IMPLEMENTATION_FILES
        or any(
            part in {"tests", "__pycache__", "build", "dist", ".git", ".venv", "venv"}
            or part.endswith(".egg-info")
            for part in rel.parts
        )
    )


__all__ = ["is_excluded_path"]
