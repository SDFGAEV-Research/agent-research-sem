# SEM Paper Round 133 — variant binding and Core-6 fail-closed repair

Date: 2026-08-25

This round records a root-cause repair after the architecture snapshot was
committed. It does not claim a completed Minecraft experiment.

## Root causes

- `StudyMatrixExecutor` already passed the compiled `VariantBinding` through
  `MinecraftPairedBranchRunner`, but `MinecraftWorkloadBranchExecutor` dropped
  it before opening the workload binding. A Core-6 arm could therefore fail at
  runtime or fall back to the wrong method endpoint.
- `compose_sem_paper` implicitly reused the generic candidate materializer for
  both `RuleBasedEvolver` and `SelfEvolve`. That made two scientific arms share
  one implementation while their provider identities remained different.
- The current repository still has no genuine independent RuleBased provider
  bound to the final SEM composition. Treating the existing SelfEvolve
  materializer as RuleBased would invalidate the comparison.

## Repairs

- `VariantBinding` is now part of the Minecraft workload binding factory seam
  and is forwarded into the concrete `open` call.
- Project composition now requires explicit RuleBased and SelfEvolve
  materializers; it no longer derives either one from the generic fallback.
- `SemPaperVariantMethodEndpointFactory` rejects identical provider object
  identities, preventing a mislabeled arm from being composed.
- The Minecraft Core-6 runtime guard fails before host startup when the three
  required providers are not composed. This is an intentional scientific
  safety boundary, not a degraded execution path.

## Evidence boundary

- Static source inspection and diff checks are the validation performed in this
