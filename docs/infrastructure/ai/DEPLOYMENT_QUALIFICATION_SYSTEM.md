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

The first vertical slice is implemented under `model/qualification` and is
composed through the existing platform management root:

- the read-only probe captures operating-system identity, NVIDIA driver/CUDA
  facts, GPU inventory and compute capability, Python/pip/ensurepip/venv and
  Torch facts, model `config.json`, package-index versions and observed
  SGLang kernel architectures;
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
Failures persist a receipt and re-raise the original root exception.

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
  `516d70a0b1bbf2eb018525a4a712f15add77e35a3665fe90c016f86db01bdf16`;
- plan digest:
  `fa5b8504116429691dfad5976d0617dadc5898d8d20eadc2f55180a77c6f2987`;
- evidence record digest:
  `5d2186c062915758c5da684438f812291d2d9c00173cabcd83dd17134dc713c`.

Server validation for the current slice is **37 focused tests**,
`ARCHITECTURE_GATE_PASS`, and `NO_DEGRADATION_AUDIT_PASS`. The real Qwen
environment has not been passed to the mutating apply operation, no vLLM
service has been started from this plan, and no scientific SEM result is
claimed from it.

## Capability closure to complete

The current facts are the foundation, not the final closure. The completed
system must capture or explicitly mark unavailable every deployment-relevant
fact in the following typed groups:

| Fact group | Required evidence | Owning authority |
| --- | --- | --- |
| Host execution | OS distribution/version, kernel, libc/glibc, CPU ISA/count, RAM, limits, container/runtime identity | `resource` and platform host adapters |
| GPU/CUDA | GPU UUID/name/memory/SM/PCI identity, driver, driver CUDA API, toolkit, NVRTC, CUDA runtime libraries, MIG state | `resource/compute` |
| Multi-GPU fabric | device topology, peer access, PCI/NVLink links, NCCL identity and usable communication path | `resource/compute` plus runtime adapters |
| Storage/network | model-path filesystem, free/required capacity, permissions, mount identity, local cache, network/proxy reachability and bandwidth evidence | `resource` and `runtime/server` |
| Python runtime | exact interpreter identity, Python ABI, pip/installer, venv/conda/mamba backend, site-packages, Torch/CUDA ABI, installed native extensions | `environment/python` |
| Model artifact | revision/digest, config, architecture, dtype, context, tokenizer/processor, shard completeness, required disk and model-specific support | `model/asset` and `model/stack` |
| Package candidates | exact version, wheel tags, Python ABI, CUDA channel, native extension architectures, dependency closure and source digest | `model/qualification` adapters |
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
   qualification as the join and interpretation module;
2. add wheel/native-extension and dependency-closure evidence so candidate
   versions are selected by the exact environment rather than by a blind
   newest-version rule;
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

