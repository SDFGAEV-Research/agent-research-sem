# Round 125 — paired workload identity repair and server smoke evidence

## Root cause found by execution

The first current-code paired Minecraft smoke completed both control and
`seed_x_v018` candidate branches, but its comparability proof was invalid. The
Paper composition had encoded `role` and `branch_id` into `workload_id`, so the
two branches represented the same task under different workload identities.
This was an experiment-boundary defect, not a Minecraft or memory-method
failure.

## Structural repair

The workload identity is now run-scoped and shared by both paired branches:

```text
workload_id = sem-paper:paired:<run_id>
branch_id   = <run_id>:control | <run_id>:candidate
```

The branch id remains the isolation identity. The shared workload id now
correctly expresses that the source cut, task manifest and environment
generation are being compared as one workload.

## Server evidence

- Commit `29056fe`: focused Paper-1/Minecraft/server regression **37 passed**.
- Commit `29056fe`: paired scripted smoke completed on Ubuntu with
  `scientific_claim=false` and `comparability.valid=true`.
- The smoke wrote event, metric, method-observation, result and branch
  artifacts; `failures.jsonl` was absent.
- Commit `f058bfd`: added the managed SGLang deployment declaration for the
  Paper-1 Qwen3.6 planner, assigned to GPUs `0,1,3,4`; the occupied GPU `2`
  is not used.
- The deployment working directory was corrected to the exact path returned by
  the platform workspace authority after a server-side composition check.

This smoke is plumbing evidence only. It is not a model-backed scientific
result and does not support a method claim.

## Current baseline gate

The exact Qwen3.6-35B-A3B server asset was found incomplete (one weight shard
in the target directory). The platform-managed resumable fetch is running in
the persistent `sem-paper-model-fetch` session through the non-Xet HTTP path
after the initial Xet CAS route returned 401. Model registration, service
readiness, unmodified baseline, small model-backed smoke and full experiment
remain gated on a complete verified asset receipt.
