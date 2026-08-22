# Round 130 — Deluxe runtime/evaluation migration slice

## Scope

This round continues the migration of the v034 Deluxe backlog into the
current `projects/sem_paper/method/self_evolving_memory` namespace. The old
tree remains reference material only; no current runtime imports it.

## Implemented

- Added a typed `J_mem`-only `EvidenceIndex` that is rebuildable from a pinned
  evidence cut and selects event types from the current architecture sources.
- Added lossless HOT/WARM/COLD evidence retention governance. It never accepts
  private audit records and never permits lossy deletion of `J_mem`.
- Extended Deluxe lineage with ancestor/depth/reconstructibility queries and
  forward-only architecture-generation lineage.
- Added leaf-only architecture garbage-collection candidate generation. GC
  produces a normal `RETIRE_NODE` proposal and has no compile/accept/adopt
  authority.
- Added a fixed long-window Deluxe candidate audit over paired receipt metrics,
  including stability and created-provider adoption evidence.
- Added read-only architecture trajectory and broad-seed basin analysis.
- Added conditional `REWIRE_SOURCE` and contract-preserving
  `SUBSTITUTE_NODE` compiler operations, disabled by default.
- Added per-task workload metrics so long-window candidate audits can consume
  task-level evidence without reconstructing it from aggregate means.
- Added a derived Deluxe runtime report exposing capability, budget, fault and
  last-query state without exposing a writer.

## Not claimed yet

This slice is not a live Deluxe scientific result. The production entrypoint
still needs the complete qualified host/model composition and a real
SelfEvolve pipeline binding. T2B live Vanilla execution remains pending until
the server bridge dependencies are installed and the canonical gate passes.

## Verification requirement

The exact GitHub revision must be synchronized to Ubuntu, then compiled and
tested on the server. No local test result is used as evidence.
