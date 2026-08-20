from __future__ import annotations

from research_platform.reliability.failure.api import fingerprint_failure
from research_platform.reliability.diagnostics.api import IncidentProjectionSync
from research_platform.reliability.forensics.providers.incident_db import IncidentSQLiteStore
from research_platform.reliability.forensics.providers.incident_projection import IncidentProjectionWriter


class IncidentLedgerSynchronizer:
    """Synchronizes a disposable incident projection against one verified failure-ledger cut."""

    def __init__(self,store:IncidentSQLiteStore,writer:IncidentProjectionWriter)->None:
        self.store=store
        self.writer=writer

    def sync(self,ledger)->IncidentProjectionSync:
        with self.store.transaction() as db:
            source_rows,source_tail=self.store.freshness(db)
            total,tail,checkpoint,payloads=ledger.verified_payloads_after(source_rows)
            rebuilt=False
            if source_rows and checkpoint!=source_tail:
                self.store.reset_projection(db)
                source_rows=0
                total,tail,checkpoint,payloads=ledger.verified_payloads_after(0)
                rebuilt=True
            added=0
            for payload in payloads:
                failure_id=str(payload.get("failure_id") or "")
                if not failure_id:
                    continue
                if self.writer.project(
                    db,fingerprint_failure(payload),failure_id,
                    timestamp=float(payload.get("created_at") or 0.0),
                ):
                    added+=1
            self.store.set_freshness(db,total,tail)
        return IncidentProjectionSync(total,tail,added,rebuilt)
