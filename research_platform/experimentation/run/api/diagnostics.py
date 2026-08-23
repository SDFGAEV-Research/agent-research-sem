from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class RunDiagnosticsPort(Protocol):
    """Durable run diagnostics seam shared by all experiment environments."""

    def event(
        self,
        event: str = "",
        *,
        phase: str = "workload",
        attributes: Mapping[str, object] | None = None,
        level: str = "DEBUG",
        correlation_refs: tuple[str, ...] = (),
    ) -> None: ...

    def metric(
        self,
        name: str = "",
        value: float = 0.0,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None: ...

    def failure(
        self,
        code: str = "",
        message: str = "",
        *,
        phase: str = "workload",
        exception: BaseException | None = None,
        attributes: Mapping[str, object] | None = None,
        correlation_refs: tuple[str, ...] = (),
    ) -> None: ...


__all__ = ["RunDiagnosticsPort"]
