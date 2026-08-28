from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
from typing import Protocol
from collections.abc import Mapping

from .architecture import MemoryArchitectureSpec, MemoryMode, SourceKind, TransformPlan
from .architecture.projection import NodePartitionedDeluxeSnapshot, project_deluxe_architecture
from .architecture.records import NodePartitionedRecord
from .architecture.validation import ArchitectureValidator
from .architecture.values import validate_payload
from .architecture.serialization import architecture_from_dict, architecture_to_dict
from .deluxe.api.ports import DeluxeServingSource
from .evidence_api import EvidenceMaterializationSource, EvidenceReadPort
from .materialization import MaterializationContract, PreparedGeneration
from .session_state_api import SEMSessionStatePort
from research_platform.platform.kernel import canonical_digest
from research_platform.platform.kernel.errors import describe_exception
from .typed_builders import (
    SemPaperTypedMaterializationConfiguration,
    TypedSemanticNodeTransformPort,
    build_sem_paper_typed_materialization_configuration,
)


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


TYPED_GENERATION_SCHEMA_VERSION = "sem.typed_materialized_generation.v2"


@dataclass(frozen=True, slots=True)
class TypedMaterializedGeneration:
    generation: str
    base_generation: str
    candidate_id: str
    architecture: MemoryArchitectureSpec
    source_sequence: int
    source_snapshot_digest: str
    records: tuple[NodePartitionedRecord, ...]

    _DOCUMENT_FIELDS = frozenset(
        {
            "schema_version",
            "generation",
            "base_generation",
            "candidate_id",
            "architecture",
            "source_sequence",
            "source_snapshot_digest",
            "records",
            "document_digest",
        }
    )

    def to_document(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema_version": TYPED_GENERATION_SCHEMA_VERSION,
            "generation": self.generation,
            "base_generation": self.base_generation,
            "candidate_id": self.candidate_id,
            "architecture": architecture_to_dict(self.architecture),
            "source_sequence": self.source_sequence,
            "source_snapshot_digest": self.source_snapshot_digest,
            "records": [
                {
                    "node_id": record.node_id,
                    "record_id": record.record_id,
                    "sequence": record.sequence,
                    "text": record.text,
                    "payload": dict(record.payload),
                    "source_refs": list(record.source_refs),
                }
                for record in self.records
            ],
        }
        return {**body, "document_digest": canonical_digest(body)}

    @classmethod
    def from_document(cls, document: dict[str, object]) -> "TypedMaterializedGeneration":
        if set(document) != cls._DOCUMENT_FIELDS:
            missing = tuple(sorted(cls._DOCUMENT_FIELDS - set(document)))
            unknown = tuple(sorted(set(document) - cls._DOCUMENT_FIELDS))
            raise TypedMaterializationError(
                f"typed generation document schema mismatch: missing={missing!r} unknown={unknown!r}"
            )
        if document["schema_version"] != TYPED_GENERATION_SCHEMA_VERSION:
            raise TypedMaterializationError("unsupported typed generation schema version")
        digest = document["document_digest"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise TypedMaterializationError("typed generation document digest is invalid")
        body = {key: value for key, value in document.items() if key != "document_digest"}
        if canonical_digest(body) != digest:
            raise TypedMaterializationError("typed generation document digest mismatch")

        architecture_document = document["architecture"]
        if not isinstance(architecture_document, dict):
            raise TypedMaterializationError("typed generation architecture document is invalid")
        architecture = architecture_from_dict(architecture_document)

        raw_records = document["records"]
        if not isinstance(raw_records, (list, tuple)):
            raise TypedMaterializationError("typed generation records must be a sequence")
        records: list[NodePartitionedRecord] = []
        record_fields = {"node_id", "record_id", "sequence", "text", "payload", "source_refs"}
        for raw in raw_records:
            if not isinstance(raw, dict) or set(raw) != record_fields:
                raise TypedMaterializationError("typed generation record schema mismatch")
            sequence = raw["sequence"]
            payload = raw["payload"]
            source_refs = raw["source_refs"]
            string_fields = (raw["node_id"], raw["record_id"], raw["text"])
            if any(not isinstance(value, str) for value in string_fields):
                raise TypedMaterializationError("typed generation record string fields are invalid")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
                raise TypedMaterializationError("typed generation record sequence must be a non-negative integer")
            if not isinstance(payload, dict) or not isinstance(source_refs, (list, tuple)):
                raise TypedMaterializationError("typed generation record payload/source_refs are invalid")
            if any(not isinstance(ref, str) or not ref.strip() for ref in source_refs):
                raise TypedMaterializationError("typed generation record source_refs must be non-empty strings")
            records.append(
                NodePartitionedRecord(
                    raw["node_id"],
                    raw["record_id"],
                    sequence,
                    raw["text"],
                    dict(payload),
                    tuple(source_refs),
                )
            )

        source_sequence = document["source_sequence"]
        if isinstance(source_sequence, bool) or not isinstance(source_sequence, int) or source_sequence < 0:
            raise TypedMaterializationError("typed generation source_sequence must be a non-negative integer")
        identity_fields = ("generation", "base_generation", "candidate_id", "source_snapshot_digest")
        identities = {name: document[name] for name in identity_fields}
        if any(not isinstance(value, str) or not value.strip() for value in identities.values()):
            raise TypedMaterializationError("typed generation identity fields must be non-empty strings")
        source_digest = identities["source_snapshot_digest"]
        if len(source_digest) != 64 or any(char not in "0123456789abcdef" for char in source_digest):
            raise TypedMaterializationError("typed generation source snapshot digest is invalid")

        cls_validator = ArchitectureValidator()
        cls_validator.verify(architecture)
        normalized_records = cls._validate_decoded_records(architecture, tuple(records))
        return cls(
            identities["generation"],
            identities["base_generation"],
            identities["candidate_id"],
            architecture,
            source_sequence,
            identities["source_snapshot_digest"],
            normalized_records,
        )

    @staticmethod
    def _validate_decoded_records(
        architecture: MemoryArchitectureSpec,
        records: tuple[NodePartitionedRecord, ...],
    ) -> tuple[NodePartitionedRecord, ...]:
        return TypedMemoryMaterializer._validate_records(architecture, records)

    def deluxe_snapshot(self) -> NodePartitionedDeluxeSnapshot:
        return NodePartitionedDeluxeSnapshot(
            project_deluxe_architecture(self.architecture, generation=self.generation),
            self.records,
        )



class TypedGenerationDriftError(RuntimeError):
    pass


class TypedGenerationArtifactError(RuntimeError):
    pass


class TypedGenerationArtifactPort(Protocol):
    def load(self, generation: str) -> TypedMaterializedGeneration: ...


@dataclass(frozen=True, slots=True)
class PinnedEvidenceMaterializationSource(EvidenceMaterializationSource):
    """Read-only materialization source over one already-pinned evidence cut."""

    evidence: EvidenceReadPort

    def pin(self) -> EvidenceReadPort:
        return self.evidence


class LiveTypedDeluxeSnapshotSource(DeluxeServingSource):
    """Build one Deluxe read projection from the session's pinned J_mem cut.

    This is a read-side derivation only. The session state remains the sole
    evidence and generation authority; the typed generation is never written
    back by serving.
    """

    def __init__(
        self,
        state: SEMSessionStatePort,
        *,
        architecture: MemoryArchitectureSpec,
        contracts: tuple[MaterializationContract, ...],
        builder: TypedNodeBuilderPort,
        candidate_id: str,
    ) -> None:
        if not candidate_id.strip():
            raise TypedMaterializationError("live Deluxe snapshot candidate_id is required")
        self._state = state
        self._architecture = architecture
        self._contracts = contracts
        self._builder = builder
        self._candidate_id = candidate_id

    def open_deluxe_snapshot(self):
        generation, evidence = self._state.open_serving_cut()
        typed = TypedMemoryMaterializer(
            PinnedEvidenceMaterializationSource(evidence),
            self._builder,
        ).build(
            generation,
            base_generation=generation,
            candidate_id=self._candidate_id,
            architecture=self._architecture,
            contracts=self._contracts,
        )
        return typed.deluxe_snapshot()


def build_live_typed_snapshot_factory(
    *,
    architecture: MemoryArchitectureSpec,
    contracts: tuple[MaterializationContract, ...],
    builder: TypedNodeBuilderPort,
    candidate_id: str = "deluxe.live.read.v1",
):
    """Compose a session-bound Deluxe factory over pinned canonical evidence."""

    ArchitectureValidator().verify(architecture)
    return lambda state: LiveTypedDeluxeSnapshotSource(
        state,
        architecture=architecture,
        contracts=contracts,
        builder=builder,
        candidate_id=candidate_id,
    )


def build_sem_paper_live_deluxe_snapshot_factory(
    transformer: TypedSemanticNodeTransformPort,
    *,
    preset: str = "seed_c_v018",
    candidate_id: str = "deluxe.live.sem_paper.v1",
):
    """Build the current Paper Deluxe read factory from an explicit transform seam."""

    configuration: SemPaperTypedMaterializationConfiguration = build_sem_paper_typed_materialization_configuration(
        transformer,
        preset=preset,
    )
    return build_live_typed_snapshot_factory(
        architecture=configuration.architecture,
        contracts=configuration.contracts,
        builder=configuration.builder,
        candidate_id=candidate_id,
    )


class AdoptedTypedGenerationSource(DeluxeServingSource):
    """Read provider for one generation after the authoritative state adopts it."""

    def __init__(self, state: SEMSessionStatePort, generation: TypedMaterializedGeneration) -> None:
        self._state = state
        self._generation = generation

    def open_deluxe_snapshot(self) -> NodePartitionedDeluxeSnapshot:
        current = self._state.current_generation()
        if current != self._generation.generation:
            raise TypedGenerationDriftError(
                f"typed Deluxe generation {self._generation.generation} is not adopted; current is {current}"
            )
        return self._generation.deluxe_snapshot()


def build_adopted_typed_snapshot_factory(generation: TypedMaterializedGeneration):
    """Compose a session factory around one already-adopted typed generation."""

    def factory(state: SEMSessionStatePort) -> AdoptedTypedGenerationSource:
        return AdoptedTypedGenerationSource(state, generation)

    return factory


class PersistedAdoptedTypedGenerationSource(DeluxeServingSource):
    """Reload typed memory from an injected authoritative artifact source."""

    def __init__(self, state: SEMSessionStatePort, artifacts: TypedGenerationArtifactPort) -> None:
        self._state = state
        self._artifacts = artifacts

    def open_deluxe_snapshot(self) -> NodePartitionedDeluxeSnapshot:
        current = self._state.current_generation()
        try:
            generation = self._artifacts.load(current)
        except Exception as exc:
            if isinstance(exc, TypedGenerationArtifactError):
                raise
            raise TypedGenerationArtifactError(f"failed to load adopted typed generation {current}") from exc
        if generation.generation != current:
            raise TypedGenerationDriftError(
                f"artifact generation {generation.generation} does not match adopted generation {current}"
            )
        return generation.deluxe_snapshot()


def build_persisted_adopted_typed_snapshot_factory(artifacts: TypedGenerationArtifactPort):
    def factory(state: SEMSessionStatePort) -> PersistedAdoptedTypedGenerationSource:
        return PersistedAdoptedTypedGenerationSource(state, artifacts)

    return factory


class TypedMaterializerAdapter:
    """Adapter from typed materialization into the existing adoption prepare port."""

    def __init__(self, materializer: "TypedMemoryMaterializer") -> None:
        self.materializer = materializer

    def clean_build(
        self,
        generation: str,
        *,
        base_generation: str,
        candidate_id: str,
        target_spec_digest: str,
        contracts: tuple[MaterializationContract, ...],
        target_spec: object | None = None,
    ) -> PreparedGeneration:
        if not isinstance(target_spec, MemoryArchitectureSpec):
            raise TypedMaterializationError("Deluxe adoption requires a typed MemoryArchitectureSpec target")
        typed = self.materializer.build(
            generation,
            base_generation=base_generation,
            candidate_id=candidate_id,
            architecture=target_spec,
            contracts=contracts,
        )
        records = tuple((record.node_id, record.record_id) for record in typed.records)
        return PreparedGeneration(
            generation,
            base_generation,
            candidate_id,
            typed.source_sequence,
            typed.source_snapshot_digest,
            target_spec_digest,
            records,
            typed_generation=typed,
        )


class TypedMemoryMaterializer:
    """Build an immutable node-partitioned generation from J_mem only.

    The injected builder performs the semantic node transforms. This class
    refuses to infer a typed payload from an arbitrary evidence row and never
    reuses the legacy flat `(node_id, string)` placeholder path.
    """

    def __init__(self, evidence: EvidenceMaterializationSource, builder: TypedNodeBuilderPort) -> None:
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
        contract_by_id = {contract.node_id: contract for contract in contracts}
        for node in architecture.nodes:
            contract = contract_by_id[node.node_id]
            if isinstance(contract.transform_plan, TransformPlan) and (
                contract.source_selector != node.selector or contract.transform_plan != node.transform
            ):
                raise TypedMaterializationError(
                    f"typed materialization contract for {node.node_id} does not match the architecture"
                )
        read_view = self.evidence.pin()
        snapshot = read_view.materialize()
        raw_records = tuple(self.builder.build_records(architecture, read_view, contracts))
        evidence_ids = frozenset(row.evidence_id for row in read_view.iter_rows())
        records = self._validate_records(
            architecture,
            raw_records,
            evidence_ids=evidence_ids,
        )
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
        *,
        evidence_ids: frozenset[str] | None = None,
    ) -> tuple[NodePartitionedRecord, ...]:
        known_nodes = architecture.node_map()
        seen: set[str] = set()
        record_ids = {record.record_id for record in records}
        record_ids_by_node: dict[str, set[str]] = {}
        records_by_node: dict[str, list[NodePartitionedRecord]] = {}
        for record in records:
            if record.node_id not in known_nodes:
                raise TypedMaterializationError(f"record {record.record_id} names unknown node {record.node_id}")
            if record.record_id in seen:
                raise TypedMaterializationError(f"duplicate typed materialized record {record.record_id}")
            if not record.source_refs:
                raise TypedMaterializationError(
                    f"typed materialized record {record.record_id} has no source_refs"
                )
            if evidence_ids is not None:
                unknown_refs = set(record.source_refs) - evidence_ids - record_ids
                if unknown_refs:
                    raise TypedMaterializationError(
                        f"typed materialized record {record.record_id} has unknown source_refs: "
                        f"{sorted(unknown_refs)}"
                    )
            seen.add(record.record_id)
            try:
                validate_payload(known_nodes[record.node_id], record.payload)
            except ValueError as exc:
                descriptor = describe_exception(exc)
                raise TypedMaterializationError(
                    f"{descriptor.error_type}[{descriptor.error_digest[:16]}]"
                ) from exc
            record_ids_by_node.setdefault(record.node_id, set()).add(record.record_id)
            records_by_node.setdefault(record.node_id, []).append(record)

        if evidence_ids is not None:
            allowed_refs_by_node: dict[str, frozenset[str]] = {}
            for node in architecture.nodes:
                allowed_refs: set[str] = set()
                for source in node.sources:
                    if source.kind is SourceKind.EVIDENCE:
                        allowed_refs.update(evidence_ids)
                    elif source.node_id is not None:
                        allowed_refs.update(record_ids_by_node.get(source.node_id, set()))
                allowed_refs_by_node[node.node_id] = frozenset(allowed_refs)

            for record in records:
                unknown_refs = set(record.source_refs) - allowed_refs_by_node[record.node_id]
                if unknown_refs:
                    raise TypedMaterializationError(
                        f"typed materialized record {record.record_id} references undeclared ancestry: "
                        f"{sorted(unknown_refs)}"
                    )

        normalized: list[NodePartitionedRecord] = []
        for node in architecture.nodes:
            node_records = records_by_node.get(node.node_id, ())
            if node.mode is MemoryMode.CURRENT:
                latest: dict[tuple[object, ...], NodePartitionedRecord] = {}
                for record in node_records:
                    key = tuple(canonical_digest(record.payload.get(field)) for field in node.primary_key)
                    previous = latest.get(key)
                    if previous is None or (record.sequence, record.record_id) > (previous.sequence, previous.record_id):
                        latest[key] = record
                normalized.extend(latest.values())
            elif node.mode is MemoryMode.AGGREGATE:
                keys: set[tuple[object, ...]] = set()
                for record in node_records:
                    key = tuple(canonical_digest(record.payload.get(field)) for field in node.primary_key)
                    if key in keys:
                        raise TypedMaterializationError(
                            f"aggregate node {node.node_id} emitted duplicate primary key"
                        )
                    keys.add(key)
                    normalized.append(record)
            else:
                normalized.extend(node_records)
        return tuple(sorted(normalized, key=lambda record: (record.node_id, record.sequence, record.record_id)))



__all__ = [
    "TypedMaterializationError",
    "TypedMaterializerAdapter",
    "TypedMaterializedGeneration",
    "TYPED_GENERATION_SCHEMA_VERSION",
    "TypedMemoryMaterializer",
    "TypedNodeBuilderPort",
    "TypedGenerationDriftError",
    "TypedGenerationArtifactError",
    "TypedGenerationArtifactPort",
    "PinnedEvidenceMaterializationSource",
    "LiveTypedDeluxeSnapshotSource",
    "build_live_typed_snapshot_factory",
    "build_sem_paper_live_deluxe_snapshot_factory",
    "AdoptedTypedGenerationSource",
    "PersistedAdoptedTypedGenerationSource",
    "build_adopted_typed_snapshot_factory",
    "build_persisted_adopted_typed_snapshot_factory",
]
