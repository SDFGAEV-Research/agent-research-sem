from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable

from research_platform.governance.api import RepositorySourceBlob


DEFAULT_EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".local", ".server-state", "dist", "build",
})
ALGORITHM_EXCLUDED_DIRECTORIES = DEFAULT_EXCLUDED_DIRECTORIES | frozenset({
    ".mypy_cache", ".ruff_cache",
})


class RepositorySourceTree:
    """Deterministic, pruned repository source discovery and byte decoding."""

    def __init__(
        self,
        root: Path,
        *,
        include_tests: bool = False,
        excluded_directories: frozenset[str] = DEFAULT_EXCLUDED_DIRECTORIES,
    ) -> None:
        self._root = Path(root).resolve()
        self._include_tests = include_tests
        self._excluded_directories = frozenset(excluded_directories)
        if any(not name or "/" in name or "\\" in name for name in self._excluded_directories):
            raise ValueError("excluded directory entries must be single non-empty names")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def include_tests(self) -> bool:
        return self._include_tests

    def documents(self, *, suffixes: Iterable[str]) -> Iterable[RepositorySourceBlob]:
        """Yield exact source bytes in the legacy global path order.

        Algorithm-Complexity: O(N log N)
        Algorithm-Rationale: N bounds visited directory entries and supported source files; pruning is linear and the final deterministic path sort contributes O(N log N).
        """
        supported = frozenset(str(suffix).lower() for suffix in suffixes)
        if not supported:
            return
        candidates: list[Path] = []
        for directory, dirnames, filenames in os.walk(self._root, topdown=True):
            current = Path(directory)
            dirnames[:] = sorted(
                name
                for name in dirnames
                if name not in self._excluded_directories
                and not (not self._include_tests and current == self._root and name == "tests")
            )
            candidates.extend(
                current / filename
                for filename in filenames
                if (current / filename).suffix.lower() in supported
            )

        for path in sorted(candidates):
            try:
                raw = path.read_bytes()
                text = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            yield RepositorySourceBlob(
                relative_path=path.relative_to(self._root).as_posix(),
                suffix=path.suffix.lower(),
                sha256=hashlib.sha256(raw).hexdigest(),
                text=text,
            )


__all__ = ["ALGORITHM_EXCLUDED_DIRECTORIES", "DEFAULT_EXCLUDED_DIRECTORIES", "RepositorySourceTree"]
