from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping


class AlgorithmLanguage(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    SHELL = "shell"


class AlgorithmPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


@dataclass(frozen=True, slots=True)
class SourceDocument:
    relative_path: str
    language: AlgorithmLanguage
    sha256: str
    text: str


@dataclass(frozen=True, slots=True)
class AlgorithmMetrics:
    source_lines: int = 0
    branches: int = 0
    loops: int = 0
    max_loop_depth: int = 0
    comprehensions: int = 0
    sort_calls: int = 0
    database_calls_in_loops: int = 0
    io_calls_in_loops: int = 0
    serialization_calls_in_loops: int = 0
    lock_calls_in_loops: int = 0
    subprocess_calls_in_loops: int = 0
    recursive_calls: int = 0
    call_count: int = 0
    cyclomatic_estimate: int = 1
    risk_score: int = 0
    estimated_complexity: str = "O(1)"


@dataclass(frozen=True, slots=True)
class AlgorithmFinding:
    priority: AlgorithmPriority
    code: str
    detail: str
    score: int


@dataclass(frozen=True, slots=True)
class AlgorithmSymbol:
    symbol_id: str
    relative_path: str
    language: AlgorithmLanguage
    qualified_name: str
    line_start: int
    line_end: int
    metrics: AlgorithmMetrics
    findings: tuple[AlgorithmFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class LanguageCoverage:
    language: AlgorithmLanguage
    file_count: int
    symbol_count: int
    parse_errors: int


@dataclass(frozen=True, slots=True)
class AlgorithmSnapshot:
    schema_version: str
    analyzer_revision: str
    source_digest: str
    symbols: tuple[AlgorithmSymbol, ...]
    coverage: tuple[LanguageCoverage, ...]
    generated_unix_ns: int

    @property
    def candidate_count(self) -> int:
        return sum(1 for symbol in self.symbols if symbol.findings)


@dataclass(frozen=True, slots=True)
class SymbolDelta:
    symbol_id: str
    old_score: int | None
    new_score: int | None
    old_complexity: str | None
    new_complexity: str | None
    findings_added: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AlgorithmDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[SymbolDelta, ...]
    moved: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AlgorithmGateReport:
    passed: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    diff: AlgorithmDiff


@dataclass(frozen=True, slots=True)
class FileAnalysis:
    relative_path: str
    language: AlgorithmLanguage
    source_sha256: str
    analyzer_revision: str
    symbols: tuple[AlgorithmSymbol, ...]
    parse_errors: int = 0


__all__ = [
    "AlgorithmDiff",
    "AlgorithmFinding",
    "AlgorithmGateReport",
    "AlgorithmLanguage",
    "AlgorithmMetrics",
    "AlgorithmPriority",
    "AlgorithmSnapshot",
    "AlgorithmSymbol",
    "FileAnalysis",
    "LanguageCoverage",
    "SourceDocument",
    "SymbolDelta",
]
