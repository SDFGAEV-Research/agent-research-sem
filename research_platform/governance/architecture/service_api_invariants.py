from __future__ import annotations

from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, violation


def audit_service_api_invariants(root: Path) -> list[SourceInvariantViolation]:
    rows: list[SourceInvariantViolation] = []
    api = root / "research_platform" / "runtime" / "service" / "api"
    forbidden_api = (
        "research_platform.runtime.service.runtime",
        "research_platform.execution.runtime.manager",
        "research_platform.experimentation.study",
        "research_platform.platform.composition",
        "research_platform.reliability.forensics",
        "research_platform.operator",
    )
    if api.exists():
        for path in sorted(api.rglob("*.py")):
            for module, line in imports(path):
                if module.startswith(forbidden_api):
                    rows.append(violation(
                        root,
                        path,
                        "service_api_dependency_firewall",
                        line,
                        f"service API imports implementation/orchestration layer {module}",
                    ))

    consumers = (
        ("runtime-manager", root / "research_platform" / "execution" / "runtime" / "manager"),
        ("experiment", root / "research_platform" / "experimentation" / "experiment"),
        ("workflows", root / "research_platform" / "execution" / "workflow" / "implementations"),
        ("operator", root / "research_platform" / "operator"),
    )
    for package_name, package in consumers:
        if not package.exists():
            continue
        for path in sorted(package.rglob("*.py")):
            for module, line in imports(path):
                if module == "research_platform.runtime.service.runtime" or module.startswith("research_platform.runtime.service.runtime."):
                    rows.append(violation(root, path, "service_external_api_boundary", line, f"{package_name} imports service implementation {module}; depend on research_platform.runtime.service.api"))

    legacy = root / "research_platform" / "runtime" / "service" / "runtime" / "runtime_ports.py"
    if legacy.exists():
        rows.append(violation(
            root,
            legacy,
            "service_external_api_boundary",
            1,
            "Service runtime cross-system ABI must live in runtime.service.api, not runtime.runtime_ports",
        ))
    return rows


__all__ = ["audit_service_api_invariants"]
