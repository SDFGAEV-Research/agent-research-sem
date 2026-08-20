# Round 105 — MC diagnostic composition and Deluxe migration audit

## Changes

- Added `StructuredMinecraftDiagnostics` under the MC composition layer.
- MC still depends only on `MinecraftDiagnosticsPort`; structured logging,
  context metrics and durable failure materialization are injected from the
  composition root.
- Provider failure codes remain transport facts. Failure taxonomy, recovery and
  scientific-risk semantics remain outside the MC subsystem.
- Added the first current-tree Deluxe migration audit. The legacy v034 Deluxe
  completion report is explicitly treated as historical evidence, not current
  implementation proof.

## Verification

- MC environment and diagnostic composition tests: 9 passed.
- MC architecture/cross-subsystem/meta-system regression: 65 passed.
- Python syntax compilation for the new diagnostic adapter and focused tests:
  passed.
- No live Minecraft or scientific experiment was run.

## D1 read-side migration

Ported the legacy capability/lifecycle, budget, working-set, Memory Fault and
rebuildable lineage invariants into
`projects/sem_paper/method/self_evolving_memory/deluxe/`. They consume a pinned
project-owned architecture snapshot and do not own `J_mem`, architecture
adoption, acceptance, or evidence persistence.

## Verification

- Deluxe read-side contract tests: 3 passed.
- New Deluxe package has no imports from `memory_runtime`, `memory_ir`,
  `mc_runtime` or the legacy v034 tree.
- Python syntax compilation for D1: passed.

## D2 serving provider foundation

Added an explicit `DeluxeMemoryServingService` over the new
`DeluxeServingSource` seam. It ports capability disclosure, role authorization,
working-set selection, multi-resolution views, bounded Memory Fault recovery and
query diagnostics. It rejects generation drift and node records outside the
pinned architecture.

The service is not yet bound to the default session factory: the current Core
evidence view is flat and cannot truthfully supply the required architecture
node partition. The first part of that migration is now present under
`projects/sem_paper/method/self_evolving_memory/architecture`: it ports the
memory-IR contracts/validator and exposes an explicit
`NodePartitionedDeluxeSnapshot`. Unknown nodes and duplicate projected record
ids are rejected. The remaining binding work is to make the project
materializer publish this partition as an authoritative generation artifact;
no row-to-node shortcut is permitted.

## D2 architecture projection verification

- Current-project architecture IR/projection tests: 9 passed.
- Deluxe read-side plus architecture projection tests: 14 passed.
- The typed materializer now requires an injected semantic node builder and
  rejects incomplete target-node contract coverage; it does not use the flat
  placeholder materializer as a fallback.
- Legacy `seed_c_v018` and `seed_x_v018` both parse and validate through the
  migrated serializer/validator; each has four acyclic nodes.
- The default session serving path is intentionally unchanged until the flat
  `J_mem` materializer is replaced by the typed node-partitioned materializer.
