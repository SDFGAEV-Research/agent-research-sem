from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable

from .degradation_contracts import BANNED_RUNTIME_IDENTIFIERS, DegradationFinding
from .degradation_paths import iter_audited_files

_BANNED_IDENTIFIER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(item) for item in sorted(BANNED_RUNTIME_IDENTIFIERS)) + r")\b"
)


def scan_python_degradation(root: Path) -> Iterable[DegradationFinding]:
    # Exact lexical prefilter: every forbidden AST identifier/attribute/string
    # must occur verbatim in source text.  Most files therefore avoid AST parse.
    for path in iter_audited_files(root, suffixes=frozenset({".py"})):
        rel = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if _BANNED_IDENTIFIER_RE.search(text) is None:
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
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
