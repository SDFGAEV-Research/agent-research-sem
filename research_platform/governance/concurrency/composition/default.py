from __future__ import annotations
from pathlib import Path
from research_platform.governance.concurrency.providers import FilesystemConcurrencySnapshotStore, RepositoryConcurrencySourceInventory
from research_platform.governance.concurrency.runtime import ConcurrencyGovernanceService, ConcurrencyScanner, JavaScriptConcurrencyAnalyzer, PythonConcurrencyAnalyzer, ShellConcurrencyAnalyzer


def build_concurrency_governance(root:Path, *, state_root:Path|None=None)->ConcurrencyGovernanceService:
    root=Path(root).resolve(); state=Path(state_root) if state_root is not None else root/'.local'/'concurrency-governance'
    return ConcurrencyGovernanceService(
        ConcurrencyScanner(RepositoryConcurrencySourceInventory(root),(PythonConcurrencyAnalyzer(),JavaScriptConcurrencyAnalyzer(),ShellConcurrencyAnalyzer())),
        FilesystemConcurrencySnapshotStore(state,baseline_path=root/'docs'/'governance'/'CONCURRENCY_BASELINE.json'),
    )
