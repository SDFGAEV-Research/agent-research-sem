# Model Serving OS

## Principle

A model server is a managed, evidence-producing state machine. It is not a shell command.

## Model Run state machine

```text
NEW → INVENTORY → PREPARE → LOAD → WARMUP → READY → RUNNING
                                                  ↓
                                             DRAINING
                                                  ↓
                                              STOPPING → STOPPED

Any active phase → FAILED / INTERRUPTED → RECOVERY_REQUIRED
```

## Exact recovery

One-click recovery means one command can mechanically execute this plan:

1. verify artifact hashes;
2. verify log/transcript chains;
3. verify exact model identity;
4. re-inventory the host;
5. reconcile old PID/process-group identity;
6. restart the exact same model stack;
7. wait for HTTP + local supervisor readiness;
8. run the exact role canary suite;
9. restore the latest valid study/checkpoint cut;
10. resume unfinished work only.

It does **not** mean choosing a smaller model, lower precision, shorter context, another engine, another prompt, or another model revision.

## Serving-engine policy

Use a model-stack catalog. Each stack freezes:

- model ID and exact revision;
- tokenizer revision;
- engine and exact version/container digest;
- dtype/quantization;
- context length;
- tensor/expert/data/pipeline parallel settings;
- attention/cache backend;
- reasoning/tool-call parser;
- scheduler and batching parameters;
- environment/runtime dependencies.

### Current model candidates

- **Primary default candidate: Qwen3.6-35B-A3B + SGLang.** It is compact enough to be a realistic research workhorse while retaining strong agentic/coding ability. The exact deployment still depends on target GPU inventory and qualification.
- **Large Qwen candidate: Qwen3.5-397B-A17B + SGLang.** Use only if the host has enough GPUs/memory and it wins the role qualification on the actual workload.
- **Alternative large candidate: DeepSeek-V4-Flash + SGLang.** Treat it as a separately qualified model stack, not a fallback inside the same confirmatory run.

Do not choose the final stack from benchmark headlines alone. Qualification should run the actual Planner/Semantic/Meta contract suite and workload-shaped throughput tests.

## Performance qualification

Measure at minimum:

- cold/warm load time
- TTFT p50/p90/p99
- TPOT p50/p90/p99
- input/output tokens/s
- request concurrency vs latency curve
- scheduler queue delay
- continuous-batch size
- prefix/radix-cache hit ratio
- KV cache occupancy
- preemption count
- GPU memory/utilization/power/temp
- NCCL/collective time where available
- CPU/NUMA locality
- host memory and I/O pressure
- HTTP error and contract-error rate
- exact-token correctness canaries

The performance winner is the best stack that passes correctness and role contract qualification, not the fastest degraded configuration.
