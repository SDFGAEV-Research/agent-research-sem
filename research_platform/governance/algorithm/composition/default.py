from __future__ import annotations

from pathlib import Path

from research_platform.governance.algorithm.providers import (
    FilesystemAlgorithmSnapshotStore,
    FilesystemFileAnalysisCache,
    RepositorySourceInventory,
)
from research_platform.governance.algorithm.runtime import (
    AlgorithmGovernanceService,
    AlgorithmScanner,
    JavaScriptAlgorithmAnalyzer,
    PythonAlgorithmAnalyzer,
    ShellAlgorithmAnalyzer,
)


def build_algorithm_governance(
    root: Path,
    *,
    exact: bool = False,
    state_root: Path | None = None,
) -> AlgorithmGovernanceService:
    root = Path(root).resolve()
    state = Path(state_root) if state_root is not None else root / ".local" / "algorithm-governance"
    cache = None if exact else FilesystemFileAnalysisCache(state / "cache")
    scanner = AlgorithmScanner(
        inventory=RepositorySourceInventory(root),
        analyzers=(PythonAlgorithmAnalyzer(), JavaScriptAlgorithmAnalyzer(), ShellAlgorithmAnalyzer()),
        cache=cache,
        use_cache=not exact,
    )
    # Baseline is a reviewed repository artifact; current/history stay in local durable state.
    repository_baseline = root / "docs" / "status" / "algorithm" / "ALGORITHM_BASELINE.json"
    store = FilesystemAlgorithmSnapshotStore(state, baseline_path=repository_baseline)
    return AlgorithmGovernanceService(scanner=scanner, store=store)


__all__ = ["build_algorithm_governance"]
