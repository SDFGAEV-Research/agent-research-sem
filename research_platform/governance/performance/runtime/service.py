from __future__ import annotations

from dataclasses import dataclass

from research_platform.governance.performance.api import PerformanceBaseline, PerformanceGateReport, PerformanceSnapshot
from research_platform.governance.performance.api.ports import PerformanceSnapshotStorePort
from .diff import gate_against_baseline
from .scanner import PerformanceScanner


class PerformanceBaselineMissing(RuntimeError):
    pass


@dataclass(slots=True)
class PerformanceGovernanceService:
    scanner: PerformanceScanner
    store: PerformanceSnapshotStorePort

    def scan(self, *, persist: bool = True) -> PerformanceSnapshot:
        snapshot = self.scanner.scan()
        if persist:
            self.store.publish_current(snapshot)
            self.store.append_history(snapshot)
        return snapshot

    def accept_baseline(self) -> PerformanceSnapshot:
        snapshot = self.scan(persist=True)
        self.store.publish_baseline(PerformanceBaseline(
            "performance-baseline.v1",
            snapshot.analyzer_revision,
            snapshot.blocker_fingerprints,
        ))
        return snapshot

    def gate(self) -> tuple[PerformanceSnapshot, PerformanceGateReport]:
        baseline = self.store.load_baseline()
        if baseline is None:
            raise PerformanceBaselineMissing(
                "performance baseline is missing; explicitly accept a reviewed baseline"
            )
        current = self.scan(persist=True)
        return current, gate_against_baseline(baseline, current)
