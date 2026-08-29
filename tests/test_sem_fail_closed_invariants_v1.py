from __future__ import annotations

import ast
from pathlib import Path


def _production_python_files(root: Path) -> tuple[Path, ...]:
    composition = tuple(sorted((root / "projects" / "sem_paper" / "composition").rglob("*.py")))
    scripts = (
        root / "scripts" / "sem_paper_minecraft_application.py",
        root / "scripts" / "sem_paper_architecture_audit.py",
    )
    return composition + scripts


def test_sem_production_invariants_do_not_depend_on_python_assert() -> None:
    root = Path(__file__).resolve().parents[1]
    violations: list[str] = []
    for path in _production_python_files(root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                violations.append(f"{path.relative_to(root)}:{node.lineno}")
    assert violations == []
