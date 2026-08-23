from __future__ import annotations

from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, violation


_ORCHESTRATION_PREFIXES = (
    "research_platform.platform.composition",
    "research_platform.participant.session.runtime",
    "research_platform.execution.runtime.manager",
    "research_platform.runtime.session.runtime",
    "research_platform.runtime.service.runtime",
    "research_platform.experimentation",
    "research_platform.execution.workflow.implementations",
)

_CONCRETE_PARTICIPANT_PREFIXES = (
    "research_platform.participant.definition.runtime",
    "research_platform.participant.binding.runtime",
    "research_platform.participant.session.runtime",
)


def _python_files(base: Path) -> tuple[Path, ...]:
    return tuple(sorted(base.rglob("*.py"))) if base.exists() else ()


def audit_participant_dependency_invariants(root: Path) -> list[SourceInvariantViolation]:
    rows: list[SourceInvariantViolation] = []
    api = root / "research_platform" / "participant" / "core" / "api"
    for path in _python_files(api):
        for module, line in imports(path):
            if any(module.startswith(prefix) for prefix in _CONCRETE_PARTICIPANT_PREFIXES):
                rows.append(violation(root, path, "participant_api_implementation_firewall", line, f"participant API imports concrete participant implementation package {module}"))
            elif any(module.startswith(prefix) for prefix in _ORCHESTRATION_PREFIXES):
                rows.append(violation(root, path, "participant_api_orchestration_firewall", line, f"participant API imports orchestration/runtime package {module}"))

    for prefix in _CONCRETE_PARTICIPANT_PREFIXES:
        implementation = root.joinpath(*prefix.split("."))
        for path in _python_files(implementation):
            for module, line in imports(path):
                if any(module.startswith(orchestration) for orchestration in _ORCHESTRATION_PREFIXES):
                    rows.append(violation(root, path, "participant_implementation_orchestration_firewall", line, f"participant implementation assembly imports orchestration/runtime package {module}"))
    return rows


__all__ = ["audit_participant_dependency_invariants"]
