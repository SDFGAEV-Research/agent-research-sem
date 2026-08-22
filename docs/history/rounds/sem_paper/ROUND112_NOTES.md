# Round 112 — workload diagnostic failure retention

## Change

The Paper Minecraft workload adapter no longer silently discards failures from
its injected event, metric or failure sinks. `MinecraftWorkloadRunner` keeps a
bounded diagnostic-error tail and exposes it in `MinecraftTaskRunResult` under
`diagnostic_sink_errors`.

The primary workload operation still follows its original failure semantics:
a diagnostic sink failure does not fabricate task failure or hide an actual
environment/method/planner exception. The sink error is retained as structured
handoff evidence so the platform/project composition root can surface it in
the unified diagnostic system.

## Verification

- workload, evidence, MC environment, project firewall and source-invariant
  tests: **73 passed**;
- a failing diagnostic sink test confirms the task result remains correct and
  the sink error tail is returned;
- changed modules compile successfully;
- no diagnostic storage authority was added to the workload adapter;
- no server, model or scientific experiment was run.
