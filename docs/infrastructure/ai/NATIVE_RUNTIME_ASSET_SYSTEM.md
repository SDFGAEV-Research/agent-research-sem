# Native Runtime Asset System

Date: 2026-08-23

This document defines the platform boundary for native runtime assets required
by open-source model serving. It is a child of `model/qualification` and
`environment/python`; it is not a second package registry and it does not
allow a Python package name to stand in for a verified shared library.

## Problem being closed

The serving stack is a closure of more than Python distributions:

```text
backend package
  -> Python extension modules
  -> ELF/DSO dependencies
  -> CUDA runtime / BLAS / NCCL / NVRTC
  -> driver, GPU architecture and multi-GPU fabric
```

An installation can pass `pip check` while the first import fails with a
missing `libcudart.so.<major>`. Therefore package installation, native loading,
CUDA device access and serving readiness are separate certificates. None may
promote another one implicitly.

## Ownership and composition

```text
resource/compute
  ├─ host linker and system CUDA observations
  ├─ driver/toolkit/NVML/NVRTC/NCCL observations
  └─ GPU architecture and fabric observations

environment/python
  ├─ interpreter ABI and site-packages
  ├─ installed native-library observations
  └─ Python package/artifact installation port

model/qualification
  ├─ native requirement extraction from backend and Torch facts
  ├─ provider candidate resolution
  └─ immutable qualification evidence and frozen plan

environment/system (provider boundary)
  └─ future OS/toolchain/native-asset materialization
```

`model/qualification` joins facts and interprets compatibility. It does not
own CUDA, Python, operating-system or package-manager state. A provider must
declare what it supplies, how it was observed, which target it affects and
how its materialization is verified.

## Native asset closure

For a target runtime `r`, the required native closure is a typed relation:

```text
NativeRequirement
  = (library name, ABI/major, architecture, provider kind, consumer)

NativeObservation
  = (library name, resolved path, provider kind, ABI, architecture, digest,
     linker visibility, evidence/error)

NativeProviderCandidate
  = (provider identity, materialization actions, artifacts, verification,
     ownership and rollback contract)
```

The resolver may accept a requirement only when one of these is true:

1. the target Python environment already exposes the required library and the
   dynamic loader can resolve it;
2. the host/system provider exposes the required ABI and architecture;
3. a declared native artifact has a platform-specific binary artifact and its
   contents/metadata prove that it supplies the requirement; or
4. a declared operating-system/toolchain provider has an exact package and
   post-materialization verification contract.

The fourth provider kind is intentionally separate from `pip`. A generic
`py3-none-any` wheel, a package name containing `cuda`, a successful download,
or a `pip check` result is not proof of a native provider.

## Qualification data flow

```text
host + linker + driver + GPU fabric
          │
target Python + Torch + native site-packages
          │
backend wheel + recursive dependency metadata
          v
native requirement set
          │
provider candidates with binary/OS evidence
          v
joint backend/package/native plan
          │
exact Python or system materialization
          v
DSO resolution + import + CUDA + NCCL + serving readiness receipts
```

The backend plan and native provider plan are one immutable qualification
decision. A backend cannot be accepted with a complete Python dependency graph
while leaving a required native library as an unproven future action.

## Current implementation

The current server-validated slice now:

- records native CUDA/BLAS/NCCL library basenames discovered inside the target
  Python environment;
- joins those observations with system CUDA runtime-library evidence;
- derives the CUDA-major runtime requirement from the target Torch/driver facts;
- inspects the configured package index for a matching runtime candidate; and
- rejects a candidate when the only artifact is platform-independent and does
  not prove that it contains the required native library.

The latest failed-vLLM qualification on `sem-ubuntu` recorded:

```text
facts: de60fd26ac5fb1fdb09aceac2b8dfc32bd5be85dff8283814740f19bb826e961
evidence: native-cuda-runtime:libcudart.so.13:unproven:artifact-not-platform-specific
operation: srv-op-7a2de1003fdf44a2942ebbfcab07c9ff
decision: rejected
```

The mirror exposed `nvidia-cuda-runtime-cu13==0.0.0a0` only as an
`any`-platform placeholder. The resolver therefore did not add it to the
frozen install plan. This is a deliberate fail-closed result: the platform
has detected the missing native asset, but has not yet claimed that it can
repair CUDA 13 automatically.

The independent SGLang environment remains an observation anchor because its
target runtime exposes CUDA 13 and `torch.cuda.is_available()` succeeds. It
does not turn the failed vLLM environment into a serving certificate.

The subsequent host inventory corrected the provider-family mapping. The
healthy SGLang environment exposes the real CUDA 13 NVIDIA package family:

```text
nvidia-cuda-runtime==13.0.96
nvidia-cuda-nvrtc==13.0.88
nvidia-cublas==13.1.0.3
nvidia-nccl-cu13==2.28.9
```

CUDA 13 therefore prefers the unsuffixed `nvidia-cuda-runtime` candidate and
uses `nvidia-cuda-runtime-cu13` only when that alternative is actually
observed on the configured index. The next real vLLM qualification planned
`nvidia-cuda-runtime==13.3.29` from a platform-specific wheel, with evidence:

```text
native-cuda-runtime:libcudart.so.13:planned:
https://pypi.tuna.tsinghua.edu.cn/simple:13.3.29
```

The backend was still rejected by its complete Torch/runtime closure, so no
provider was installed. Discovering a usable native provider does not override
an independent backend closure failure.

The recursive dependency closure now carries extras as part of the dependency
state. This matters because Torch's CUDA requirements are expressed through
`cuda-toolkit[cublas,cudart,cufft,cufile,cupti,curand,cusolver,cusparse,nvjitlink,nvrtc,nvtx]`.
The latest server qualification expanded the vLLM closure from 163 to 195
nodes; the native provider is visible in the same frozen candidate rather than
being reconstructed after installation.

## Required future provider work

The next implementation is a provider contract, not a fallback package:

1. represent system/toolkit/native artifacts as typed assets owned by the
   environment/resource systems;
2. probe linker visibility, `ldd`/ELF dependencies, ABI, architecture and
   provenance for each candidate;
3. resolve exact OS/toolchain materialization actions from the host profile,
   with an immutable receipt and post-install verification;
4. allow the qualification plan to contain both Python and native provider
   actions; and
5. reject the complete plan when either side is incomplete.

No OS mutation, CUDA replacement, engine downgrade or manual package
substitution is authorized by this document. Such an action must come from a
declared provider with a reversible operation receipt and root-cause evidence.

## Verification boundary

The native gate is not a serving or scientific result. The current server
regression has 24 focused tests, including acceptance of a proven
platform-specific native artifact and rejection of the placeholder wheel. No
vLLM service, Minecraft run or SEM scientific result has been started from
this slice.
