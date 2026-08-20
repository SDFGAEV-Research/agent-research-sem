from __future__ import annotations

from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, violation


def audit_runtime_model_api_boundary(root: Path) -> list[SourceInvariantViolation]:
    runtime_manager = root / "research_platform" / "execution" / "runtime" / "manager"
    if not runtime_manager.exists():
        return []
    rows: list[SourceInvariantViolation] = []
    for path in sorted(runtime_manager.rglob("*.py")):
        for module, line in imports(path):
            if (module == "research_platform.model.serving" or module.startswith("research_platform.model.serving.")) and not (module == "research_platform.model.serving.api" or module.startswith("research_platform.model.serving.api.")):
                rows.append(violation(root, path, "runtime_model_api_boundary", line, f"runtime manager imports Model Serving implementation {module}; consume research_platform.model.serving.api contracts"))
    return rows


__all__ = ["audit_runtime_model_api_boundary"]
