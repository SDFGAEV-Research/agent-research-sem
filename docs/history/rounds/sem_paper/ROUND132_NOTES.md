# SEM Paper Round 132 — current model qualification status

Date: 2026-08-23

This note records the current implementation/evidence boundary. It does not
promote any model-backed result.

## What is implemented

- The SEM planner now sends the compiled planner prompt in a user message,
  satisfying the deployed Qwen endpoint's chat protocol.
- The experiment can explicitly generate a process-scoped ephemeral RCON
  secret when no secret is supplied; the secret is not persisted in manifests
  or logs.
- The result writer's scientific-claim gate rejects control-only runs,
  scripted-only runs, no-request runs, and runs without paired control and
  candidate memory queries.
- The model endpoint provider preserves bounded structured HTTP error details,
  including status and server error payload, for root-cause diagnosis.

## What is not yet evidence

- T01 baseline completed without a model request and is not model-backed
  scientific evidence.
- T02 reached the endpoint after the user-turn repair but the Qwen3.5 service
  returned a non-JSON abort/degenerated `!` response. It is a serving-stack
  failure, not a SEM algorithm result.
- No baseline/candidate paired scientific run has been promoted.
- The SGLang 0.5.17 candidate did not pass architecture-specific kernel import
  on the RTX 3090 host, so it was never used for an experiment.

## Immediate dependency

The next step is the platform-level deployment qualification plan described in
`docs/history/rounds/platform/ROUND40_NOTES.md`. The SEM project will consume
the resulting frozen environment/deployment identity; it will not manually
choose a framework version or bypass a failed qualification gate.
