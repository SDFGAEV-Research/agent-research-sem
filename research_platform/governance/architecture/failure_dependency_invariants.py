from __future__ import annotations

from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, violation


def audit_failure_dependency_invariants(root: Path) -> list[SourceInvariantViolation]:
    rows: list[SourceInvariantViolation] = []
    protected = (
        root / "projects", root / "research_platform" / "experimentation" / "experiment", root / "research_platform" / "execution" / "workflow" / "implementations",
        root / "research_platform" / "execution" / "runtime" / "manager", root / "research_platform" / "model" / "serving",
        root / "research_platform" / "runtime" / "service" / "runtime", root / "research_platform" / "participant" / "agent" / "api",
        root / "research_platform" / "participant" / "capability" / "api", root / "research_platform" / "environment" / "runtime" / "api",
        root / "research_platform" / "participant" / "method" / "api", root / "research_platform" / "participant" / "core" / "api",
        root / "research_platform" / "reliability" / "effect" / "api", root / "research_platform" / "reliability" / "failure" / "api",
    )
    for base in protected:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            for module, line in imports(path):
                if module.startswith("research_platform.reliability.forensics"):
                    rows.append(violation(root, path, "failure_forensics_dependency_direction", line, f"domain/runtime code imports forensic implementation {module}; use research_platform.reliability.failure.api or an injected port"))

    forensics = root / "research_platform" / "reliability" / "forensics"
    if forensics.exists():
        for path in sorted(forensics.glob("*.py")):
            if path.name != "__init__.py":
                rows.append(violation(
                    root, path, "forensics_layer_layout", 1,
                    f"forensic implementation module {path.name} is flat at subsystem root; use api/runtime/providers/composition",
                ))
    for legacy_name in ("failure.py", "failure_builder.py", "redaction.py", "service_crash.py"):
        for path in sorted(forensics.rglob(legacy_name)) if forensics.exists() else ():
            rows.append(violation(root, path, "failure_contract_authority", 1, f"forensic backend reintroduced failure semantic/domain adapter in {legacy_name}"))
    forbidden_domain_prefixes = (
        "research_platform.runtime.service.runtime", "research_platform.participant.method.api", "research_platform.environment.runtime.api",
        "research_platform.participant.agent.api", "research_platform.participant.capability.api", "research_platform.execution.workflow.implementations",
        "research_platform.experimentation.study", "research_platform.model.serving", "research_platform.execution.runtime.manager", "projects",
    )
    for path in sorted(forensics.rglob("*.py")):
        for module, line in imports(path):
            if module.startswith(forbidden_domain_prefixes):
                rows.append(violation(root, path, "failure_contract_authority", line, f"forensic backend imports domain implementation {module}; domain-to-failure mapping belongs in an integration adapter"))
    return rows


__all__ = ["audit_failure_dependency_invariants"]
