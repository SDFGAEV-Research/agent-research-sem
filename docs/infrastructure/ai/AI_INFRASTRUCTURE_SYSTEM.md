# AI Infrastructure System

The platform treats model acquisition and serving as reusable infrastructure,
not as code embedded in one paper project. The authority remains the existing
recursive `model` system; this document describes how its child modules compose
without creating a second registry.

## Ownership topology

```text
model
├── stack
│   └── immutable model + artifact + runtime-build + parallelism identity
├── asset
│   └── source acquisition, resumable receipt, provenance and storage pool
├── assignment
│   └── role-to-deployment identity
├── deployment
│   └── desired/applied contract, process lifecycle, logs and reconciliation
├── qualification
│   └── measured host/role qualification evidence
└── serving
    └── endpoint, admission, recovery and runtime qualification protocols

environment/python ── owns Python/Conda/Mamba environment lifecycle
resource/compute   ── owns GPU inventory and live resource observation
event spine        ── owns logs, metrics, traces and projections
```

The `stack` module is a composition-time identity. It does not start a
process, download weights, select a GPU, or inspect health. Those operations
remain behind the interfaces of the owning child modules. A project therefore
binds one stack and imports the resulting narrow runtime interfaces; it does
not reimplement SGLang/vLLM startup or model download logic.

## Standard lifecycle

```text
stack declaration
  → source acquisition with resumable receipt
  → asset registration and artifact inspection
  → managed Python environment and package-lock verification
  → deployment materialization with exact engine arguments
  → GPU allocation observation and conflict reporting
  → HTTP/process readiness and event publication
  → qualification / exact recovery when the scientific run requires it
```

Mutable management state and scientific freeze state remain separate. A
deployment restart uses the same model/revision/engine/runtime contract; it
never silently changes model quality, context, precision, tensor parallelism,
or prompt semantics.

## Current implementation slice

- `model.stack` now owns `ModelStackSpec`, `ModelArtifactClosure` and
  `RuntimeBuildIdentity`; they are no longer owned by `model.serving`.
- Hugging Face acquisition exposes typed `max_workers` while preserving
  resumability and the same source/destination identity.
- The management CLI accepts `model fetch --max-workers N`.
- SGLang and vLLM launch templates remain deployment adapters, not project
  code.

The active Paper-1 server download used the same stack inputs and an explicit
worker count as an operational acceleration. The asset is not considered
usable until all expected files are verified and the model manager writes its
registration receipt.

## Next reusable increments

The next vertical slice is a stack manifest/catalog that references, rather
than duplicates, the asset, environment and deployment authorities. It will
provide `inspect`, exact `start`, `stop`, `status` and recovery-plan commands
while retaining the existing per-child ledgers and event records. A stack
manifest will become the single project-facing declaration for future
models, serving engines and servers.
