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
qualification record reports:

- SGLang 0.5.18 plus `sglang-kernel 0.4.6.post1+cu130` rejected because the
  observed native kernels expose SM90/SM100 while the host is SM86;
- vLLM 0.27.1 selected as the next exact package candidate;
- facts digest
  `516d70a0b1bbf2eb018525a4a712f15add77e35a3665fe90c016f86db01bdf16`;
- plan digest
  `fa5b8504116429691dfad5976d0617dadc5898d8d20eadc2f55180a77c6f2987`;
- record digest
  `5d2186c062915758c5da684438f812291d2d9c00173cabcd83dd17134dc713c`.

The server-validated regression is **37 focused tests** with
`ARCHITECTURE_GATE_PASS` and `NO_DEGRADATION_AUDIT_PASS`.

## Explicit non-claims

- The real Qwen environment has not been mutated by the frozen-plan apply
  operation.
- No vLLM service has been started from this plan.
- Pre-start runtime qualification is not live endpoint qualification.
- No model-backed SEM scientific result is claimed from this slice.
- The current fact set is not yet the complete host deployment closure: host
  libc/resources, multi-GPU fabric/NCCL, storage/network, wheel metadata and
  model-specific backend support still need typed evidence.

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

Close the remaining capability groups through existing platform seams, add
wheel/native-extension/dependency evidence to candidate resolution, and bridge
successful pre-start receipts into the existing serving readiness protocol.
All regressions remain server-only, and all real environment mutations require
an explicit frozen plan plus durable receipts.

