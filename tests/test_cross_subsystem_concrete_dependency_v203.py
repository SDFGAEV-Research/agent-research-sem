from __future__ import annotations

from pathlib import Path
import tempfile

from research_platform.governance.architecture.concrete_dependency_invariants import (
    audit_cross_subsystem_concrete_dependencies,
)


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_cross_subsystem_runtime_import_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(
            root,
            "research_platform/execution/workflow/example.py",
            "from research_platform.reliability.diagnostics.runtime import FailureDiagnosisService\n",
        )
        rows = audit_cross_subsystem_concrete_dependencies(root)
        assert len(rows) == 1
        assert rows[0].invariant == "cross_subsystem_concrete_dependency"


def test_cross_subsystem_api_import_is_allowed() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(
            root,
            "research_platform/execution/workflow/example.py",
            "from research_platform.reliability.diagnostics.api import DiagnosticEvidencePort\n",
        )
        assert audit_cross_subsystem_concrete_dependencies(root) == []


def test_composition_root_may_bind_concrete_runtime() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(
            root,
            "research_platform/platform/composition/example.py",
            "from research_platform.reliability.diagnostics.runtime import FailureDiagnosisService\n",
        )
        assert audit_cross_subsystem_concrete_dependencies(root) == []
