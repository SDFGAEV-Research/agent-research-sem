# Round 40 — AI deployment environment qualification foundation

Date: 2026-08-23

## Purpose

Record the real server qualification state before changing the serving stack,
and define the next platform slice: detect the host/runtime capability closure,
resolve an exact backend/package plan, then let the existing environment and
deployment authorities materialize and qualify that plan.

## Current server evidence

- The SEM server is an Ubuntu 22.04 host with eight NVIDIA GeForce RTX 3090
  devices, 24 GiB per device, driver `580.173.02`, compute capability `8.6`
  (SM86), and system CUDA `12.4`.
- The registered Qwen3.5-35B-A3B asset is complete: 26 safetensor shards,
  approximately 80 GiB, with model type `qwen3_5_moe`.
- The original `qwen36-sglang` environment is SGLang 0.5.10 / Torch 2.9.1 /
  Transformers 5.3.0. A real request against that service produced the
  repeated `!` degeneration and the service was stopped. This is a model-stack
  qualification failure, not evidence that the SEM planner or experiment is
  correct.
- A separate SGLang 0.5.17 candidate was assembled with the official
  FlashInfer 0.6.15.post1 Python/cubin/JIT-cache trio. Its package consistency
  check and FlashInfer import passed, but every tested official SGLang kernel
  wheel exposed only an SM100 `common_ops` library on this host. Import then
  failed before serving because the host is SM86 (and one trial also exposed a
  Torch extension-symbol mismatch). No scientific run used this candidate.
- The server package index currently exposes vLLM 0.27.1. The first clean vLLM
  environment creation attempt used `/usr/bin/python3` and failed at the
  environment layer because Ubuntu's `ensurepip`/`python3-venv` prerequisite is
  absent. Independent observation confirmed that the target prefix was
  partially materialized with an executable and `pyvenv.cfg`; the operation
  ledger was reconciled as `effect_confirmed`. The partial prefix is not yet a
  qualified vLLM environment.
- The model request protocol failure was separately localized: the planner
  sent only a system message, while the deployed Qwen endpoint requires a user
  turn. The planner now emits the compiled prompt as a user message. A later
  200 response still returned a non-JSON abort (`!!`), so that response remains
  a failed model-stack qualification witness rather than a successful run.
- The first baseline run did not make a model request. Its result is therefore
  not scientific model-backed evidence; the result claim gate now requires a
  real model request, paired control/candidate memory queries, and a valid
  comparison before it can claim scientific evidence.

## Root cause and architecture decision

The previous process required a human to manually correlate OS, CUDA, GPU
architecture, Python bootstrap support, framework wheels, kernel extensions,
model support, and launch arguments. That is not a reliable deployment
interface: package version alone is insufficient, and a package can install
successfully while its architecture-specific extension cannot load.

The platform will therefore add a deployment-qualification module under the
existing `model/qualification` authority. `model/deployment` consumes only its
narrow qualification port. It has three explicit seams:

1. a read-only capability probe adapter, owned by the host/environment
   composition, producing immutable OS, driver, CUDA, GPU, Python, package
   index, filesystem and prerequisite facts;
2. a pure compatibility resolver, selected at composition time, producing a
   digestable `DeploymentQualificationPlan` with candidate backends, exact
   package sources, rejected candidates and actionable prerequisite causes;
3. the existing Python-environment and model-deployment ports, which apply the
   plan and run import/extension/readiness qualification. They remain the
   authorities for materialization and live process state.

The resolver never installs a package, probes through a global service locator,
or silently falls back to a lower-quality engine. An unsupported candidate is
reported with the exact fact and source rule that rejected it. The plan is
the composition-time artifact; runtime serving receives only the already
bound environment/deployment ports. Logs, metrics and qualification evidence
continue through the independent observation plane.

## Server verification result

The typed facts/plan contracts, resolver and `research-platform-manage`
qualification command are now implemented in the existing `model/qualification`
node. After moving process execution behind the platform-wide local command
port, the server architecture gate passed with `ARCHITECTURE_GATE_PASS`, and
the focused server regression passed **29 tests**. The real qualification
command produced facts digest
`4316f0fc7e7ad55fc59051fede850223374b3afb65a09abdaa964ff2ce392888` and plan
digest `00e4e6bf3cb66a0ce362a2539c174a3565924b84a6b899c4a7b55878cb3d40a3`.
It resolved:

- SGLang 0.5.18 plus `sglang-kernel 0.4.6.post1+cu130`: rejected because the
  selected environment exposes `sm90,sm100` kernel libraries while the host
  requires `sm86`.
- vLLM 0.27.1 from PyPI: selected as the next materialization candidate, not
  yet a runtime qualification certificate.

An intermediate false-negative was found and fixed at the CLI seam: resolving
the venv interpreter path followed `bin/python` to `/usr/bin/python3` and
discarded the environment's site-packages. The regression now preserves the
environment entrypoint, and the same server command reports the actual
`sm90,sm100` evidence. The same run is now free of the earlier `runpy` warning;
the management package no longer imports its CLI eagerly. The qualification
probe also no longer owns a direct `subprocess.run` call: it uses the platform
process port, so the architecture gate and the runtime ownership model agree.

## Persistent evidence slice

The qualification composition now publishes a checksummed record under the
configured state directory at `model/qualification/<plan_digest>.json`. The
record joins the exact request, all captured host/runtime/model/package facts,
all backend candidates and the plan digest. `deployment qualification
<plan_digest>` reads the record back and rejects checksum or internal digest
mismatches. The server regression covers round-trip and tamper detection.

The latest live record is plan `c0b4fad8640f44c4ff7075f8ef0ee2496e4a15083f5a388e6f9e68d2c5b6bebc`,
facts `cb7df139c9ea1d380b672d74c9d4b8251c330c091a17946689c7636b54875ab9`,
record `f795f1d91caa74864b396fce8f9682c6193dba23ce0b6841b693830d38e2ff84`.
The server read-back verified schema `model-deployment-qualification-evidence.v1`,
two candidates and selected backend `vllm`.

The post-change server checks are: `ARCHITECTURE_GATE_PASS`, **31 focused
tests**, and `NO_DEGRADATION_AUDIT_PASS`.

The next step is to let the existing `environment/python` authority apply only
that frozen plan. No package installation is considered successful until
`pip check`, framework import, architecture-specific extension import and
endpoint readiness are all recorded.
