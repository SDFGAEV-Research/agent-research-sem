from __future__ import annotations

from research_platform.observability.status.api import HealthState
from research_platform.observability.status.runtime import (
    InMemoryStatusEventBus,
    RecoveryLeaseStatusProbe,
)
from research_platform.reliability.recovery.api.lease import RecoveryLease
from research_platform.reliability.recovery.composition import compose_recovery_lease_status_probe


class Source:
    def __init__(self, lease: RecoveryLease | None) -> None:
        self.lease = lease

    def read(self) -> RecoveryLease | None:
        return self.lease

    def evidence_refs(self) -> tuple[str, ...]:
        return ("lease-state:stable",)


def test_recovery_status_is_published_then_consumed_through_event_bus() -> None:
    probe = compose_recovery_lease_status_probe(Source(None), clock=lambda: 100.0)
    snapshot = probe.snapshot()
    assert snapshot.state is HealthState.READY
    assert snapshot.summary == "no active recovery owner"


def test_active_recovery_lease_event_preserves_observation_evidence() -> None:
    source = Source(RecoveryLease("owner-a", "manifest-a", 10.0, 160.0))
    snapshot = compose_recovery_lease_status_probe(source, clock=lambda: 100.0).snapshot()
    assert snapshot.state is HealthState.READY
    assert snapshot.summary == "owner=owner-a; expires_in=60.0s"
    assert snapshot.evidence == ("lease-state:stable",)


def test_expired_recovery_lease_event_is_failed_with_recovery_action() -> None:
    source = Source(RecoveryLease("owner-a", "manifest-a", 10.0, 99.0))
    snapshot = compose_recovery_lease_status_probe(source, clock=lambda: 100.0).snapshot()
    assert snapshot.state is HealthState.FAILED
    assert snapshot.reason_codes == ("recovery_lease_expired",)
    assert "inspect stale recovery owner" in snapshot.next_commands[0]


def test_observation_probe_reports_missing_event_without_reliability_dependency() -> None:
    snapshot = RecoveryLeaseStatusProbe(InMemoryStatusEventBus()).snapshot()
    assert snapshot.state is HealthState.UNKNOWN
    assert snapshot.reason_codes == ("status_event_missing",)
