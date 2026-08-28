from __future__ import annotations
from pathlib import Path
from research_platform.governance.performance.providers import RepositoryPerformanceSourceInventory, FilesystemPerformanceSnapshotStore
from research_platform.governance.providers import RepositorySourceTree
from research_platform.governance.performance.runtime import PerformanceGovernanceService, PerformanceScanner, PythonPerformanceAnalyzer, JavaScriptPerformanceAnalyzer, ShellPerformanceAnalyzer

def build_performance_governance(root:Path, *, state_root:Path|None=None)->PerformanceGovernanceService:
    root=Path(root).resolve(); state=Path(state_root) if state_root is not None else root/'.local'/'performance-governance'
    return PerformanceGovernanceService(PerformanceScanner(RepositoryPerformanceSourceInventory(RepositorySourceTree(root)),(PythonPerformanceAnalyzer(),JavaScriptPerformanceAnalyzer(),ShellPerformanceAnalyzer())),FilesystemPerformanceSnapshotStore(state, baseline_path=root/'docs'/'status'/'performance'/'PERFORMANCE_BASELINE.json'))
