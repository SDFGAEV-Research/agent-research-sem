# Open-Model Candidate Matrix — 2026-08 planning basis

## Recommended qualification order

1. **Qwen3.8-27B** — primary SEM qualification track.
   - Frozen asset revision for the active track: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
   - Server-1 acquisition is complete (~52 GB, zero incomplete files).
   - vLLM 0.27.1 has already demonstrated TP=2, BF16 and full 262,144-token context boot on 2× RTX 5000 Ada; this is capability evidence, not yet a published scientific qualification closure.
   - TP=3 is structurally invalid for this model; placement qualification must respect the model head divisibility constraints rather than trying arbitrary GPU counts.
   - The intended SEM role bundle is planner, semantic, meta and diagnostic, with independent prompt/request identities.

2. **Qwen3.6-35B-A3B** — first paper workhorse candidate.
   - Official Qwen release, Apache-2.0 open weights.
   - Official deployment examples support both SGLang and vLLM and show a 262,144-token serving configuration.
   - Small enough relative to frontier MoE models to be the first candidate for a practical multi-role research stack.

3. **DeepSeek-V4-Flash** — second large-model candidate.
   - Official DeepSeek V4 preview family; Flash is the smaller V4 variant and targets million-token context.
   - SGLang added production-oriented DeepSeek-V4 support, including multiple parallelism modes and dedicated kernels.
   - Qualify separately; never use it as an automatic fallback for a Qwen confirmatory run.

4. **Qwen3.5-397B-A17B** — high-capability large Qwen candidate.
   - Official model card reports 397B total / 17B activated parameters and 262,144 native context, extensible beyond that under supported deployment.
   - Use only if host inventory and workload qualification justify the larger footprint.

## Serving engine

For the active Qwen3.8 track, start from the actually verified **vLLM 0.27.1** container because it has already completed a full-context TP2 boot on the managed Ada host. Reconcile readiness, run role/parser/recovery qualification and freeze the exact container digest before promotion.

SGLang remains a separately qualified engine candidate; do not switch engines inside one confirmatory run and do not treat engine substitution as fallback. The winning engine is the one that passes the exact role contracts and workload-shaped performance gates for the frozen model revision.

## Selection rule

Do not pick a model from public benchmark tables alone. Select the model stack that:

- passes every critical Planner/Semantic/Meta prompt contract;
- preserves tool/reasoning parser semantics;
- survives hard-kill/restart and exact-resume tests;
- meets workload-specific latency/throughput targets;
- has stable memory usage under the actual context-length distribution;
- produces zero unexplained model-identity or tokenizer drift.
