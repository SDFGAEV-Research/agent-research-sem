from __future__ import annotations

from typing import Any

from .contracts import (
    AccessMode,
    EvidenceSourceChannel,
    FieldSpec,
    MemoryArchitectureSpec,
    MemoryMode,
    MemoryNodeSpec,
    MemoryScope,
    OperatorKind,
    PredicateAtom,
    PredicateOp,
    RecordSelector,
    SemanticObjective,
    SourceKind,
    SourceRequirement,
    SourceSpec,
    TransformOpSpec,
    TransformPlan,
    parse_type_spec,
)


def _selector_from_dict(data: Any) -> RecordSelector | None:
    if data is None:
        return None
    atoms = tuple(
        PredicateAtom(raw["field"], PredicateOp(raw["op"]), raw.get("value"))
        for raw in data.get("all_of", ())
    )
    return RecordSelector(atoms, bool(data.get("negated", False)))


def _transform_from_dict(data: dict[str, Any]) -> TransformPlan:
    requirements = tuple(
        SourceRequirement(
            raw["source_node_id"],
            tuple(
                (
                    item if isinstance(item, str) else item["name"],
                    None if isinstance(item, str) or not item.get("type") else parse_type_spec(item["type"]),
                )
                for item in raw.get("fields", ())
            ),
        )
        for raw in data.get("source_requirements", ())
    )
    if "ops" in data:
        operations = tuple(
            TransformOpSpec(
                OperatorKind(raw["op"]),
                tuple(raw.get("inputs", ())),
                {key: value for key, value in raw.items() if key not in {"op", "inputs", "objective"}},
                SemanticObjective(raw["objective"].strip()) if raw.get("objective") else None,
            )
            for raw in data["ops"]
        )
    else:
        operation = TransformOpSpec(
            OperatorKind(data["op"]),
            (),
            {key: value for key, value in data.items() if key not in {"op", "objective", "source_requirements"}},
            SemanticObjective(data["objective"].strip()) if data.get("objective") else None,
        )
        operations = (operation,)
    return TransformPlan(operations, data.get("output_ref", "out"), requirements)


def architecture_from_dict(data: dict[str, Any]) -> MemoryArchitectureSpec:
    nodes = []
    for raw in data["nodes"]:
        fields = tuple(
            FieldSpec(
                field["name"],
                parse_type_spec(field["type"]),
                bool(field.get("required", True)),
                field.get("description", ""),
            )
            for field in raw["schema"]
        )
        sources = tuple(
            SourceSpec(
                SourceKind(source["kind"]),
                source.get("node_id"),
                tuple(source.get("event_types", ())),
                EvidenceSourceChannel(source.get("channel", "MEMORY")),
            )
            for source in raw.get("sources", ())
        )
        nodes.append(
            MemoryNodeSpec(
                node_id=raw["node_id"],
                label=raw.get("label", ""),
                purpose=raw["purpose"].strip(),
                scope=MemoryScope(raw["scope"]),
                mode=MemoryMode(raw["mode"]),
                schema=fields,
                primary_key=tuple(raw.get("primary_key", ())),
                access=frozenset(AccessMode(value) for value in raw.get("access", ())),
                sources=sources,
                transform=_transform_from_dict(raw["transform"]),
                selector=_selector_from_dict(raw.get("selector")),
            )
        )
    return MemoryArchitectureSpec(
        str(data.get("format_version", data.get("seed_contract_version", "0"))),
        data["architecture_id"],
        int(data.get("generation", 0)),
        tuple(nodes),
    )


def architecture_to_dict(architecture: MemoryArchitectureSpec) -> dict[str, Any]:
    def selector_to_dict(selector: RecordSelector | None) -> dict[str, Any] | None:
        if selector is None:
            return None
        return {
            "all_of": [
                {"field": atom.field, "op": atom.op.value, "value": atom.value}
                for atom in selector.all_of
            ],
            "negated": selector.negated,
        }

    def transform_to_dict(plan: TransformPlan) -> dict[str, Any]:
        value: dict[str, Any] = {"ops": []}
        for operation in plan.ops:
            item: dict[str, Any] = {"op": operation.op.value, **dict(operation.params)}
            if operation.inputs:
                item["inputs"] = list(operation.inputs)
            if operation.objective is not None:
                item["objective"] = operation.objective.text
            value["ops"].append(item)
        if plan.output_ref != "out":
            value["output_ref"] = plan.output_ref
        if plan.source_requirements:
            value["source_requirements"] = [
                {
                    "source_node_id": requirement.source_node_id,
                    "fields": [
                        {"name": name, **({"type": spec.canonical()} if spec is not None else {})}
                        for name, spec in requirement.required_fields
                    ],
                }
                for requirement in plan.source_requirements
            ]
        return value

    return {
        "format_version": architecture.format_version,
        "architecture_id": architecture.architecture_id,
        "generation": architecture.generation,
        "nodes": [
            {
                "node_id": node.node_id,
                "label": node.label,
                "purpose": node.purpose,
                "scope": node.scope.value,
                "mode": node.mode.value,
                "schema": [
                    {
                        "name": field.name,
                        "type": field.dtype.canonical(),
                        "required": field.required,
                        **({"description": field.description} if field.description else {}),
                    }
                    for field in node.schema
                ],
                "primary_key": list(node.primary_key),
                "access": sorted(access.value for access in node.access),
                "sources": [
                    {
                        "kind": source.kind.value,
                        **({"node_id": source.node_id} if source.node_id else {}),
                        **({"event_types": list(source.event_types)} if source.event_types else {}),
                        **({"channel": source.evidence_channel.value} if source.evidence_channel is not EvidenceSourceChannel.MEMORY else {}),
                    }
                    for source in node.sources
                ],
                "transform": transform_to_dict(node.transform),
                **({"selector": selector_to_dict(node.selector)} if node.selector is not None else {}),
            }
            for node in architecture.nodes
        ],
    }


__all__ = ["architecture_from_dict", "architecture_to_dict"]
