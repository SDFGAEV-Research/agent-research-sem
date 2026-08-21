from __future__ import annotations

from typing import Protocol

from .contracts import (
    EndpointAllocation,
    EndpointAllocationRequest,
    EndpointProbeResult,
    NetworkEndpoint,
)


class EndpointProbePort(Protocol):
    def probe(self, endpoint: NetworkEndpoint) -> EndpointProbeResult: ...


class EndpointAllocationPort(Protocol):
    def allocate(self, request: EndpointAllocationRequest) -> EndpointAllocation: ...
    def release(self, allocation_id: str) -> EndpointAllocation: ...
    def get(self, allocation_id: str) -> EndpointAllocation: ...
    def active(self) -> tuple[EndpointAllocation, ...]: ...


__all__ = ["EndpointAllocationPort", "EndpointProbePort"]
