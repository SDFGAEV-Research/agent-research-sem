# Harness pattern adoption

## Current verified development state

At the current development baseline, these integrations are exercised by the normal platform tests rather than isolated demos: **687 tests collected; 687 passed + 4 subtests; Architecture / Silent-Failure / No-Degradation gates PASS**. The current architecture report contains **6 capability, 30 operation, and 12 event seam edges**.

This platform borrows a small set of runtime ideas from the reviewed DeepSeek Harness source without adopting Cordis or an "everything is a plugin" architecture.

## Adopted boundaries

### Reconstructable model requests

`model_request_api` defines the storage-neutral envelope and ports. The envelope freezes the full `ImmutableModelIdentity` rather than an opaque resume tuple. `model_request_runtime` stores the canonical request body, compiled prompt and tool-schema bundle in content-addressed storage before the request is considered model-visible. `PromptRequestBuildTransaction` requires a `ModelRequestRecorderPort`, verifies the visible body, and returns a fresh body reconstructed from durable content rather than the builder-owned object graph.

The invariant is:

```text
model-visible request bytes == reconstruct(ModelRequestEnvelope)
```

### Scoped registrations

`scope_api` owns the lifecycle contract and `scope_runtime` implements hierarchical scope visibility, reversible registration handles, and quiescent disposal. A child lease against an inherited parent registration is counted against both lifetime boundaries. Individual handles can quiescently retire one registration; concurrent scope disposal callers share the same terminal boundary. Agent-turn capability routes are owned by a decision-cycle scope and are disposed in `finally`, so temporary registrations cannot survive the turn that created them.

### Capability invocation pipeline

`capability_runtime.CapabilityInvocationPipeline` wraps routing and the existing crash-safe effect engine. The order is:

```text
monotonic guards -> approval -> existing effect-safe execution -> post policies

A post-policy rejection is explicitly marked as `execution_completed=True` and `retry_safe=False`; it can never be misinterpreted as evidence that an effectful capability did not run.
```

The pipeline does not implement retry, effect certainty, reconciliation or WAL semantics; those remain in the effect subsystem.

### Incremental projections

`projection_api` defines source watermarks/checkpoints and a single `ProjectionTail` contract that binds the exact starting watermark, ending watermark and item suffix. `projection_runtime` accepts only this tail object. Source rewind, source identity change, same-watermark identity drift or projector-version change fails closed and requires rebuild. Forensics event projection uses the same cursor contract for ledger freshness.


### Record planes

`record_api.ExecutionRecordPlane` makes three semantic planes explicit without collapsing them into one universal event type:

```text
DURABLE_FACT           -> may participate in reconstruction/replay
LIVE_INTERCEPTION      -> affects only the current execution; changes to durable/model-visible truth need an explicit fact
SIDE_PLANE_OBSERVATION -> diagnostics/telemetry only; never primary operational/scientific authority
```

`DurableFact`, capability `GuardDecision`, and observability `EventEnvelope` expose these planes respectively.

### Durable facts and unknown extensions

`fact_api` distinguishes required and ignorable durable facts. `FactDecoderRegistry` skips only unknown facts explicitly marked `IGNORABLE`; an unknown required fact fails closed.

### Architecture graphs

The architecture report now emits generated capability, operation and event seam graphs in addition to import, authority and source-invariant checks. Capability edges combine static source discovery with the declared component registry. Operation/event edges are source-derived. Dynamic event families can declare `EMITTED_EVENT_TYPES` / `CONSUMED_EVENT_TYPES` in their owning source module; the scanner reads those declarations directly, so helper-generated lifecycle events remain visible without a separately maintained graph file.

## Deliberately not adopted

- Cordis is not a runtime dependency.
- Scientific method authority is not dynamically patchable.
- Existing effect journals, failure ledgers, runtime-control state and method evidence are not collapsed into one universal event log.
- Plugin dynamism never overrides treatment identity, scientific firewalls, effect safety or release reproducibility.
