# Episode Evidence Bundle Architecture — 2026-08-24

## Decision

The platform keeps raw capture, final evidence indexing and semantic projections
as three separate authorities:

1. `observability/capture` owns append-only, schema-registered raw records and
   record integrity;
2. `experimentation/run/manifest` owns the immutable final bundle index;
3. project or analysis adapters own replay, summary, diagnosis and distillation
   semantics and publish them only as derived artifacts.

The older Minecraft project demonstrated the value of one episode index across
events, snapshots, conversations, outputs and judge decisions. Its monolithic
recorder, direct synchronous file writes, mutable timers and keyword policies are
not imported. The reusable invariant is preserved through typed platform ports.

## Contract

An `EvidenceBundleManifest` contains:

- one run and bundle identity;
- optional source-checkpoint identity;
- ordered raw stream descriptors with family, schema, count, reference and
  SHA-256;
- explicit required/source-of-truth flags;
- ordered derived artifacts with exact source-stream lineage;
- a terminal `complete` or `failed` status.

A complete bundle is invalid if a required stream is empty. A derived artifact
is invalid if any source stream is absent. Decoder fields are exact; schema drift
cannot be silently ignored.

## Shared execution path

`GenericWorkloadTaskRunner` publishes action lifecycle diagnostics before and
after every environment action. Both events carry the same canonical action
request digest. The finished event additionally identifies the resulting
observation generation and effect receipt. Minecraft and closed-world adapters
use this runner and therefore share the evidence vocabulary without sharing
domain state or action schemas.

## Authority boundaries

- The evidence manifest does not write raw streams.
- Raw capture does not interpret scientific meaning.
- Derived projections are never promoted to source-of-truth records.
- The publisher writes only through `RunArtifactStorePort`.
- Evidence completeness does not imply environment qualification, treatment
  correctness, comparability, metric sufficiency or a scientific claim.

## Next binding

The production composition must expose raw-capture stream summaries to an
evidence-bundle finalizer at the run boundary. The finalizer can then publish
the same required stream set for Minecraft and non-Minecraft repetitions while
allowing environment-specific optional streams through descriptors rather than
branching the platform contract.
