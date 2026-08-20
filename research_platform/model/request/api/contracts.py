from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol, runtime_checkable

from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity, canonical_digest


@dataclass(frozen=True, slots=True)
class ContentRef:
    sha256: str
    size_bytes: int
    media_type: str

    def __post_init__(self) -> None:
        if len(self.sha256) != 64:
            raise ValueError("content sha256 must be a 64-character hex digest")
        int(self.sha256, 16)
        if self.size_bytes < 0:
            raise ValueError("content size_bytes must be non-negative")
        if not self.media_type.strip():
            raise ValueError("content media_type must be non-empty")


@dataclass(frozen=True, slots=True)
class ModelRequestEnvelope:
    schema_version: str
    request_id: str
    context: ExecutionContext
    role: str
    model: ImmutableModelIdentity
    prompt_generation_id: str
    prompt_id: str
    prompt_digest: str
    request_body: ContentRef
    compiled_prompt: ContentRef | None = None
    tool_schema_bundle: ContentRef | None = None
    source_artifact_refs: tuple[str, ...] = ()
    source_state_refs: tuple[str, ...] = ()
    envelope_digest: str = ""

    def __post_init__(self) -> None:
        for value in (
            self.schema_version,
            self.request_id,
            self.role,
            self.prompt_generation_id,
            self.prompt_id,
            self.prompt_digest,
        ):
            if not value.strip():
                raise ValueError("model request identity fields must be non-empty")
        expected = canonical_digest({
            key: value
            for key, value in asdict(self).items()
            if key != "envelope_digest"
        })
        if self.envelope_digest and self.envelope_digest != expected:
            raise ValueError("model request envelope digest mismatch")
        object.__setattr__(self, "envelope_digest", expected)


@dataclass(frozen=True, slots=True)
class ReconstructedModelRequest:
    request_body: dict[str, object]
    compiled_prompt_text: str | None
    tool_schema_bundle: object | None


@runtime_checkable
class ContentAddressedStorePort(Protocol):
    durability: str

    def put(self, payload: bytes, *, media_type: str) -> ContentRef: ...
    def get(self, ref: ContentRef) -> bytes: ...


@runtime_checkable
class ModelRequestLedgerPort(Protocol):
    durability: str

    def append(self, envelope: ModelRequestEnvelope) -> None: ...
    def get(self, request_id: str) -> ModelRequestEnvelope: ...


@runtime_checkable
class ModelRequestRecorderPort(Protocol):
    def record(
        self,
        *,
        request_id: str,
        context: ExecutionContext,
        role: str,
        model: ImmutableModelIdentity,
        prompt_generation_id: str,
        prompt_id: str,
        prompt_digest: str,
        request_body: dict[str, object],
        compiled_prompt_text: str | None = None,
        tool_schema_bundle: object | None = None,
        source_artifact_refs: tuple[str, ...] = (),
        source_state_refs: tuple[str, ...] = (),
    ) -> ModelRequestEnvelope: ...

    def reconstruct(self, envelope: ModelRequestEnvelope) -> ReconstructedModelRequest: ...
    def reconstruct_request_body(self, envelope: ModelRequestEnvelope) -> dict[str, object]: ...
    def verify_visible_request(self, envelope: ModelRequestEnvelope, actual_body: dict[str, object]) -> None: ...


__all__ = [
    "ContentAddressedStorePort",
    "ContentRef",
    "ModelRequestEnvelope",
    "ModelRequestLedgerPort",
    "ModelRequestRecorderPort",
    "ReconstructedModelRequest",
]
