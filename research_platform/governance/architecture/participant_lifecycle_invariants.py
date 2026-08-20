from __future__ import annotations

import ast
from pathlib import Path

from .source_scan import SourceInvariantViolation, violation


def _python_files(base: Path) -> tuple[Path, ...]:
    return tuple(sorted(base.rglob("*.py"))) if base.exists() else ()


def audit_participant_lifecycle_invariants(root: Path) -> list[SourceInvariantViolation]:
    rows: list[SourceInvariantViolation] = []
    implementation = root / "research_platform" / "participant" / "core" / "implementation"
    for path in (implementation / "catalog.py", implementation / "configuration.py", implementation / "local_resolution.py"):
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "open_session":
                rows.append(violation(root, path, "participant_session_lifecycle_authority", node.lineno, "implementation/configuration/resolver authority must not own open_session lifecycle"))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "open_session":
                rows.append(violation(root, path, "participant_session_lifecycle_authority", node.lineno, "implementation/configuration/resolver authority must not invoke open_session lifecycle"))

    owner = root / "research_platform" / "execution" / "participants" / "session_lifecycle.py"
    if owner.exists():
        owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=str(owner))
        owners = {
            "resolve": root / "research_platform" / "execution" / "participants" / "resolution.py",
            "open_session": owner,
            "close": owner,
            "checkpoint": root / "research_platform" / "execution" / "participants" / "checkpoint_operations.py",
            "restore": root / "research_platform" / "execution" / "participants" / "checkpoint_operations.py",
        }
        for verb, verb_owner in owners.items():
            if not verb_owner.exists():
                rows.append(violation(root, verb_owner, "participant_runtime_lifecycle_backbone", 1, f"generic participant runtime operation owner missing for verb={verb}"))
                continue
            verb_tree = owner_tree if verb_owner == owner else ast.parse(verb_owner.read_text(encoding="utf-8"), filename=str(verb_owner))
            found = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "participant_operation_type"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == verb
                for node in ast.walk(verb_tree)
            )
            if not found:
                rows.append(violation(root, verb_owner, "participant_runtime_lifecycle_backbone", 1, f"generic participant runtime lifecycle missing operation verb={verb}"))

    forbidden_names = {"ResearchMethodEndpoint", "AgentRuntimeEndpoint", "EnvironmentRuntimeEndpoint", "CapabilityProviderRuntimeEndpoint"}
    domain_roots = (
        root / "research_platform" / "participant" / "method" / "api",
        root / "research_platform" / "participant" / "agent" / "api",
        root / "research_platform" / "environment" / "runtime" / "api",
        root / "research_platform" / "participant" / "capability" / "api",
    )
    for base in domain_roots:
        for path in _python_files(base):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name in forbidden_names:
                    rows.append(violation(root, path, "participant_runtime_endpoint_single_authority", node.lineno, f"domain API reintroduced runtime endpoint lifecycle protocol {node.name}; use participant_api.ParticipantRuntimeEndpoint"))
    return rows


__all__ = ["audit_participant_lifecycle_invariants"]
