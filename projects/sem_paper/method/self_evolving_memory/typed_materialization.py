from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
from typing import Protocol

from .architecture import MemoryArchitectureSpec
from .architecture.projection import NodePartitionedDeluxeSnapshot, project_deluxe_architecture
from .architecture.records import NodePartitionedRecord
from .architecture.validation import ArchitectureValidator
from .architecture.values import validate_payload
from .evidence_api import EvidenceReadPort, EvidenceStorePort
from .materialization import MaterializationContract


class TypedMaterializationError(ValueError):
    pass


class TypedNodeBuilderPort(Protocol):
    """Semantic transform seam; no default or lossy fallback is provided."""

    def build_records(
        self,
        architecture: MemoryArchitectureSpec,
        evidence: EvidenceReadPort,
        contracts: tuple[MaterializationContract, ...],
    ) -> Iterable[NodePartitionedRecord]: ...


@dataclass(frozen=True, slots=True)
class TypedMaterializedGeneration:
    generation: str
    base_generation: str
    candidate_id: str
    architecture: MemoryArchitectureSpec
    source_sequence: int
    source_snapshot_digest: str
    records: tuple[NodePartitionedRecord, ...]

    def deluxe_snapshot(self) -> NodePartitionedDeluxeSnapshot:
        return NodePartitionedDeluxeSnapshot(project_deluxe_architecture(self.architecture), self.records)


class TypedMemoryMaterializer:
    """Build an immutable node-partitioned generation from J_mem only.

    The injected builder performs the semantic node transforms. This class
    refuses to infer a typed payload from an arbitrary evidence row and never
    reuses the legacy flat `(node_id, string)` placeholder path.
    """

    def __init__(self, evidence: EvidenceStorePort, builder: TypedNodeBuilderPort) -> None:
        if not callable(getattr(builder, "build_records", None)):
            raise TypedMaterializationError("typed materializer requires an explicit node builder")
        self.evidence = evidence
        self.builder = builder
        self.validator = ArchitectureValidator()

    def build(
        self,
        generation: str,
        *,
        base_generation: str,
        candidate_id: str,
        architecture: MemoryArchitectureSpec,
        contracts: tuple[MaterializationContract, ...],
    ) -> TypedMaterializedGeneration:
        self.validator.verify(architecture)
        if not generation.strip() or not base_generation.strip() or not candidate_id.strip():
            raise TypedMaterializationError("typed materialization identity is required")
        node_ids = {node.node_id for node in architecture.nodes}
        contract_ids = tuple(contract.node_id for contract in contracts)
        if len(contract_ids) != len(set(contract_ids)):
            raise TypedMaterializationError("duplicate typed materialization contract")
        if set(contract_ids) != node_ids:
            raise TypedMaterializationError("typed materialization contracts must cover exactly the target architecture")
        snapshot = self.evidence.snapshot()
        read_view = self.evidence.read_view()
        raw_records = tuple(self.builder.build_records(architecture, read_view, contracts))
        records = self._validate_records(architecture, raw_records)
        return TypedMaterializedGeneration(
            generation,
            base_generation,
            candidate_id,
            architecture,
            snapshot.sequence,
            snapshot.digest,
            records,
        )

    @staticmethod
    def _validate_records(
        architecture: MemoryArchitectureSpec,
        records: tuple[NodePartitionedRecord, ...],
    ) -> tuple[NodePartitionedRecord, ...]:
        known_nodes = architecture.node_map()
        seen: set[str] = set()
        for record in records:
            if record.node_id not in known_nodes:
                raise TypedMaterializationError(f"record {record.record_id} names unknown node {record.node_id}")
            if record.record_id in seen:
                raise TypedMaterializationError(f"duplicate typed materialized record {record.record_id}")
            seen.add(record.record_id)
            try:
                validate_payload(known_nodes[record.node_id], record.payload)
            except ValueError as exc:
                raise TypedMaterializationError(str(exc)) from exc
        return tuple(sorted(records, key=lambda record: (record.node_id, record.sequence, record.record_id)))


__all__ = [
    "TypedMaterializationError",
    "TypedMaterializedGeneration",
    "TypedMemoryMaterializer",
    "TypedNodeBuilderPort",
]
