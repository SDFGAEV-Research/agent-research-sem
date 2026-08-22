# Round 106 — Deluxe session composition and adopted-generation binding

## Changes

- Added `DeluxeServingSessionSource` and `DeluxeSnapshotFactory` contracts.
- Extended the SEM composition root so an explicit Deluxe serving provider
  receives a project-owned typed snapshot source.
- Added `build_deluxe_session_serving`.
- Added `AdoptedTypedGenerationSource`, which checks the unique session
  generation before every Deluxe snapshot open and rejects generation drift.
- Kept the Core flat serving source separate; no row-to-node fallback exists.

## Root-cause correction

Before this round, `SEMSessionAssembly` always supplied
`ReadOnlyServingSessionSource`, so the newly migrated Deluxe service could
only be tested in isolation. The session runtime now selects the explicit
Deluxe source only when a typed snapshot factory is composed. Selecting the
Deluxe provider without that factory fails during implementation construction.

## Verification

- Architecture/projection/typed materialization/composition tests: 13 passed.
- Existing SEM evolution/adoption/method-boundary tests in the focused run:
  39 passed.
- The real SEM session assembly reached `build_deluxe_session_serving` with an
  adopted typed generation and returned node-partitioned context.
- Generation drift was rejected before a stale Deluxe snapshot could be read.
- No Minecraft process, model process, server deployment, or scientific
  experiment was run in this round.

## Remaining boundary

The typed generation is now reachable through the serving composition root,
but the existing candidate/adoption materializer still publishes the old flat
`PreparedGeneration` shape. The next migration must make the current unique
adoption authority persist and reload the typed generation artifact; it must
not add a second adoption service or silently retain the flat path as a
Deluxe fallback.
