# Open-Model Candidate Matrix — 2026-08 planning basis

## Recommended qualification order

1. **Qwen3.8-27B** — latest high-capability candidate and independent
   qualification track.
   - The official Qwen release record lists the open-weight release on
     2026-08-14. The model is a dense native vision-language model with
     262,144 native context and an official SGLang serving path.
   - Its official model card reports major gains over Qwen3.6-27B on agentic
     coding, multimodal agent and embodied-intelligence measurements. Those
     tables do **not** directly compare against Qwen3.6-35B-A3B, so they are
     a candidate signal, not a paper result.
   - It is downloaded into an independent asset path and must use an
     independent runtime identity. The current host has RTX 3090 GPUs, while
     the current SGLang Qwen3.8-27B recipe is validated on newer GPU classes;
     the 3090 path therefore requires explicit boot, parser, memory and
     recovery qualification before promotion.

2. **Qwen3.6-35B-A3B** — first paper workhorse candidate.
   - Official Qwen release, Apache-2.0 open weights.
   - Official deployment examples support both SGLang and vLLM and show a 262,144-token serving configuration.
   - Small enough relative to frontier MoE models to be the first candidate for a practical multi-role research stack.

2. **DeepSeek-V4-Flash** — second large-model candidate.
   - Official DeepSeek V4 preview family; Flash is the smaller V4 variant and targets million-token context.
   - SGLang added production-oriented DeepSeek-V4 support, including multiple parallelism modes and dedicated kernels.
   - Qualify separately; never use it as an automatic fallback for a Qwen confirmatory run.

3. **Qwen3.5-397B-A17B** — high-capability large Qwen candidate.
   - Official model card reports 397B total / 17B activated parameters and 262,144 native context, extensible beyond that under supported deployment.
   - Use only if host inventory and workload qualification justify the larger footprint.

## Serving engine

Start qualification with **SGLang** because the existing project already has SGLang-oriented model-stack templates and the framework currently emphasizes production serving, model coverage and large-scale reliability. Pin an exact stable release/container digest; do not run `latest` in scientific work.

Also keep a vLLM profile for A/B engine qualification if the same model/revision/precision/context can be served identically. Engine choice is infrastructure, but it must be frozen within a confirmatory run.

## Selection rule

Do not pick a model from public benchmark tables alone. Select the model stack that:

- passes every critical Planner/Semantic/Meta prompt contract;
- preserves tool/reasoning parser semantics;
- survives hard-kill/restart and exact-resume tests;
- meets workload-specific latency/throughput targets;
- has stable memory usage under the actual context-length distribution;
- produces zero unexplained model-identity or tokenizer drift.
