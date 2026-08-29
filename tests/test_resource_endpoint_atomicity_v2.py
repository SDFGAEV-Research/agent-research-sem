from __future__ import annotations

from contextlib import closing
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Event

import pytest

from research_platform.resource.allocation.api import (
    EndpointAllocationRequest,
    EndpointLeasePolicy,
    EndpointAllocationState,
    EndpointBindingProof,
    EndpointProbeResult,
    NetworkEndpoint,
)
from research_platform.resource.providers import SQLiteEndpointAllocationStore
from research_platform.platform.concurrency.api import ConcurrencyBudget
from research_platform.platform.concurrency.composition import build_concurrency_runtime
from research_platform.resource.allocation.runtime import (
    AtomicEndpointAllocator,
    EndpointLeaseHeartbeatError,
    EndpointLeaseHeartbeatFactory,
)
from research_platform.resource.lease.api import LeaseState
from research_platform.resource.providers import SQLiteResourceLeaseRegistry
from research_platform.scope.api import ScopeIdentity, ScopeKind


class _AvailableProbe:
    def __init__(self, barrier: Barrier | None = None) -> None:
        self._barrier = barrier

    def probe(self, endpoint: NetworkEndpoint) -> EndpointProbeResult:
        if self._barrier is not None:
            self._barrier.wait(timeout=5)
        return EndpointProbeResult(endpoint, True, "available")


def _request(allocation_id: str, *, port: int = 25565) -> EndpointAllocationRequest:
    return EndpointAllocationRequest(
        allocation_id=allocation_id,
        holder_scope=ScopeIdentity(ScopeKind.BRANCH, f"branch-{allocation_id}"),
        purpose="atomic endpoint test",
        host="127.0.0.1",
        candidate_ports=(port,),
    )


def _active_lease_count(database: Path) -> int:
    with closing(sqlite3.connect(database)) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM resource_leases WHERE state='active'").fetchone()[0])


def test_same_allocation_race_commits_exactly_one_allocation_and_one_lease() -> None:
    with TemporaryDirectory() as directory:
        database = Path(directory) / "platform.sqlite"
        barrier = Barrier(2)
        left = AtomicEndpointAllocator(
            reservations=SQLiteEndpointAllocationStore(database),
            probe=_AvailableProbe(barrier),
            lease_ttl_seconds=60,
        )
        right = AtomicEndpointAllocator(
            reservations=SQLiteEndpointAllocationStore(database),
            probe=_AvailableProbe(barrier),
            lease_ttl_seconds=60,
        )
        request = _request("same")

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(pool.map(lambda allocator: allocator.allocate(request), (left, right)))

        assert results[0] == results[1]
        assert len(SQLiteEndpointAllocationStore(database).active()) == 1
        assert _active_lease_count(database) == 1


def test_expiry_releases_orphan_and_next_allocation_gets_higher_fencing_token() -> None:
    with TemporaryDirectory() as directory:
        database = Path(directory) / "platform.sqlite"
        store = SQLiteEndpointAllocationStore(database)
        first_allocator = AtomicEndpointAllocator(
            reservations=store,
            probe=_AvailableProbe(),
            lease_ttl_seconds=0.05,
        )
        first = first_allocator.allocate(_request("first"))
        assert first.lease_fencing_token == 1

        expired = store.reconcile_orphans(now=(first.lease_expires_at_epoch_s or 0) + 1)
        assert [row.allocation_id for row in expired] == ["first"]
        assert store.get("first").state is EndpointAllocationState.RELEASED  # type: ignore[union-attr]

        second = AtomicEndpointAllocator(
            reservations=store,
            probe=_AvailableProbe(),
            lease_ttl_seconds=60,
        ).allocate(_request("second"))
        assert second.endpoint == first.endpoint
        assert second.lease_fencing_token > first.lease_fencing_token


def test_renew_is_fenced_and_atomic_with_allocation_expiry_projection() -> None:
    with TemporaryDirectory() as directory:
        database = Path(directory) / "platform.sqlite"
        store = SQLiteEndpointAllocationStore(database)
        allocator = AtomicEndpointAllocator(
            reservations=store,
            probe=_AvailableProbe(),
            lease_ttl_seconds=30,
        )
        current = allocator.allocate(_request("renew"))
        renewed = allocator.renew("renew", ttl_seconds=120)
        assert renewed.lease_fencing_token == current.lease_fencing_token
        assert renewed.lease_expires_at_epoch_s is not None
        assert current.lease_expires_at_epoch_s is not None
        assert renewed.lease_expires_at_epoch_s > current.lease_expires_at_epoch_s

        # Simulate a stale external holder by replacing the lease fencing token.
        with closing(sqlite3.connect(database)) as conn:
            conn.execute(
                "UPDATE resource_leases SET fencing_token=fencing_token+1 WHERE lease_id=?",
                (current.lease_id,),
            )
            conn.commit()
        reconciled = store.get("renew")
        assert reconciled is not None
        assert reconciled.state is EndpointAllocationState.RELEASED
        with pytest.raises(RuntimeError):
            allocator.renew("renew", ttl_seconds=120)


def test_release_updates_lease_and_allocation_in_one_transaction() -> None:
    with TemporaryDirectory() as directory:
        database = Path(directory) / "platform.sqlite"
        store = SQLiteEndpointAllocationStore(database)
        allocator = AtomicEndpointAllocator(reservations=store, probe=_AvailableProbe())
        allocation = allocator.allocate(_request("release"))

        released = allocator.release("release")
        assert released.state is EndpointAllocationState.RELEASED
        lease = SQLiteResourceLeaseRegistry(database).get(allocation.lease_id)
        assert lease.state is LeaseState.RELEASED
        assert allocator.release("release") == released


def test_early_external_lease_release_is_reconciled_by_point_get() -> None:
    with TemporaryDirectory() as directory:
        database = Path(directory) / "platform.sqlite"
        store = SQLiteEndpointAllocationStore(database)
        allocator = AtomicEndpointAllocator(reservations=store, probe=_AvailableProbe())
        allocation = allocator.allocate(_request("orphan"))

        SQLiteResourceLeaseRegistry(database).release(allocation.lease_id)
        current = store.get("orphan")
        assert current is not None
        assert current.state is EndpointAllocationState.RELEASED


def test_concurrent_schema_bootstrap_is_idempotent() -> None:
    with TemporaryDirectory() as directory:
        database = Path(directory) / "platform.sqlite"
        barrier = Barrier(8)

        def build(_: int) -> int:
            barrier.wait(timeout=5)
            SQLiteEndpointAllocationStore(database)
            SQLiteResourceLeaseRegistry(database)
            return 1

        with ThreadPoolExecutor(max_workers=8) as pool:
            assert sum(pool.map(build, range(8))) == 8
        with closing(sqlite3.connect(database)) as conn:
            assert conn.execute(
                "SELECT value FROM endpoint_meta WHERE key='schema_version'"
            ).fetchone() == ("3",)
            assert conn.execute(
                "SELECT value FROM resource_meta WHERE key='schema_version'"
            ).fetchone() == ("2",)


def _binding_proof(allocation, *, evidence_ref: str = "runtime-listener-evidence:1") -> EndpointBindingProof:
    return EndpointBindingProof(
        allocation_id=allocation.allocation_id,
        endpoint=allocation.endpoint,
        lease_fencing_token=allocation.lease_fencing_token,
        binder_identity_digest="a" * 64,
        observed_at_epoch_s=1234.5,
        evidence_ref=evidence_ref,
    )


def test_endpoint_binding_requires_current_fencing_and_is_idempotent() -> None:
    with TemporaryDirectory() as directory:
        database = Path(directory) / "platform.sqlite"
        store = SQLiteEndpointAllocationStore(database)
        allocator = AtomicEndpointAllocator(reservations=store, probe=_AvailableProbe())
        reserved = allocator.allocate(_request("bind"))
        assert reserved.state is EndpointAllocationState.RESERVED
        assert reserved.binding_proof_digest is None

        proof = _binding_proof(reserved)
        bound = allocator.confirm_bound(proof)
        assert bound.state is EndpointAllocationState.BOUND
        assert bound.binding_proof_digest == proof.digest()
        assert bound.binding_evidence_ref == proof.evidence_ref
        assert allocator.confirm_bound(proof) == bound

        with pytest.raises(RuntimeError, match="different binding proof"):
            allocator.confirm_bound(_binding_proof(reserved, evidence_ref="runtime-listener-evidence:2"))
        stale = EndpointBindingProof(
            allocation_id=reserved.allocation_id,
            endpoint=reserved.endpoint,
            lease_fencing_token=reserved.lease_fencing_token + 1,
            binder_identity_digest="b" * 64,
            observed_at_epoch_s=1235.0,
            evidence_ref="stale-listener-evidence",
        )
        with pytest.raises(RuntimeError, match="fencing lost"):
            allocator.confirm_bound(stale)

        released = allocator.release(reserved.allocation_id)
        assert released.state is EndpointAllocationState.RELEASED
        assert released.binding_proof_digest == proof.digest()
        assert released.binding_evidence_ref == proof.evidence_ref


def test_v2_active_endpoint_migrates_fail_closed_to_reserved() -> None:
    with TemporaryDirectory() as directory:
        database = Path(directory) / "platform.sqlite"
        with closing(sqlite3.connect(database)) as conn:
            conn.execute("CREATE TABLE endpoint_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO endpoint_meta VALUES('schema_version','2')")
            conn.execute(
                """
                CREATE TABLE endpoint_allocations(
                    allocation_id TEXT PRIMARY KEY, host TEXT NOT NULL, port INTEGER NOT NULL,
                    protocol TEXT NOT NULL, lease_id TEXT NOT NULL, holder_scope_kind TEXT NOT NULL,
                    holder_scope_id TEXT NOT NULL, purpose TEXT NOT NULL, request_digest TEXT NOT NULL,
                    state TEXT NOT NULL, lease_holder_generation INTEGER NOT NULL DEFAULT 1,
                    lease_fencing_token INTEGER NOT NULL DEFAULT 1, lease_expires_at_epoch_s REAL
                )
                """
            )
            conn.execute(
                "INSERT INTO endpoint_allocations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "legacy", "127.0.0.1", 25565, "tcp", "legacy-lease", "branch", "legacy",
                    "legacy endpoint", "d" * 64, "active", 1, 7, 9999999999.0,
                ),
            )
            conn.commit()
        SQLiteEndpointAllocationStore(database)
        with closing(sqlite3.connect(database)) as conn:
            row = conn.execute(
                "SELECT state,binding_proof_digest,binding_evidence_ref,bound_at_epoch_s "
                "FROM endpoint_allocations WHERE allocation_id='legacy'"
            ).fetchone()
            version = conn.execute(
                "SELECT value FROM endpoint_meta WHERE key='schema_version'"
            ).fetchone()
        assert row == ("reserved", None, None, None)
        assert version == ("3",)


def test_endpoint_heartbeat_surfaces_background_renewal_failure() -> None:
    renewed = Event()

    class _FailingAllocations:
        def renew_many(self, allocation_ids: tuple[str, ...], *, ttl_seconds: float | None = None):
            renewed.set()
            raise RuntimeError(f"renew failed: {allocation_ids[0]}:{ttl_seconds}")

    runtime = build_concurrency_runtime(
        budget=ConcurrencyBudget(
            max_blocking_io_workers=1,
            max_cpu_workers=1,
            default_queue_capacity=8,
        ),
        blocking_io_thread_name_prefix="atomic-heartbeat-failure-io",
        timer_name="atomic-heartbeat-failure-timer",
    )
    group = runtime.open_task_group("atomic-heartbeat-failure")
    guard = EndpointLeaseHeartbeatFactory(
        allocations=_FailingAllocations(),  # type: ignore[arg-type]
        task_group=group,
        heartbeat_scheduler=runtime.heartbeats,
        lane_id="atomic-heartbeat-failure-writer",
        lane_capacity=8,
        policy=EndpointLeasePolicy(ttl_seconds=0.2, renewal_interval_seconds=0.01),
    ).create(("allocation-a",))
    guard.start()
    assert renewed.wait(timeout=1.0)
    with pytest.raises(EndpointLeaseHeartbeatError, match="renew failed"):
        guard.assert_healthy()
    with pytest.raises(EndpointLeaseHeartbeatError, match="renew failed"):
        guard.close()
    with pytest.raises(ExceptionGroup):
        runtime.close()
