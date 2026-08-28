from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True, slots=True)
class RepositorySourceBlob:
    """Decoded repository source with identity bound to exact filesystem bytes."""

    relative_path: str
    suffix: str
    sha256: str
    text: str


class RepositorySourcePort(Protocol):
    """Read-only source discovery contract; scoring semantics stay with consumers."""

    def documents(self, *, suffixes: Iterable[str]) -> Iterable[RepositorySourceBlob]: ...


@dataclass(frozen=True, slots=True)
class RepositorySourceSnapshot:
    """Immutable source cut for multiple governance analyses over identical bytes."""

    blobs: tuple[RepositorySourceBlob, ...]

    def __post_init__(self) -> None:
        paths = tuple(blob.relative_path for blob in self.blobs)
        if paths != tuple(sorted(paths)):
            raise ValueError("repository source snapshot must be path-sorted")
        if len(paths) != len(set(paths)):
            raise ValueError("repository source snapshot contains duplicate paths")

    def documents(self, *, suffixes: Iterable[str]) -> tuple[RepositorySourceBlob, ...]:
        supported = frozenset(str(suffix).lower() for suffix in suffixes)
        if not supported:
            return ()
        return tuple(blob for blob in self.blobs if blob.suffix in supported)


__all__ = [
    "RepositorySourceBlob",
    "RepositorySourcePort",
    "RepositorySourceSnapshot",
]
