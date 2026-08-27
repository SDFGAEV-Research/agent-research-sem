from __future__ import annotations

from dataclasses import dataclass

from research_platform.governance.concurrency.api import ConcurrencyBaseline, ConcurrencyGateReport, ConcurrencySnapshot
from research_platform.governance.concurrency.api.ports import ConcurrencySnapshotStorePort
from .scanner import ConcurrencyScanner


class ConcurrencyBaselineMissing(RuntimeError):
    pass


@dataclass(slots=True)
class ConcurrencyGovernanceService:
    scanner: ConcurrencyScanner
    store: ConcurrencySnapshotStorePort

    def scan(self, *, persist: bool = True) -> ConcurrencySnapshot:
        snapshot=self.scanner.scan()
        if persist:
            self.store.publish_current(snapshot); self.store.append_history(snapshot)
        return snapshot

    def accept_baseline(self) -> ConcurrencySnapshot:
        snapshot=self.scan(persist=True)
        self.store.publish_baseline(ConcurrencyBaseline(
            "concurrency-baseline.v1", snapshot.analyzer_revision, snapshot.blocker_fingerprints,
        ))
        return snapshot

    def gate(self) -> tuple[ConcurrencySnapshot, ConcurrencyGateReport]:
        snapshot=self.scan(persist=True)
        baseline=self.store.load_baseline()
        if baseline is None:
            raise ConcurrencyBaselineMissing("concurrency baseline missing")
        current=set(snapshot.blocker_fingerprints); accepted=set(baseline.blocker_fingerprints)
        new=tuple(sorted(current-accepted))
        parse_errors=sum(row.parse_errors for row in snapshot.coverage)
        blockers=list(new)
        if parse_errors:
            blockers.append(f"concurrency analyzer parse errors: {parse_errors}")
        stale_analyzer = baseline.analyzer_revision != snapshot.analyzer_revision
        if stale_analyzer:
            blockers.append("concurrency analyzer revision changed; baseline must be reviewed and re-accepted")
        warnings=tuple(sorted(accepted-current))
        return snapshot, ConcurrencyGateReport(not blockers, tuple(blockers), warnings)
