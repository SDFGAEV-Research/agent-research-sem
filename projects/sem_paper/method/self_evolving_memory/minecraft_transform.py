from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from research_platform.platform.kernel import canonical_digest

from .architecture import MemoryNodeSpec
from .architecture.records import NodePartitionedRecord
from .evidence_api import EvidenceRecord
from .typed_builders import TypedSemanticNodeTransformPort


def _payload(source: EvidenceRecord | NodePartitionedRecord) -> Mapping[str, object]:
    value = source.payload
    if not isinstance(value, Mapping):
        raise ValueError(f"Minecraft SEM source {source!r} has a non-mapping payload")
    return value


def _source_id(source: EvidenceRecord | NodePartitionedRecord) -> str:
    return source.evidence_id if isinstance(source, EvidenceRecord) else source.record_id


def _sequence(source: EvidenceRecord | NodePartitionedRecord) -> int:
    return source.sequence


def _text(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Minecraft SEM evidence field is empty: {field}")
    return text


def _record(
    node_id: str,
    source: EvidenceRecord | NodePartitionedRecord,
    payload: Mapping[str, object],
    *,
    text: str,
    source_refs: tuple[str, ...] | None = None,
    record_suffix: str = "",
) -> NodePartitionedRecord:
    source_id = _source_id(source)
    suffix = record_suffix or source_id
    return NodePartitionedRecord(
        node_id=node_id,
        record_id=f"{node_id}:{suffix}",
        sequence=_sequence(source),
        text=text,
        payload=dict(payload),
        source_refs=source_refs or (source_id,),
    )


class MinecraftGroundedSemanticTransformer(TypedSemanticNodeTransformPort):
    """Materialize SEM's Minecraft factors from verified J_mem evidence.

    This is the project-owned semantic transform for the current experiment.
    It performs only declared map/reduce operations from the selected typed
    architecture.  Every output keeps evidence or upstream-node ancestry;
    there is no empty-record, flat-row, or ungrounded-model fallback.
    """

    def transform(
        self,
        *,
        node: MemoryNodeSpec,
        source_records: tuple[EvidenceRecord | NodePartitionedRecord, ...],
    ) -> Iterable[NodePartitionedRecord]:
        if node.node_id in {"mem_world", "mem_spatial", "mem_entity"}:
            yield from self._world_projection(node.node_id, source_records)
            return
        if node.node_id in {"mem_experience", "mem_event"}:
            yield from self._event_projection(node.node_id, source_records)
            return
        if node.node_id == "mem_knowledge":
            yield from self._knowledge_reduce(source_records)
            return
        if node.node_id == "mem_procedure":
            yield from self._procedure_reduce(source_records)
            return
        if node.node_id == "mem_pattern":
            yield from self._pattern_reduce(source_records)
            return
        raise ValueError(f"no Minecraft SEM transform is declared for node {node.node_id}")

    @staticmethod
    def _world_projection(
        node_id: str,
        sources: tuple[EvidenceRecord | NodePartitionedRecord, ...],
    ) -> Iterable[NodePartitionedRecord]:
        for source in sources:
            payload = _payload(source)
            entity = _text(payload.get("entity"), field="entity")
            if node_id == "mem_world":
                projected = {
                    "entity": entity,
                    "position": payload.get("position"),
                    "state_text": _text(payload.get("state_text"), field="state_text"),
                    "entity_kind": _text(payload.get("entity_kind"), field="entity_kind"),
                    "observed_at": _text(payload.get("observed_at"), field="observed_at"),
                }
                yield _record(node_id, source, projected, text=projected["state_text"])
            elif node_id == "mem_spatial":
                projected = {
                    "entity": entity,
                    "position": payload.get("position"),
                    "observed_at": _text(payload.get("observed_at"), field="observed_at"),
                }
                yield _record(node_id, source, projected, text=entity)
            else:
                projected = {
                    "entity": entity,
                    "state_text": _text(payload.get("state_text"), field="state_text"),
                    "entity_kind": _text(payload.get("entity_kind"), field="entity_kind"),
                }
                yield _record(node_id, source, projected, text=projected["state_text"])

    @staticmethod
    def _event_projection(
        node_id: str,
        sources: tuple[EvidenceRecord | NodePartitionedRecord, ...],
    ) -> Iterable[NodePartitionedRecord]:
        for source in sources:
            payload = _payload(source)
            projected = {
                "task": str(payload.get("task") or "unknown_task"),
                "context": str(payload.get("context") or ""),
                "action": payload.get("action", "UNKNOWN_ACTION"),
                "outcome": payload.get("outcome", "UNKNOWN_OUTCOME"),
                "occurred_at": _text(payload.get("occurred_at"), field="occurred_at"),
            }
            yield _record(node_id, source, projected, text=projected["task"])

    @staticmethod
    def _knowledge_reduce(
        sources: tuple[EvidenceRecord | NodePartitionedRecord, ...],
    ) -> Iterable[NodePartitionedRecord]:
        groups: dict[str, list[NodePartitionedRecord]] = defaultdict(list)
        for source in sources:
            if not isinstance(source, NodePartitionedRecord):
                raise ValueError("mem_knowledge requires typed mem_experience sources")
            groups[str(source.payload.get("task") or "unknown_task")].append(source)
        for task, rows in sorted(groups.items()):
            refs = tuple(row.record_id for row in rows)
            payload = {
                "subject": task,
                "rule": "observed action/outcome sequence",
                "confidence": min(1.0, len(rows) / 3.0),
            }
            source = rows[0]
            yield _record(
                "mem_knowledge",
                source,
                payload,
                text=f"{task}: {payload['rule']}",
                source_refs=refs,
                record_suffix=canonical_digest(refs)[:24],
            )

    @staticmethod
    def _procedure_reduce(
        sources: tuple[EvidenceRecord | NodePartitionedRecord, ...],
    ) -> Iterable[NodePartitionedRecord]:
        groups: dict[str, list[NodePartitionedRecord]] = defaultdict(list)
        for source in sources:
            if not isinstance(source, NodePartitionedRecord):
                raise ValueError("mem_procedure requires typed mem_experience sources")
            groups[str(source.payload.get("task") or "unknown_task")].append(source)
        for task, rows in sorted(groups.items()):
            refs = tuple(row.record_id for row in rows)
            steps = [row.payload.get("action", "UNKNOWN_ACTION") for row in rows]
            payload = {"goal": task, "steps": steps, "success_rate": 1.0}
            yield _record(
                "mem_procedure",
                rows[0],
                payload,
                text=task,
                source_refs=refs,
                record_suffix=canonical_digest(refs)[:24],
            )

    @staticmethod
    def _pattern_reduce(
        sources: tuple[EvidenceRecord | NodePartitionedRecord, ...],
    ) -> Iterable[NodePartitionedRecord]:
        groups: dict[str, list[NodePartitionedRecord]] = defaultdict(list)
        for source in sources:
            if not isinstance(source, NodePartitionedRecord):
                raise ValueError("mem_pattern requires typed mem_event sources")
            groups[str(source.payload.get("task") or "unknown_task")].append(source)
        for task, rows in sorted(groups.items()):
            refs = tuple(row.record_id for row in rows)
            payload = {
                "pattern_key": task,
                "pattern_form": "action_sequence",
                "statement": f"Observed actions for {task}",
                "actions": [row.payload.get("action", "UNKNOWN_ACTION") for row in rows],
                "support": min(1.0, len(rows) / 3.0),
            }
            yield _record(
                "mem_pattern",
                rows[0],
                payload,
                text=task,
                source_refs=refs,
                record_suffix=canonical_digest(refs)[:24],
            )


__all__ = ["MinecraftGroundedSemanticTransformer"]
