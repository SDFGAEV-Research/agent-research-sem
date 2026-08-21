# Resource endpoint allocation v1

## Ownership

`resource/lease` is the sole authority for resource identity, ownership and
exclusive lease state. The former `resource/core` implementation was removed;
there is no compatibility import path. `resource/allocation` owns the
resource-specific allocation policy for network endpoints, while
`runtime/server` remains the owner of server process lifecycle.

## Contract

An `EndpointAllocationRequest` contains an explicit host, protocol, ordered
candidate port set, holder scope, owner scope and purpose. The allocator does
not select a random port or silently substitute a default. For each candidate,
the allocator must establish both facts:

1. the resource lease registry has no active lease for the endpoint identity;
2. the injected `EndpointProbePort` reports that the endpoint is available.

The first candidate satisfying both facts becomes an `EndpointAllocation` and
receives a corresponding `ResourceLease`. Repeated allocation with the same
allocation identity is idempotent only while the request digest is identical;
reusing a released allocation identity is rejected. Release is idempotent and
releases the logical lease before marking the allocation released.

The OS probe is deliberately a fact provider, not an ownership authority. The
logical lease serializes platform-managed allocations; server readiness still
has to verify that the launched process actually owns the endpoint. A probe
failure is retained in `EndpointAllocationUnavailable.attempts`, so a failed
branch cannot be mistaken for a valid fallback.

## Three-plane placement

- Composition plane: `PlatformMetaAuthorities.endpoint_allocations` injects the
  allocation port and its lease/probe dependencies.
- Runtime plane: `InMemoryEndpointAllocator` implements the narrow allocation
  port and returns an immutable allocation record; it has no project or MC
  imports.
- Observation plane: the allocator returns structured attempt facts through
  its error; MC diagnostics and the platform event bus may observe them without
  becoming allocation dependencies.

This slice is intentionally local/in-memory for the current composition root.
The server deployment phase must bind the same port to a durable host-scoped
lease store before live multi-process runs; it must not replace this contract
with an untracked project-local port map.
