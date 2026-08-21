# Platform Composition Vocabulary

This file records the terms used by the final architecture migration. It is a
navigation aid, not a second topology or runtime registry.

## Capability composition graph

An immutable, composition-time graph of typed `CapabilityOffer` and
`CapabilityRequirement` metadata. The graph validates locality against the
system catalog, scope visibility, port-interface identity, cardinality,
explicit provider selection and dependency cycles. It produces a
`BindingPlan` with reproducible digest evidence.

## Binding plan

A frozen record of contracts, imported offers and requirement-to-offer edges.
It never contains provider objects and intentionally exposes no generic
lookup, resolution or service-location API. It is run/configuration evidence,
not a runtime bus.

## Runtime port

A narrow protocol object injected after composition. It is the only mechanism
used on a runtime hot path. For example, Minecraft/service/model runtime code
receives `OperatingSystemRoute`; it does not select an OS provider.

## Composition locality

A composition root can construct itself and its direct catalog children only.
Imports from a parent composition are explicit `CapabilityOffer` values, not
permission to traverse the global system tree. This keeps recursive ownership
and replacement local.

## Event spine

An observation-plane stream for logs, metrics, traces and projections. It is
not a command bus, dependency container, scientific-state owner or fallback
execution path.
