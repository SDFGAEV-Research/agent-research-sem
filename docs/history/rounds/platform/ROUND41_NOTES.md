# Round 41 — Deployment qualification system status and closure

Date: 2026-08-23

## Record purpose

Freeze the current state before extending automatic open-source model
deployment management. This round records what is already real, what remains
unproven, and the system boundary for the next implementation slices.

## Current state

The platform already contains a `model/qualification` vertical slice:

1. read-only host/runtime/model/package observation;
2. pure backend candidate resolution;
3. checksummed qualification evidence keyed by `plan_digest`;
4. frozen-plan package materialization through `environment/python`;
5. persisted application receipts and mandatory `pip check`;
6. bounded post-materialization backend, CUDA/device and model-config checks.

The current server evidence is the eight-RTX-3090 Ubuntu host. The latest
qualification record reports the expanded v2 capability snapshot:

- SGLang 0.5.18 plus `sglang-kernel 0.4.6.post1+cu130` rejected because the
  observed native kernels expose SM90/SM100 while the host is SM86;
- vLLM 0.27.1 selected as the next exact package candidate;
- host execution, libc/resource limits, PCI/NUMA/power GPU identity, cleaned
  eight-GPU topology, target-Python NCCL, local model-path storage and
  artifact file/shard statistics are now observed or explicitly marked
  unavailable;
- facts digest
  `4501722a1290b55757ed0ca2ef8c3dfca76a43d4028d5e815e032a6fb30dd8b5`;
- plan digest
  `695d45feabebfc61a621541485425b62775aa7d200de478521506f6fbffd4084`;
- record digest
  `cc73ba5224be7138559b2d63f7f740a0c3cdd8d96d25da2f84136ed88866c114`.

The server-validated regression is **37 focused tests** with
`ARCHITECTURE_GATE_PASS` and `NO_DEGRADATION_AUDIT_PASS`.

## Explicit non-claims

- The real Qwen environment has not been mutated by the frozen-plan apply
  operation.
- No vLLM service has been started from this plan.
- Pre-start runtime qualification is not live endpoint qualification.
- No model-backed SEM scientific result is claimed from this slice.
- The current fact set is not yet the complete deployment closure: package
  wheel/native-extension/dependency closure, network reachability, live serving
  readiness and model-specific backend support still need typed evidence.

The first attempt through the installed `research-platform-manage` executable
failed before touching the remote environment because that executable was
stale and did not expose `deployment qualify`. The root cause was repaired by
installing the current checkout editable into the server management
environment. The official entrypoint was then re-run successfully; no
compatibility bypass or lower-quality fallback was introduced.

## Architecture decision

Automatic compatibility management is a platform system, not a collection of
paper-specific scripts. Existing authorities remain owners of their facts:
`resource/compute` owns physical GPU and fabric facts, `environment/python`
owns interpreter/package facts, `model/asset` and `model/stack` own artifact
facts, `model/qualification` joins and interprets them, `model/deployment`
owns materialization, and `model/serving` owns live service proof.

The resolver must produce an exact, explainable plan from the observed closure.
It may reject a candidate when evidence is missing or incompatible; it may not
silently choose an unverified fallback, downgrade requirements, or treat an
index's newest release as sufficient proof.

The full contract is recorded in
`docs/infrastructure/ai/DEPLOYMENT_QUALIFICATION_SYSTEM.md`.

## Next slice

Close the remaining package/network/backend capability groups through existing
platform seams, add wheel/native-extension/dependency evidence to candidate
resolution, and bridge successful pre-start receipts into the existing serving
readiness protocol.
All regressions remain server-only, and all real environment mutations require
an explicit frozen plan plus durable receipts.
