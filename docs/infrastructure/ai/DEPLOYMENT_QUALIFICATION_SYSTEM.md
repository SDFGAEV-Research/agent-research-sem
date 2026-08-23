# Deployment Qualification System

Date: 2026-08-23

This document is the authoritative design and status record for automatic
qualification of open-source model deployment environments. It is a child
document of the `model` system and does not create a second model registry.

## Purpose

Model deployment must not depend on a person manually correlating an operating
system, NVIDIA driver, CUDA runtime, GPU architecture, Python bootstrap,
package wheels, model architecture and serving arguments. A package version
that installs is not necessarily a package version that can import its native
extensions or serve the selected model on the current host.

The platform therefore owns a reproducible qualification flow:

```text
read-only environment observation
  -> normalized capability closure
  -> evidence-backed candidate resolution
  -> exact frozen materialization
  -> bounded pre-start runtime checks
  -> live serving qualification
  -> scientific deployment freeze
```

The system must answer two different questions without conflating them:

1. Which exact backend, package versions, indexes and launch prerequisites are
   justified by this host, Python environment and model artifact?
2. After materialization, does the exact installation actually import, expose
   the required CUDA/device capability, load the model configuration and become
   a live qualified service?

“Latest on an index” is only an observed input. It is never by itself a
qualification decision.

## Current implementation state

The current qualification slice is implemented under `model/qualification`
and is composed through the existing platform management root:

The preferred management entrypoint resolves the target interpreter from the
single Python-environment registry and records that environment identity in
the checksummed request:

```bash
research-platform-manage --config configs/runtime_management.json \
  deployment qualify \
  --model-id MODEL_ID \
  --model-path /models/MODEL_ID \
  --environment-id serving \
  --backend sglang \
  --backend vllm \
  --tensor-parallel 4
```

`--python` remains an explicit path for an interpreter not yet registered by
the platform. Supplying both forms is rejected; the manager never silently
discovers or replaces a registered environment.

The default observation budget is 90 seconds. It bounds the complete recursive
binary-wheel and PEP 658 metadata closure, not only the first package page;
callers may explicitly choose a smaller budget when they want a deliberate
fail-closed time limit.

- the read-only probe captures operating-system identity, kernel/libc, CPU and
  memory limits, cgroup/container markers, NVIDIA driver/CUDA facts, GPU
  inventory and compute capability, PCI/NUMA/power identity, multi-GPU topology
  and target-Python NCCL facts, model-path storage capacity/permissions, Python
  ABI/platform/pip/ensurepip/venv and Torch facts, model `config.json` plus
  artifact/shard statistics, package-index versions and observed SGLang kernel
  architectures; it also reads PEP 503 simple-index links through a bounded
  target-environment network adapter to select compatible binary wheels and
  records their Python/ABI/platform tags and hashes without downloading them;
  the development closure
  path additionally reads PEP 658 metadata and recursively resolves
  `Requires-Dist` under the target interpreter's markers;
- the pure resolver produces a `DeploymentQualificationPlan` with exact
  package names, versions, source indexes, accepted/rejected backend
  candidates, reasons and evidence references;
- the qualification record is checksummed and persisted by `plan_digest`;
- the apply operation consumes only the persisted frozen plan, uses the
  existing `environment/python` package authority, runs `pip check`, and
  persists command digests and status;
- the post-materialization verifier consumes only a successful application
  receipt and performs bounded backend-import, CUDA/device/tensor-parallel and
  model-config checks;
- live HTTP/process readiness remains owned by `model/serving`; the pre-start
  verifier does not pretend that an import check is an endpoint certificate.

The current implementation is deliberately narrow at its seams. The probe
uses the platform-wide local command authority rather than owning a private
subprocess path. Materialization does not re-probe, silently switch engines,
fall back to a rejected candidate or lower the requested deployment quality.
Failures persist a receipt and re-raise the original root exception. The
recursive dependency-closure path is fail-closed: a backend is not accepted
when its transitive metadata is unavailable, its compatible binary wheel is
missing, its specifiers conflict, or a direct URL requirement cannot be
verified from the declared index evidence.

### Verified recursive closure state — Round 45

The worktree now stores one typed dependency node for each resolved package
version under the root package's index observation. Each node is derived from
the same artifact/metadata carrier as the root; it is not a second package
registry. The target interpreter downloads only index HTML and `.whl.metadata`
documents, never wheel payloads. The observation is bounded and records an
explicit error when a page, metadata document, marker, specifier or graph
boundary cannot be proven.

The corrected v4 source is now uploaded and server-verified. The target
interpreter resolves dependency constraints to a fixed point and preserves
deterministic evidence order. On the RTX 3090 host, vLLM completed in the
bounded observation budget with a 162-node closure and 161 transitive packages
in the frozen plan. The resolver selected `numpy==2.3.5` after reconciling
graph-wide constraints instead of accepting the first newest version.

Round 44 closes the materialization boundary: once a dependency closure is
complete, every observed dependency node is copied into the candidate's
frozen `InstallPackage` tuple. The existing Python environment adapter groups
those exact packages by their recorded index and invokes pip with
`--no-deps --only-binary=:all:`. Thus the installer cannot silently discover a
different transitive graph or introduce a source distribution after the
qualification decision. This change is server-verified together with the
closure solver.

## Latest verified server state

The latest inherited server evidence is for the eight-RTX-3090 Ubuntu host:

- Ubuntu 22.04, driver `580.173.02`, driver CUDA API `13.0`, host compute
  capability SM86;
- the selected Qwen3.5-35B-A3B model artifact is registered and its model
  configuration is readable;
- the observed SGLang 0.5.18 candidate with
  `sglang-kernel==0.4.6.post1+cu130` is rejected because the available
  observed kernel libraries expose SM90/SM100 rather than the host's SM86;
- vLLM `0.27.1` is the selected next materialization candidate;
- facts digest:
  `66f1bb904303d12bb69d17beda7f7144cdbd9fa21ced3e75f04066b268080823`;
- plan digest:
  `216ad4d756cd35df0141e6844df291a2ca4c59e9e56173d204c825f4154eafbe`;
- evidence record digest:
  `83ac16117f106ff80e1a7e41f356925283e15f46a463750be6c89bfc24f2dd45`.

The latest full v4 record supersedes the inherited v3 compatibility snapshot:

- facts digest:
  `23a10803981db312760d617e5e0bd88650457464eec90e8a7432b38e008d6e2c`;
- plan digest:
  `504f51ea3a48f87b8d05cb03c6b55fe3d7c623003ef2da0ea19a2938c4d56c57`;
- evidence record digest:
  `ea8a9403996d56a21bb35781f544b3fa3343bead81aebab354cef14eefb84de6`;
- selected backend: `vllm==0.27.1`, with 162 planned packages;
- SGLang rejection: no compatible `cuda-tile==1.6.0rc5` binary wheel,
  unavailable SGLang-kernel metadata, and kernel architectures `sm100,sm90`
  not covering host `sm86`.

Server validation for the current slice is **42 focused tests**,
`ARCHITECTURE_GATE_PASS`, and `NO_DEGRADATION_AUDIT_PASS`. The real Qwen
environment has not been passed to the mutating apply operation, no vLLM
service has been started from this plan, and no scientific SEM result is
claimed from it. The formal `research-platform-manage` entrypoint was also
verified after repairing its stale installed package by a server-side editable
installation of the current checkout; the qualification command now resolves
through the official management surface.

The probe deliberately does not use `pip install --dry-run` to inspect a
candidate: that command can download large CUDA wheels even when no package is
installed. The verified v4 path reads simple-index metadata and PEP 658
metadata through the target Python, reconciles graph-wide constraints and
selects a complete binary dependency closure. It records all transitive
packages in the frozen plan and never uses dry-run installation as a
read-only probe.

## Capability closure to complete

The current facts are the foundation, not the final closure. The completed
system must capture or explicitly mark unavailable every deployment-relevant
fact in the following typed groups:

| Fact group | Required evidence | Owning authority |
| --- | --- | --- |
| Host execution | OS distribution/version, kernel, libc/glibc, CPU ISA/count, RAM, limits, container/runtime identity | `resource` and platform host adapters — observed in current slice |
| GPU/CUDA | GPU UUID/name/memory/SM/PCI identity, driver, driver CUDA API, toolkit, NVRTC, CUDA runtime libraries, MIG state | `resource/compute` — current probe covers the observed subset and records unavailable fields |
| Multi-GPU fabric | device topology, peer access, PCI/NVLink links, NCCL identity and usable communication path | `resource/compute` plus runtime adapters — topology and target-Python NCCL observed; system-library identity unavailable on this host |
| Storage/network | model-path filesystem, free/required capacity, permissions, mount identity, local cache, network/proxy reachability and bandwidth evidence | `resource` and `runtime/server` — local storage/model-path subset observed; network closure remains |
| Python runtime | exact interpreter identity, Python ABI, pip/installer, venv/conda/mamba backend, site-packages, Torch/CUDA ABI, installed native extensions | `environment/python` — ABI/platform and existing package facts observed; wheel/import closure remains |
| Model artifact | revision/digest, config, architecture, dtype, context, tokenizer/processor, shard completeness, required disk and model-specific support | `model/asset` and `model/stack` — config, size/file/shard subset observed; model-specific support remains |
| Package candidates | exact version, wheel tags, Python ABI, CUDA channel, native extension architectures, dependency closure and source digest | `model/qualification` adapters — v4 recursive closure and frozen transitive package plan are server-verified |
| Backend rules | model-family support, GPU/precision/parallelism requirements, launch contract and known incompatibility evidence | `model/qualification` resolver |

The phrase “all relevant information” means that each field is either
observed and recorded, or explicitly recorded as unavailable with its probe
error. Missing information is not silently treated as compatibility.

## Final ownership and data flow

The qualification module is a deep interpretation module, not a second owner
of host, Python, model or serving state:

```text
resource/compute facts ─┐
environment/python facts ─┼─> qualification snapshot
model/asset + stack facts ─┤       |
package/wheel evidence ────┘       v
                            pure compatibility resolver
                                      |
                                      v
                              frozen deployment plan
                                      |
                         environment/python materializer
                                      |
                         model/deployment lifecycle
                                      |
                            model/serving live proof
```

Each arrow is a narrow interface seam. The composition root selects the
adapters. Runtime code receives already bound ports and never discovers a
provider through a broad service locator. Observation, logs, metrics and
diagnostic projections continue through the independent event spine.

The persisted artifacts are separate by meaning:

- capability snapshot: what was observed;
- qualification evidence: why a candidate was accepted or rejected;
- application receipt: what exact package commands ran and their outcomes;
- runtime receipt: whether pre-start checks passed;
- serving receipt: whether the live endpoint satisfied the frozen deployment;
- scientific release evidence: whether the experiment may make a claim.

No later receipt may rewrite an earlier fact or silently promote an earlier
receipt into a stronger certificate.

## Next implementation sequence

The next work is to close the capability groups and resolver evidence in this
order:

1. extend the snapshot through existing `resource/compute`,
   `environment/python`, `model/asset` and server-resource ports, keeping
   qualification as the join and interpretation module; the current slice has
   already closed host execution, GPU identity/fabric, local storage and model
   artifact-size observations;
2. add bounded dependency-closure evidence so candidate versions and their
   transitive requirements are selected by the exact environment rather than
   by a blind newest-version rule; the current probe has already closed the
   wheel/Python-ABI/platform-tag portion without artifact downloads;
3. bind the successful pre-start receipt into the existing `model/serving`
   live-readiness protocol without duplicating serving qualification semantics;
4. expose one management operation that can inspect, explain, materialize and
   verify a deployment while retaining every intermediate digest and rejection
   cause;
5. run the full regression only on the Ubuntu server, then perform a deliberate
   small-scale materialization before any complete SEM experiment.

This sequence improves the deployment system itself. It does not alter the
SEM memory method, weaken a scientific gate, or use a lower-quality backend as
an escape route.
