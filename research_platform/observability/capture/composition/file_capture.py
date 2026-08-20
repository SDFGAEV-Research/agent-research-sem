from __future__ import annotations

from pathlib import Path

from ..providers.file_persistence import FileRawObservationPersistence
from ..runtime.lake import RawObservationLake
from ..runtime.registry import RawObservationRegistry
from .catalog import build_default_raw_registry


def build_file_raw_observation_lake(
    root: Path,
    registry: RawObservationRegistry | None = None,
) -> RawObservationLake:
    return RawObservationLake(registry or build_default_raw_registry(), FileRawObservationPersistence(root))


__all__ = ["build_file_raw_observation_lake"]
