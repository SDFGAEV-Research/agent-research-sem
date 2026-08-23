# Round 47 — Managed environment materialization and adaptive AI-infrastructure boundary

Date: 2026-08-23

## Purpose

This round records the first complete qualification/materialization failure
loop for an open-source serving backend. The platform must determine
deployment prerequisites from observed host, interpreter, GPU, model and
package-index facts rather than from manually chosen version strings. This
round records the actual installation result, the runtime root cause, and the
resolver corrections required before the paper environment can be used.

## Current evidence before installation

The server-side qualification path has already observed the deployment-relevant
closure for the selected host and target Python environment:

```text
OS / distribution / kernel / libc / limits / container
  -> NVIDIA driver / CUDA API / NVRTC / NVML
  -> GPU identity / memory / SM / PCI-NUMA / multi-GPU topology
  -> model configuration / shards / storage
  -> target Python ABI / pip / venv / Torch-CUDA / NCCL
  -> compatible binary wheels and PEP 658 metadata
  -> recursive dependency closure and graph-wide constraint reconciliation
  -> immutable backend/package plan
```

The first verified plan selected `vllm==0.27.1` for the current host and
rejected the observed SGLang candidate with explicit CUDA-kernel and SM86
coverage evidence. That plan contained 162 closure nodes and 162 frozen
install packages, including the backend root. It was later shown to be
incorrect for the target environment because its closure selected Torch
`2.13.0` while the target Python already contained Torch `2.11.0+cu130`.

The historical qualification evidence used for the first materialization is:

- facts digest:
  `33fd6893fc321150d99d8275ed205d0c7b25e2f1e5ac0c482df48de88df9edc8`;
- plan digest:
  `24eca0f99856d8b79f420f11abb9647a41d7544e6f4292fe8e6b334d6c26526a`;
- selected backend: vLLM `0.27.1`;
- qualification budget: 90 seconds;
- target server: managed Ubuntu `sem-ubuntu` profile.

## Registry state

The platform environment registry contains four ready records. Two legacy
records were repaired through the explicit `env migrate-legacy` operation;
their existing prefixes and packages were not replaced. The new installation
does not reuse either SGLang prefix.

A dedicated managed environment was created for the selected plan:

```text
environment id: qwen36-vllm-v0271-cu130
backend:       venv
python:        /data/research-platform/envs/qwen36-vllm-v0271-cu130/bin/python
state:         ready
ownership:     managed
tags:          paper1, qualification, qwen36, serving, vllm
```

Its immutable specification digest is
`e90b27944f04891c17a7b059018809a0a02ca3d210b8565e95dcab403bd73bb0`.

## Materialization result and runtime root cause

The frozen plan was applied through the platform's environment/package port,
not by an ad-hoc shell installation. The application operation was:

```text
operation: srv-op-0212a6ac31454a4cb2753898875a8701
plan:      24eca0f99856d8b79f420f11abb9647a41d7544e6f4292fe8e6b334d6c26526a
target:    qwen36-vllm-v0271-cu130
```

The installer used the exact frozen package tuple with
`--no-deps --only-binary=:all:` and the platform pip cache. The application
receipt closed successfully after approximately 1430 seconds:

- application digest:
  `c49abf62f31bd138548baaef2fefd1202115bc832dc77c6b5d6ba77dc00eb7e8`;
- package installation return code: `0`;
- `pip check` return code: `0`;
- no service was started and no model request was sent.

The subsequent runtime qualification failed before serving. The decisive
root cause was:

```text
OSError: libcudart.so.13: cannot open shared object file
ldd libtorch_global_deps.so -> libcudart.so.13 => not found
```

The target environment contained CUDA 13 cuDNN/cuBLAS components but no
`libcudart.so.13` in the managed environment or system library search path.
This is a native-runtime completeness failure, not a model or SEM failure.
The environment is retained as forensic evidence and must not be reused as a
serving certificate.

The independent SGLang environment remains the valid observation anchor:
Torch `2.11.0+cu130`, CUDA runtime `13.0`, eight visible GPUs, and successful
`torch.cuda.is_available()` probing. It was not modified by this round.

## Resolver corrections and current qualification

The failure loop also found a resolver correctness bug: the initial probe used
public PyPI's newest Torch instead of deriving package indexes from the target
Python's pip configuration and respecting the installed Torch runtime. The
resolver now:

1. derives the target pip primary/extra indexes and records them in the
   capability evidence;
2. uses a verified same-version public-index metadata twin only when a mirror
   omits PEP 658 metadata, while keeping the mirror as the install source;
3. constrains the dependency graph to the exact observed Torch version;
4. screens backend root versions against those direct runtime requirements
   before running recursive closure resolution; and
5. records every root-screen rejection and closure failure in the plan.

The latest real vLLM qualification therefore rejects the backend correctly:

- facts digest:
  `0e2ddc403252e31fc113a25d0bdcaac559811f02438f1eadd971a823f76bde69`;
- plan digest:
  `09afa32a2e8e8abc7f09522dfdea020b6840ddaea373016d81b7707af502e011`;
- root versions screened: `24`;
- root-compatible recursive closures attempted: `11`;
- result: no complete vLLM closure satisfying Torch `2.11.0`;
- elapsed time: `291.58` seconds, after sharing index pages and metadata
  through an ephemeral per-qualification cache. The previous uncached run
  took `1002.69` seconds; the decision and rejection evidence were unchanged.

The result is semantically correct and the dominant repeated-fetch cost has
been removed. The remaining cost is recursive closure proof for 11 distinct
root-compatible candidates. Further optimization must preserve complete
per-candidate failure evidence and may not skip closure proof or choose an
unqualified fallback.

## Automatic environment-adaptation design boundary

The intended reusable system is a three-stage composition, not a collection
of backend-specific scripts:

```text
Environment Observation
  -> immutable Capability Snapshot
  -> Candidate / dependency / launch Plan
  -> frozen Materialization + Runtime Qualification
```

The observation stage owns facts only. The resolver interprets those facts and
produces exact versions, indexes, wheel tags, native-extension coverage,
backend choices and launch prerequisites. The materializer executes only the
frozen plan. The runtime verifier then proves imports, CUDA/device access,
parallelism, model-config readability and endpoint readiness through the
owning serving system.

The following must be detected or explicitly recorded as unavailable before a
plan is accepted:

- OS distribution, kernel, libc, CPU ISA/count, RAM, limits and container
  identity;
- NVIDIA driver, CUDA API/toolkit, NVRTC/NVML, GPU UUID/name/memory/SM,
  PCI-NUMA, MIG and multi-GPU communication facts;
- Python interpreter, ABI, installer, environment backend, installed native
  packages, Torch-CUDA and NCCL facts;
- model revision/digest, architecture, dtype, context, tokenizer/processors,
  shards, storage capacity and filesystem permissions;
- package-index artifacts, Python/ABI/platform tags, CUDA channel, hashes,
  native-extension architectures, recursive dependency metadata and
  graph-wide constraints;
- backend model-family support, precision/parallelism requirements,
  launch contract and known incompatibility evidence;
- cache, network/proxy and filesystem throughput facts when they affect the
  requested materialization or serving run.

The system must never treat “latest”, “pip accepted it”, or “the directory
exists” as a compatibility certificate. A missing fact remains an explicit
unknown or rejection. A rejected backend is not converted into a lower-quality
fallback merely to make the command complete.

## Verification boundary

This round currently proves:

- the registry-backed environment identity can be selected by ID;
- the first vLLM plan can be bound to a new isolated managed prefix;
- the exact frozen package closure can be materialized through the package
  authority and passes `pip check`;
- pre-start runtime qualification detects the missing CUDA runtime library;
- the resolver rejects the later vLLM candidates when the target Torch and
  complete closure cannot be satisfied;
- existing SGLang environments remain untouched.

This round does not yet prove:

- vLLM import or CUDA extension loading;
- model loading, endpoint readiness or serving stability;
- SEM/Minecraft baseline, ablation or full scientific results.

The next transition is allowed only after the application receipt is complete:

```text
application receipt
  -> pre-start runtime qualification
  -> serving readiness qualification
  -> paper baseline smoke run
  -> small controlled experiment
  -> complete experiment
```

Any failure is to be diagnosed from its receipt, command output and immutable
input digests. The repair target is the violated contract or root cause; no
silent downgrade, bypass, retry loop without evidence, or manual package
substitution is acceptable.
