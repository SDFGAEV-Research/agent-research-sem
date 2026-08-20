from __future__ import annotations

from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, violation


def audit_composition_family_firewall(root: Path) -> list[SourceInvariantViolation]:
    rows: list[SourceInvariantViolation] = []
    composition = root / "research_platform" / "platform" / "composition"
    checks = (
        (composition / "context_action.py", "composition_context_action_firewall", (
            "research_platform.participant.agent.api", "research_platform.participant.capability.api", "research_platform.platform.composition.agent_turn",
            "research_platform.platform.composition.participants.agent", "research_platform.platform.composition.participants.capability",
            "research_platform.platform.composition.registries.agent", "research_platform.platform.composition.registries.capability",
            "research_platform.execution.workflow.implementations.agent_turn",
        )),
        (composition / "agent_turn.py", "composition_agent_turn_firewall", (
            "research_platform.environment.runtime.api", "research_platform.participant.method.api", "research_platform.platform.composition.context_action",
            "research_platform.platform.composition.participants.environment", "research_platform.platform.composition.participants.method",
            "research_platform.platform.composition.registries.environment", "research_platform.platform.composition.registries.method",
            "research_platform.execution.workflow.implementations.context_action",
        )),
    )
    for path, invariant, forbidden in checks:
        if not path.exists():
            continue
        for module, line in imports(path):
            if any(module.startswith(prefix) for prefix in forbidden):
                rows.append(violation(root, path, invariant, line, f"composition family imports unrelated domain authority {module}"))

    bridge_checks = (
        (composition / "participants" / "method.py", "participant_method_bridge_firewall", ("research_platform.environment.runtime.api", "research_platform.participant.agent.api", "research_platform.participant.capability.api")),
        (composition / "participants" / "environment.py", "participant_environment_bridge_firewall", ("research_platform.participant.method.api", "research_platform.participant.agent.api", "research_platform.participant.capability.api")),
        (composition / "participants" / "agent.py", "participant_agent_bridge_firewall", ("research_platform.participant.method.api", "research_platform.environment.runtime.api", "research_platform.participant.capability.api")),
        (composition / "participants" / "capability.py", "participant_capability_bridge_firewall", ("research_platform.participant.method.api", "research_platform.environment.runtime.api", "research_platform.participant.agent.api")),
        (composition / "participants" / "generic.py", "participant_generic_bridge_firewall", ("research_platform.participant.method.api", "research_platform.environment.runtime.api", "research_platform.participant.agent.api", "research_platform.participant.capability.api")),
    )
    for path, invariant, forbidden in bridge_checks:
        if not path.exists():
            continue
        for module, line in imports(path):
            if any(module.startswith(prefix) for prefix in forbidden):
                rows.append(violation(root, path, invariant, line, f"participant bridge imports unrelated specialized ABI {module}"))
    return rows


__all__ = ["audit_composition_family_firewall"]
