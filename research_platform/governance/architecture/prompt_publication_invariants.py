from __future__ import annotations

import ast
from pathlib import Path

from .source_scan import SourceInvariantViolation, violation


def audit_prompt_publication_invariants(root: Path) -> list[SourceInvariantViolation]:
    prompt = root / "research_platform" / "model" / "request" / "prompt" / "runtime"
    rows: list[SourceInvariantViolation] = []
    forbidden_constructors = {
        "PromptGenerationStore",
        "PromptPromotionStore",
        "PromotionRecordStore",
        "ActivePromptPointer",
    }
    for name in ("publication.py", "promotion_store.py"):
        path = prompt / name
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_constructors:
                rows.append(violation(
                    root, path, "prompt_publication_storage_boundary", node.lineno,
                    f"prompt publication authority constructs concrete store {node.func.id}; compose it explicitly",
                ))
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                rows.append(violation(
                    root, path, "prompt_publication_storage_boundary", node.lineno,
                    "prompt publication authority derives storage path; keep layout in composition",
                ))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"with_name", "with_suffix"}:
                rows.append(violation(
                    root, path, "prompt_publication_storage_boundary", node.lineno,
                    "prompt publication authority derives sibling storage path; keep layout in composition",
                ))
    return rows


__all__ = ["audit_prompt_publication_invariants"]
