from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceInvariantViolation:
    invariant: str
    path: str
    line: int
    detail: str


def imports(path: Path) -> tuple[tuple[str, int], ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            rows.append((node.module or "", node.lineno))
        elif isinstance(node, ast.Import):
            rows.extend((alias.name, node.lineno) for alias in node.names)
    return tuple(rows)


def method_calls(path: Path, function_name: str) -> tuple[tuple[str, int], ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) or child.name != function_name:
                continue
            return tuple(
                (item.func.attr, item.lineno)
                for item in ast.walk(child)
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
            )
    return ()


def violation(
    root: Path,
    path: Path | str,
    invariant: str,
    line: int,
    detail: str,
) -> SourceInvariantViolation:
    relative = str(path.relative_to(root)) if isinstance(path, Path) and path.is_absolute() else str(path)
    return SourceInvariantViolation(invariant, relative, line, detail)
