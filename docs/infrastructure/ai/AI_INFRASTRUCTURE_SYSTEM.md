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
│   └── host/runtime capability facts, compatibility plans and qualification evidence
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

The qualification node now exposes a read-only deployment plan through the
existing management composition:

```text
host + CUDA + GPU + Python + model config + package indexes
    → model/qualification facts
    → exact backend/package plan with rejection evidence
    → environment/python materialization
    → model/deployment launch and model/serving qualification
```

For example, the server-side command below inspects a model without installing
anything or starting a process:

```bash
research-platform-manage --config /data/research-platform/management/runtime_management.sem-ubuntu.json \
  deployment qualify \
  --model-id qwen36-35b-a3b \
  --model-path /data/research-platform/model-pools/nvme/qwen36-35b-a3b \
  --python /data/research-platform/envs/qwen36-sglang-v517-cu130/bin/python \
  --tensor-parallel 4
```

The command emits a digestable plan. On the current RTX 3090 host it records
`sglang==0.5.18` plus the official `sglang-kernel==0.4.6.post1+cu130` as
rejected because the observed kernel libraries are `sm90,sm100`, not the
required `sm86`, and selects `vllm==0.27.1` as the next materialization
candidate. “Selected” means selected for managed installation and subsequent
runtime qualification; it is not a scientific qualification certificate.

On 2026-08-22, the platform also started an independent persistent fetch for
the official `Qwen/Qwen3.8-27B` BF16 candidate at
`/data/research-platform/model-pools/nvme/qwen38-27b`. This does not replace
the Qwen3.6 paper candidate. Qwen3.8 uses a newer dense hybrid GDN/VL serving
path; its separate asset, Python environment, deployment identity and
qualification evidence must remain isolated until the RTX 3090 host path is
proven.

## Server verification

The server architecture gate now passes after the qualification probe was
bound to the platform-wide local command authority. The focused qualification,
evidence-store, Python-environment, public-import and composition-boundary
regression passed **31 tests**, and the no-degradation audit passed. A real
probe on the eight-RTX-3090 host produced facts digest
`cb7df139c9ea1d380b672d74c9d4b8251c330c091a17946689c7636b54875ab9` and plan
digest `c0b4fad8640f44c4ff7075f8ef0ee2496e4a15083f5a388e6f9e68d2c5b6bebc`:
SGLang was rejected because the observed `sm90,sm100` kernel extensions do not
cover host `sm86`, while vLLM `0.27.1` was accepted as the next candidate.
The persisted record digest is
`f795f1d91caa74864b396fce8f9682c6193dba23ce0b6841b693830d38e2ff84`. This is a
compatibility plan, not proof that vLLM has been installed or that the paper
runtime is scientifically qualified.

The qualification composition persists each result under the configured state
directory as a checksummed `model-deployment-qualification-evidence.v1`
document keyed by `plan_digest`. The management command can read a record back
with:

```bash
research-platform-manage --config /data/research-platform/management/runtime_management.sem-ubuntu.json \
  deployment qualification <plan_digest>
```

This makes the full fact/decision join reproducible and auditable; a checksum
or internal request/facts/plan digest mismatch is rejected. It does not grant
the qualification module authority to install packages or start services.

## Next reusable increments

The next vertical slice is an apply operation that consumes the frozen plan
through the existing environment/deployment ports. It will retain exact
package sources, facts, rejection causes and plan digests without turning
qualification into a second asset or deployment registry.
