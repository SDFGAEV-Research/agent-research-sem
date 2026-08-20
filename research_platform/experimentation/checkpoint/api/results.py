from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import OperationResult

from .contracts import RunCheckpointBundle, RunCheckpointManifest


@dataclass(frozen=True, slots=True)
class RunCheckpointResult:
    manifest: RunCheckpointManifest
    operation_results: tuple[OperationResult[object], ...]


@dataclass(frozen=True, slots=True)
class RunRestoreResult:
    bundle: RunCheckpointBundle
    operation_results: tuple[OperationResult[object], ...]


__all__ = ["RunCheckpointResult", "RunRestoreResult"]
