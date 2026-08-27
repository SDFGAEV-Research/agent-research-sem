from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Callable, Protocol, TypeVar
from research_platform.platform.kernel import JsonDocument, JsonInput

T = TypeVar("T")


class RunArtifactKind(StrEnum):
    MANIFEST = "manifest"
    PREFLIGHT = "preflight"
    RESULT = "result"
    LOG = "log"
    CLEANUP = "cleanup"
    CHECKPOINT = "checkpoint"
    EVIDENCE = "evidence"
    MODEL = "model"
    METRIC = "metric"


class RunArtifactWriteActorPort(Protocol):
    """Run-local serial owner for mutable durable artifact writes."""

    def call(
        self,
        operation: str,
        fn: Callable[..., T],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> T: ...


class RunArtifactStorePort(Protocol):
    """The only run-owned interface for durable run artifacts."""

    def path(self, name: str, *, kind: RunArtifactKind) -> str: ...

    def directory(self, name: str, *, kind: RunArtifactKind) -> str: ...

    def publish_json(self, name: str, payload: JsonInput | JsonDocument, *, kind: RunArtifactKind) -> str: ...

    def publish_text(self, name: str, content: str, *, kind: RunArtifactKind) -> str: ...

    def append_json(
        self,
        name: str,
        payload: JsonDocument,
        *,
        kind: RunArtifactKind,
    ) -> str: ...


__all__ = ["RunArtifactKind", "RunArtifactStorePort", "RunArtifactWriteActorPort"]
