from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SilentFailureFinding:
    path: str
    line: int
    kind: str
    detail: str


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name) and handler.type.id in {"Exception", "BaseException"}:
        return True
    return False


def _handler_is_silent(handler: ast.ExceptHandler) -> bool:
    body = handler.body
    if not body:
        return True
    # pass / continue / bare return are the high-confidence patterns that erase the defect.
    return all(
        isinstance(stmt, (ast.Pass, ast.Continue)) or
        (isinstance(stmt, ast.Return) and stmt.value is None)
        for stmt in body
    )


def _is_suppress_broad(node: ast.Call) -> bool:
    fn = node.func
    if not (isinstance(fn, ast.Attribute) and fn.attr == "suppress"):
        return False
    for arg in node.args:
        if isinstance(arg, ast.Name) and arg.id in {"Exception", "BaseException"}:
            return True
    return False


def scan_silent_failures(root: Path) -> tuple[SilentFailureFinding, ...]:
    findings: list[SilentFailureFinding] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (UnicodeDecodeError, SyntaxError) as exc:
            findings.append(SilentFailureFinding(str(path), getattr(exc, "lineno", 0) or 0, "parse_error", str(exc)))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_broad(node) and _handler_is_silent(node):
                findings.append(SilentFailureFinding(str(path), node.lineno, "silent_broad_except", "broad exception is discarded without evidence"))
            elif isinstance(node, ast.Call) and _is_suppress_broad(node):
                findings.append(SilentFailureFinding(str(path), node.lineno, "broad_suppress", "contextlib.suppress discards Exception/BaseException"))
    return tuple(findings)
