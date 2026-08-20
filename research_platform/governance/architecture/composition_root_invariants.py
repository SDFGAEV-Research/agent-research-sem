from __future__ import annotations

import ast
from pathlib import Path

from .source_scan import SourceInvariantViolation, violation


def audit_composition_root_imports(root: Path) -> list[SourceInvariantViolation]:
    rows: list[SourceInvariantViolation] = []
    package = root / "research_platform"
    if not package.exists():
        return rows
    for path in sorted(package.rglob("*.py")):
        if path == package / "composition" / "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "research_platform.platform.composition":
                        rows.append(violation(root, path, "composition_root_import_firewall", node.lineno, "production code imports composition root instead of an exact composition submodule"))
            elif isinstance(node, ast.ImportFrom) and node.module == "research_platform":
                if any(alias.name == "composition" for alias in node.names):
                    rows.append(violation(root, path, "composition_root_import_firewall", node.lineno, "production code imports composition root instead of an exact composition submodule"))
    return rows


__all__ = ["audit_composition_root_imports"]
