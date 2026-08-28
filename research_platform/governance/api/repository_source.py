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


__all__ = ["RepositorySourceBlob", "RepositorySourcePort"]
