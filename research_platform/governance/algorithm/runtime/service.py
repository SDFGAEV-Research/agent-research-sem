from __future__ import annotations

from dataclasses import dataclass

from research_platform.governance.algorithm.api import AlgorithmGateReport, AlgorithmSnapshot
from research_platform.governance.algorithm.api.ports import AlgorithmSnapshotStorePort
from .diff import gate_against_baseline
from .scanner import AlgorithmScanner


class AlgorithmBaselineMissing(RuntimeError):
    pass


@dataclass(slots=True)
class AlgorithmGovernanceService:
    scanner: AlgorithmScanner
    store: AlgorithmSnapshotStorePort

    def scan(self, *, persist: bool = True) -> AlgorithmSnapshot:
        snapshot = self.scanner.scan()
        if persist:
            self.store.publish_current(snapshot)
            self.store.append_history(snapshot)
        return snapshot

    def accept_baseline(self) -> AlgorithmSnapshot:
        snapshot = self.scan(persist=True)
        self.store.publish_baseline(snapshot)
        return snapshot

    def gate(self) -> tuple[AlgorithmSnapshot, AlgorithmGateReport]:
        baseline = self.store.load_baseline()
        if baseline is None:
            raise AlgorithmBaselineMissing("algorithm baseline is missing; explicitly accept a reviewed baseline")
        current = self.scan(persist=True)
        return current, gate_against_baseline(baseline, current)


__all__ = ["AlgorithmBaselineMissing", "AlgorithmGovernanceService"]
