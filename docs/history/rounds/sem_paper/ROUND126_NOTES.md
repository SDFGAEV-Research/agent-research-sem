# Round 126 — Paper-1 model acquisition throughput and resumability

## Scope

This round is operational preparation for the server-side Paper-1 experiment.
It does not constitute a model-backed scientific result.

## Root cause and action

The platform-managed Hugging Face CLI invocation was healthy but used the CLI
default of eight download connections. The Qwen3.6-35B-A3B asset was already
partially present, so the safe action was to stop the fetch session gracefully,
verify that no downloader remained, and resume the exact same model, revision,
destination and cache with an explicit 32-worker download.

No model, revision, destination, or already downloaded shard was changed.

## Evidence

- The old session was stopped through the managed server connection.
- Independent observation confirmed the old session and downloader had exited
  before the optimized session was started.
- The optimized session was independently verified as the only downloader and
  exposed 26 active connections at the observation point.
- A short transfer probe measured approximately 90 MiB of additional partial
  shard data in 20 seconds after optimization, compared with approximately
  50 MiB in the corresponding pre-optimization probe.
- The server operation ledger was reconciled and currently has no pending
  uncertain operation.

## Current gate

The asset remains incomplete and unregistered. The model service is not
started. After the downloader exits, the next authoritative steps are:

1. verify all expected shards and absence of incomplete files;
2. register the asset through `research-platform-manage`;
3. register and start the declared SGLang deployment;
4. pass readiness and model-backed `t01_observe` smoke before the full paired
   experiment.

## Follow-up

The durable model-source API should expose the worker count as a typed source
option, so future acquisitions can use this optimization through the platform
manager rather than an operator-level override. That follow-up must retain
resume semantics and receive server-side regression coverage.
