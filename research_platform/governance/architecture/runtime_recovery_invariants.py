from __future__ import annotations

import ast
from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, violation


def _class_methods(path: Path, class_name: str) -> tuple[tuple[str, int], ...]:
    if not path.exists():
        return ()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return tuple(
                (child.name, child.lineno)
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    return ()


def audit_runtime_recovery_invariants(root: Path) -> list[SourceInvariantViolation]:
    runtime = root / "research_platform" / "execution" / "runtime" / "manager"
    if not runtime.exists():
        return []
    rows: list[SourceInvariantViolation] = []

    store = root / "research_platform" / "reliability" / "recovery" / "providers" / "lease_store.py"
    for method, line in _class_methods(store, "RecoveryLeaseStore"):
        if method == "execution":
            rows.append(violation(
                root, store, "recovery_execution_authority", line,
                "durable RecoveryLeaseStore owns execution fencing; use RecoveryExecutionFactoryPort",
            ))

    one_click = runtime / "one_click.py"
    for module, line in imports(one_click) if one_click.exists() else ():
        if module in {
            "research_platform.reliability.recovery.providers.lease_store",
            "research_platform.reliability.recovery.execution.runtime.file_lock",
        }:
            rows.append(violation(
                root, one_click, "recovery_execution_authority", line,
                f"OneClickRuntimeManager imports concrete recovery backend {module}; depend on recovery ports",
            ))

    execution = (
        root
        / "research_platform"
        / "reliability"
        / "recovery"
        / "execution"
        / "runtime"
        / "file_lock.py"
    )
    for module, line in imports(execution) if execution.exists() else ():
        if module.endswith("recovery_lease_store"):
            rows.append(violation(
                root, execution, "recovery_execution_authority", line,
                "execution-fence backend imports concrete lease store; depend on RecoveryLeaseStatePort",
            ))
    return rows


__all__ = ["audit_runtime_recovery_invariants"]
