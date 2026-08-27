from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research_platform.execution.scheduling.api import ExecutionPriority
from research_platform.platform.concurrency.api import ExecutionLaneKind, ExecutionPermitRejected


class AdmissionMode(StrEnum):
    """Group-level behavior when hierarchical capacity is unavailable."""

    BLOCK = "block"
    REJECT = "reject"


class AdmissionRejected(ExecutionPermitRejected):
    """Raised when an admission request uses reject semantics and has no capacity."""


@dataclass(frozen=True, slots=True)
class AdmissionBudget:
    max_total_in_flight: int = 64
    max_in_flight_per_group: int | None = None
    max_in_flight_per_tenant: int | None = None
    max_in_flight_per_resource: int | None = None
    max_blocking_io_in_flight: int | None = None
    max_async_io_in_flight: int | None = None
    max_cpu_in_flight: int | None = None
    max_serial_in_flight: int | None = None

    def __post_init__(self) -> None:
        total = int(self.max_total_in_flight)
        group = total if self.max_in_flight_per_group is None else int(self.max_in_flight_per_group)
        tenant = total if self.max_in_flight_per_tenant is None else int(self.max_in_flight_per_tenant)
        resource = total if self.max_in_flight_per_resource is None else int(self.max_in_flight_per_resource)
        blocking = total if self.max_blocking_io_in_flight is None else int(self.max_blocking_io_in_flight)
        async_io = total if self.max_async_io_in_flight is None else int(self.max_async_io_in_flight)
        cpu = total if self.max_cpu_in_flight is None else int(self.max_cpu_in_flight)
        serial = total if self.max_serial_in_flight is None else int(self.max_serial_in_flight)
        for name, value in (
            ("max_total_in_flight", total),
            ("max_in_flight_per_group", group),
            ("max_in_flight_per_tenant", tenant),
            ("max_in_flight_per_resource", resource),
            ("max_blocking_io_in_flight", blocking),
            ("max_async_io_in_flight", async_io),
            ("max_cpu_in_flight", cpu),
            ("max_serial_in_flight", serial),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        for name, value in (
            ("max_in_flight_per_group", group),
            ("max_in_flight_per_tenant", tenant),
            ("max_in_flight_per_resource", resource),
            ("max_blocking_io_in_flight", blocking),
            ("max_async_io_in_flight", async_io),
            ("max_cpu_in_flight", cpu),
            ("max_serial_in_flight", serial),
        ):
            if value > total:
                raise ValueError(f"{name} cannot exceed max_total_in_flight")
        object.__setattr__(self, "max_total_in_flight", total)
        object.__setattr__(self, "max_in_flight_per_group", group)
        object.__setattr__(self, "max_in_flight_per_tenant", tenant)
        object.__setattr__(self, "max_in_flight_per_resource", resource)
        object.__setattr__(self, "max_blocking_io_in_flight", blocking)
        object.__setattr__(self, "max_async_io_in_flight", async_io)
        object.__setattr__(self, "max_cpu_in_flight", cpu)
        object.__setattr__(self, "max_serial_in_flight", serial)

    def lane_limit(self, lane_kind: ExecutionLaneKind) -> int:
        if lane_kind is ExecutionLaneKind.BLOCKING_IO:
            return int(self.max_blocking_io_in_flight)
        if lane_kind is ExecutionLaneKind.ASYNC_IO:
            return int(self.max_async_io_in_flight)
        if lane_kind is ExecutionLaneKind.CPU:
            return int(self.max_cpu_in_flight)
        if lane_kind is ExecutionLaneKind.SERIAL:
            return int(self.max_serial_in_flight)
        raise ValueError(f"timer is not an admission lane: {lane_kind}")


@dataclass(frozen=True, slots=True)
class AdmissionIdentity:
    tenant_id: str | None = None
    resource_id: str | None = None


@dataclass(frozen=True, slots=True)
class AdmissionIntent:
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    mode: AdmissionMode = AdmissionMode.BLOCK


@dataclass(frozen=True, slots=True)
class GroupAdmissionSnapshot:
    group_id: str
    tenant_id: str | None
    resource_id: str | None
    in_flight: int
    waiting: int


@dataclass(frozen=True, slots=True)
class TenantAdmissionSnapshot:
    tenant_id: str
    max_in_flight: int
    in_flight: int
    waiting: int


@dataclass(frozen=True, slots=True)
class ResourceAdmissionSnapshot:
    tenant_id: str | None
    resource_id: str
    max_in_flight: int
    in_flight: int
    waiting: int


@dataclass(frozen=True, slots=True)
class LaneAdmissionSnapshot:
    lane_kind: ExecutionLaneKind
    max_in_flight: int
    in_flight: int
    waiting: int


@dataclass(frozen=True, slots=True)
class AdmissionTopologySnapshot:
    max_total_in_flight: int
    max_in_flight_per_group: int
    max_in_flight_per_tenant: int
    max_in_flight_per_resource: int
    in_flight: int
    waiting: int
    closed: bool
    admitted_total: int
    rejected_total: int
    cancelled_total: int
    timed_out_total: int
    queued_total: int
    cumulative_queue_wait_seconds: float
    max_queue_wait_seconds: float
    oldest_wait_seconds: float
    groups: tuple[GroupAdmissionSnapshot, ...]
    tenants: tuple[TenantAdmissionSnapshot, ...]
    resources: tuple[ResourceAdmissionSnapshot, ...]
    lanes: tuple[LaneAdmissionSnapshot, ...]
