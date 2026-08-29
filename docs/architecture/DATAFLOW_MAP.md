# Dataflow Map — Current Development Architecture

## Scientific decision path

```text
Environment Observation
→ method-owned evidence admission
→ method ingest / scientific state
→ pinned method/evidence read source
→ prompt blocks
→ Prompt Request Build Transaction
→ canonical request body + compiled prompt + tool schemas
→ content-addressed durable refs
→ ModelRequestEnvelope
→ reconstruct + verify exact model-visible request
→ model/provider
→ agent decision
→ scoped capability resolution
→ capability policy pipeline
→ effect-safe execution / environment action
→ EffectReceipt + observations
→ task/verifier result
→ method task_completed/evolution inputs
```

The model-visible request is not inferred later from logs. It is an explicitly durable, reconstructable fact.

## Capability/effect path

```text
DecisionCycle Scope
→ capability registration lease
→ monotonic guard decisions
→ approval
→ capability.invoke operation
→ effect intent prepare
→ side effect
→ effect certainty
→ result/commit or reconcile
→ post policy
→ final capability outcome
→ scope lease release/dispose
```

A post-policy rejection does not erase the fact that an effect may already have executed.

## Operational evidence path

```text
Primary runtime/scientific components
→ DurableFact / Operation / Failure / Mutation / Effect evidence
→ append-only authoritative ledgers/stores
→ ProjectionTail
→ rebuildable diagnostic/status/incident projections
```

Side-plane telemetry receives observations through fail-isolated observers. It is not an authoritative recovery source.

## Projection path

```text
Authoritative source cursor A
+ suffix items A..B
+ source identity/version
→ ProjectionTail
→ projector version
→ checkpoint B
```

Mismatch or rewind means rebuild; the runtime never silently splices incompatible tails.

For forensic ledgers, the read contract is `VerifiedLedgerSlice`: `start_after`, `total_rows`, `checkpoint_hash`, `tail_hash`, and the verified suffix payloads are returned as one coherent cut. The zero-row checkpoint is the zero hash and a terminal checkpoint must equal the authoritative tail. This contract is read-only evidence for projection/rebuild; it does not transfer durable authority from the append-only ledger to the projection.

The disposable forensic SQLite index exposes typed read records rather than anonymous payload dictionaries. `DiagnosticObjectRecord`, `StateWriterRecord`, and `OperationInvocationRecord` bind projection identity columns to a deeply immutable JSON payload and reject identity drift. Diagnostics consume those records internally; operator/crash-bundle boundaries explicitly project them back to JSON. The records are observation cuts only: authoritative evidence remains the verified append-only ledgers.

Compound diagnosis, causal-graph, incident, triage and debug-snapshot joins retain the immutable record payload through the entire internal read transaction. They do not thaw/copy JSON between query stages; mutable JSON is materialized only at explicit operator/artifact compatibility boundaries.

## Recovery path

```text
Failure
→ failure taxonomy + effect certainty + mutation history
→ exact recovery plan
→ frozen participant/model/service/runtime identities
→ reconcile uncertain external effects
→ verified checkpoint/state cut
→ resume incomplete work
```

## Record-plane rule

```text
DURABLE_FACT           → reconstruction/replay allowed
LIVE_INTERCEPTION      → current-execution policy only
SIDE_PLANE_OBSERVATION → diagnostics/metrics only
```

Any interception that changes future model-visible or authoritative state must emit/commit the corresponding durable fact.

## Architecture audit rules

- `j_audit/j_eval -> method_memory`: forbidden.
- platform/runtime -> concrete method internals: forbidden.
- method -> concrete environment/server/model implementation: forbidden.
- derived projection/cache -> authoritative state: forbidden.
- scientific/runtime implementation -> telemetry backend ownership: forbidden.
- capability policy -> bypass effect-safety engine: forbidden.
- model-visible request without durable model-request reference: forbidden by request-build invariant.
