# Architecture Repair Report — 2026-08-25

## Scope

This report records the source-level audit and repair performed on the current
working tree. Existing uncommitted SEM changes were preserved. The repair keeps
provider selection in composition roots and narrows runtime dependencies to
typed ports.

## Findings and repairs

### 1. MC composition leaked opaque runtime values

The source-server host used `object` return values, `getattr`-based process
discovery and a mutable `dict[str, object | None]` as a lifecycle handoff.
Branch runtime and participant composition also accepted opaque implementation
and runtime values.

Repair:

- source lifecycle now consumes `ServiceLaunchContract`,
  `ServiceStartOutcome`, `ServiceReconcileObservation`,
  `ServiceStopOutcome` and `ServiceProcessIdentity`;
- MC branch and participant seams use the concrete MC implementation/runtime/
  session contracts already owned by the MC subsystem;
- diagnostic attributes use the platform `JsonValue` contract;
- the process handoff is a private typed state object, preserving the start
  identity when reconciliation is temporarily incomplete.

### 2. Compiled Core-6 branch identities were not resume-compatible

The generic paired path uses `run:role:rep-N`, while compiled variant execution
uses `run:role:rep-N:variant-id`. `MinecraftResumeIndex` previously accepted
only the first form, so a checkpoint produced by a compiled arm could not be
published into or loaded from the resume index.

Repair:

- resume identity validation now accepts the base and compiled-variant forms;
- role and repetition remain bounded by the frozen run identity;
- variant suffixes are restricted to `[A-Za-z0-9_.-]+`;
- malformed or undeclared branch identities remain fail-closed;
- regression coverage now includes a `Fixed-C` compiled branch and malformed
  suffix rejection.

### 3. Dry-composed and runtime candidate identities could diverge

The MC preflight previously materialized every non-control arm from the root
Seed-X candidate, while compiled runtime execution selected the candidate from
each binding's seed id. That made the preflight object graph weaker than the
graph actually executed: Rule-C/Self-C could be validated as Seed-X.

Repair:

- candidate selection is now an explicit typed `CandidateArchitectureResolverPort`;
- one resolver instance is constructed at the production composition root and
  injected into both provider-closure validation and MC/non-MC bound execution;
- the default resolver preserves the frozen generation while resolving
  Seed-C/Seed-X independently;
- fixed-provider classification is shared by the endpoint, MC and non-MC
  adapters, including the legacy `fixed-memory` compatibility id;
- identity-level coverage asserts the materialized candidate sequence is
  Seed-C, Seed-C, Seed-X, Seed-X for Core-6 treatment arms.

## Verification

The following checks pass in this working tree:

- Python compilation for platform, project, scripts and tests;
- typed MC source-host smoke, including temporary reconcile incompleteness;
- SEM deep-repair `unittest` suite: 7 tests passed;
- semantic candidate-identity smoke tests passed;
- deterministic non-Minecraft production run: completed, claim disabled;
- `ARCHITECTURE_GATE_PASS`;
- public contract audit: 0 weak contracts;
- silent-failure audit: PASS;
- no-degradation audit: PASS;
- SEM architecture audit: 1 blocking item open, `LIVE_EXECUTION_EVIDENCE`.

## Remaining blocker

The remaining open item is external evidence, not a missing local interface:
an immutable qualified model deployment closure and a passing real Minecraft
T2B gate are required before any live scientific claim. The current checkout
contains neither, so the claim gate correctly remains closed.
