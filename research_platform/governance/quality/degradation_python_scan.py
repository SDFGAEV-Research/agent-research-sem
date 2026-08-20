from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from .degradation_contracts import BANNED_RUNTIME_IDENTIFIERS, DegradationFinding
from .degradation_paths import is_excluded_path


def scan_python_degradation(root: Path) -> Iterable[DegradationFinding]:
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if is_excluded_path(rel):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (UnicodeDecodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Name, ast.arg)):
                name = node.id if isinstance(node, ast.Name) else node.arg
                if name in BANNED_RUNTIME_IDENTIFIERS:
                    yield DegradationFinding(rel.as_posix(), node.lineno, name, "python_identifier")
            elif isinstance(node, ast.Attribute) and node.attr in BANNED_RUNTIME_IDENTIFIERS:
                yield DegradationFinding(rel.as_posix(), node.lineno, node.attr, "python_attribute")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in BANNED_RUNTIME_IDENTIFIERS:
                yield DegradationFinding(rel.as_posix(), node.lineno, node.value, "python_literal_key")


__all__ = ["scan_python_degradation"]
