from __future__ import annotations

import ast
from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, violation

_PURE_MODEL_MODULES = (
    "api/host_verification.py",
    "api/runtime_qualification.py",
    "api/recovery_state.py",
    "runtime/durable_recovery.py",
    "runtime/supervisor.py",
)
_FORBIDDEN_STORAGE_IMPORT_SUFFIXES = (
    "host_verification_storage", "runtime_qualification_storage", "recovery_storage", "supervisor_storage",
)


def audit_model_storage_boundaries(root: Path) -> list[SourceInvariantViolation]:
    model_os = root / "research_platform" / "model" / "serving"
    rows: list[SourceInvariantViolation] = []
    for name in _PURE_MODEL_MODULES:
        path = model_os / name
        if not path.exists():
            continue
        for module, line in imports(path):
            if module in {"pathlib", "research_platform.platform.kernel.durability.durable_file"} or module.endswith(_FORBIDDEN_STORAGE_IMPORT_SUFFIXES):
                rows.append(violation(root, path, "model_storage_boundary", line, f"model semantic/runtime authority imports storage implementation {module}; inject a port"))

    runner = model_os / "runtime" / "durable_recovery.py"
    if runner.exists():
        tree = ast.parse(runner.read_text(encoding="utf-8"), filename=str(runner))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "path" and isinstance(node.value, ast.Attribute) and node.value.attr == "store":
                rows.append(violation(root, runner, "model_recovery_store_boundary", node.lineno, "durable recovery runner reaches concrete store.path; depend only on DurableRecoveryStorePort"))

    package_root = model_os / "__init__.py"
    for module, line in imports(package_root) if package_root.exists() else ():
        if module.endswith(_FORBIDDEN_STORAGE_IMPORT_SUFFIXES):
            rows.append(violation(root, package_root, "model_public_api_storage_boundary", line, f"model_os package root re-exports concrete storage backend {module}; import implementations explicitly"))

    runtime_model_ports = root / "research_platform" / "execution" / "runtime" / "manager" / "model_ports.py"
    forbidden = {
        "research_platform.model.serving.api.runtime_qualification", "research_platform.model.serving.runtime.runtime_qualification_service", "research_platform.model.serving.providers.runtime_qualification_storage",
    }
    for module, line in imports(runtime_model_ports) if runtime_model_ports.exists() else ():
        if module in forbidden:
            rows.append(violation(root, runtime_model_ports, "model_qualification_backend_boundary", line, f"runtime manager imports Model OS qualification implementation {module}; depend on runtime_qualification_ports"))
    return rows


__all__ = ["audit_model_storage_boundaries"]
