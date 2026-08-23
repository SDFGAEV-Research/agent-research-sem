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
regression passed **42 tests**, and the no-degradation audit passed. The latest
real probe on the eight-RTX-3090 host now includes host execution, PCI/NUMA GPU
identity, cleaned multi-GPU topology, target-Python NCCL, local model-path
storage, artifact-size facts and target-Python-compatible binary-wheel links,
recursive PEP 658 dependency metadata and graph-wide constraint reconciliation.
It produced facts digest
`66f1bb904303d12bb69d17beda7f7144cdbd9fa21ced3e75f04066b268080823` and plan
digest `216ad4d756cd35df0141e6844df291a2ca4c59e9e56173d204c825f4154eafbe`:
SGLang was rejected because the observed `sm90,sm100` kernel extensions do not
cover host `sm86`, while vLLM `0.27.1` was accepted as the next candidate.
The persisted record digest is
`83ac16117f106ff80e1a7e41f356925283e15f46a463750be6c89bfc24f2dd45`. This is
a compatibility plan, not proof that vLLM has been installed or that the
paper runtime is scientifically qualified.

The latest verified full v4 record supersedes that inherited v3 snapshot:
facts digest `23a10803981db312760d617e5e0bd88650457464eec90e8a7432b38e008d6e2c`,
plan digest `504f51ea3a48f87b8d05cb03c6b55fe3d7c623003ef2da0ea19a2938c4d56c57`,
and record digest `ea8a9403996d56a21bb35781f544b3fa3343bead81aebab354cef14eefb84de6`.
It selects `vllm==0.27.1` with 162 planned packages. SGLang remains rejected
for explicit `cuda-tile`, kernel metadata and SM86 evidence.

The qualification composition persists each result under the configured state
directory as a checksummed `model-deployment-qualification-evidence.v4`
document keyed by `plan_digest`. The v3 schema records the target interpreter's
compatible wheel filenames, Python/ABI/platform tags and source hashes without
downloading the artifacts. v2 snapshots are not silently treated as v3
evidence. The v4 schema adds metadata hashes, direct requirements, typed
dependency nodes and explicit recursive-closure completeness/errors. The
management
command can read a record back with:

```bash
research-platform-manage --config /data/research-platform/management/runtime_management.sem-ubuntu.json \
  deployment qualification <plan_digest>
```

This makes the full fact/decision join reproducible and auditable; a checksum
or internal request/facts/plan digest mismatch is rejected. It does not grant
the qualification module authority to install packages or start services.

## Frozen-plan materialization

The explicit apply operation is now implemented:

```bash
research-platform-manage --config /data/research-platform/management/runtime_management.sem-ubuntu.json \
  deployment apply-qualification <plan_digest> \
  --environment-id <managed-python-environment-id>
```

It loads the checksummed evidence record, consumes only its already-selected
backend and exact package versions, groups packages by their planned index, and
calls the existing `environment/python` package-management port. It never
re-probes, re-ranks candidates, silently switches engines, or bypasses a
rejected plan. After installation it always calls the same port's `pip check`
operation. The resulting command digests, exit codes, plan digest and status
are stored under `model/qualification/applications/` as a separate checksummed
receipt.

The verified v4 implementation is server-validated with **42 focused tests**,
`ARCHITECTURE_GATE_PASS`, and `NO_DEGRADATION_AUDIT_PASS`. The real Qwen
environment has not been passed to this mutating operation yet; its current
vLLM selection remains a plan, not an installation or runtime certificate.

The first official qualification attempt exposed a stale installed
`research-platform-manage` entrypoint that did not contain the new `qualify`
subcommand. The root cause was package-install drift in the management
environment, not a qualification decision. Installing the current checkout
editable on the server repaired the entrypoint; the formal CLI was then
re-run successfully and produced the v3 evidence above.

The first dependency-resolution experiment also exposed an important probe
boundary: `pip install --dry-run --report -` can download large CUDA wheels
while resolving dependencies. The process was stopped after independent
inspection confirmed that no package entered the target environment. The
qualification probe now reads only PEP 503 simple-index artifact links through
the target Python, filters them by the target interpreter's supported tags and
records the result. It never uses dry-run installation as a read-only probe.

The verified v4 closure uses the same target-Python observation boundary:
it fetches simple-index HTML and PEP 658 `.whl.metadata`, evaluates
`Requires-Python` and `Requires-Dist` against the observed interpreter,
recursively resolves compatible binary wheels, reconciles graph-wide
constraints, and rejects incomplete or unsatisfiable closures. It does not
install packages, download wheel payloads, or create a second package
authority. The full server evidence is recorded in
`docs/history/rounds/platform/ROUND45_NOTES.md`.

Round 44 also closes the plan/application seam. A complete dependency closure
is projected into the frozen installation package tuple, so the persisted
plan contains the backend's transitive packages rather than only `vllm` or
`sglang`. Materialization groups those packages by their qualified index and
uses `--no-deps --only-binary=:all:`. The package authority still owns the
actual pip command and `pip check`; qualification owns the graph that is
allowed to reach it. This source change is server-verified and has not yet
installed any package.

The next post-install command is:

```bash
research-platform-manage --config /data/research-platform/management/runtime_management.sem-ubuntu.json \
  deployment runtime-qualify <application_digest>
```

It consumes only a successful application receipt and records three bounded
read-only checks through `environment/python`: backend import, CUDA/device
capability including tensor parallel width, and model-config readability. A
failed probe publishes a failed receipt before re-raising the root exception.
Live HTTP endpoint readiness remains owned by `model/serving` and is not
faked by this pre-start qualification layer.

The complete deployment-qualification contract, current non-claims and the
remaining capability closure are recorded in
`docs/infrastructure/ai/DEPLOYMENT_QUALIFICATION_SYSTEM.md`. That document is
the authoritative design record for extending this slice to host resources,
multi-GPU fabric/NCCL, storage/network, wheel/native-extension evidence and
model-specific backend support without moving ownership into the qualification
module.
