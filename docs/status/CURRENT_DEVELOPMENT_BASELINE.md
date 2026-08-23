# Current Development Baseline — 2026-08-23

This document describes the **current development worktree**, not the last verified release. Historical round notes remain historical evidence for their own freeze points.

## Current local SEM Minecraft bootstrap status — 2026-08-24

The scripted-smoke composition now has explicit, independently auditable
bootstrap routes for the official Mojang server artifact, an official Eclipse
Temurin Java 21+ runtime, the deterministic source-world scenario and the
locked Mineflayer action stack. Java acquisition is platform-owned under
`runtime/toolchain`; MC consumes only its typed provisioning port and receipt.
The Java archive, materialized tree, executable and version output are verified
and bound into the run/source environment identities.

The hosted container's directly installed Java remains version 17, so the
host-Java preflight correctly fails the Minecraft 1.21.8 minimum. The new
explicit acquisition path closes that code/configuration gap, but this slice
did not accept the Minecraft EULA, download the full production binaries or
start a live MC process. No T2B or scientific result is claimed.

Focused MC/SEM/artifact/catalog regression is green, and the architecture,
silent-failure and no-degradation gates pass. The unfiltered full suite reports
`1083 passed, 2 failed, 1 warning, 4 subtests passed`; the two failures are the
unchanged hosted PID-namespace `/proc/<Popen pid>/stat` limitation in
`tests/test_local_service_process_v110.py`. The final exact run deselecting only
those two host-incompatible cases is
`1084 passed, 2 deselected, 1 warning, 4 subtests passed`; the Node bridge suite
is `8 passed`.

## Current server validation status — 2026-08-24

The post-Batch-18 server verification has not started because the managed
`sem-ubuntu` target is currently unreachable: the profile-bound SSH probe
timed out before authentication or remote command execution. The server
management system also correctly reports one older timed-out mutation as
`effect_uncertain=true`, so mutation, repository sync and test execution are
blocked until that operation is reconciled. No bypass, retry loop or local
substitute result is being counted as server evidence.

## Current server/model qualification snapshot — 2026-08-23

The environment identity registry is now complete on the validation server:
the platform `env list` operation returns all four `ready` Python environments
with immutable `specification_digest` values. Two pre-identity records were
repaired only through the explicit `env migrate-legacy` operation after their
actual Python 3.11.15 interpreters were checked. No package, model, service or
scientific workload was changed. Routine inventory is bounded to
`state/python-environments`; it does not scan model pools or caches.

The latest server evidence is recorded in
`docs/history/rounds/platform/ROUND46_NOTES.md`,
`docs/history/rounds/platform/ROUND45_NOTES.md`,
`docs/history/rounds/platform/ROUND44_NOTES.md`,
`docs/history/rounds/platform/ROUND43_NOTES.md`,
`docs/history/rounds/platform/ROUND42_NOTES.md`,
`docs/history/rounds/platform/ROUND41_NOTES.md`,
`docs/history/rounds/platform/ROUND40_NOTES.md` and
`docs/history/rounds/sem_paper/ROUND132_NOTES.md`. In brief, the Qwen asset is
complete, but no model-backed SEM result is qualified: the old SGLang stack
degenerated, the newer SGLang kernel candidate is incompatible with the host's
SM86 architecture, and the first vLLM environment bootstrap stopped at the
missing Ubuntu `ensurepip` prerequisite. The operation ledger has been
independently reconciled and no unresolved server mutation is being hidden.

The current platform implementation is a typed deployment-qualification plan
that combines read-only host facts, Python bootstrap facts, model/backend
support rules and package-index evidence. It produces exact install sources and
explicit rejection causes before the existing environment/deployment systems
materialize anything. The v4 recursive PEP 658 closure, fixed-point constraint
solver and frozen transitive install plan are now server-verified: 42 focused
tests, `ARCHITECTURE_GATE_PASS` and `NO_DEGRADATION_AUDIT_PASS`. The real Qwen
environment remains unmutated. The latest full qualification selected
`vllm==0.27.1` with 162 closure nodes and 161 transitive packages; SGLang was
rejected for explicit binary-wheel, metadata and SM86 architecture evidence.

The verified full record has facts digest
`23a10803981db312760d617e5e0bd88650457464eec90e8a7432b38e008d6e2c`, plan
digest `504f51ea3a48f87b8d05cb03c6b55fe3d7c623003ef2da0ea19a2938c4d56c57`,
and record digest
`ea8a9403996d56a21bb35781f544b3fa3343bead81aebab354cef14eefb84de6`. The
post-materialization runtime qualification path is implemented and server-
tested, but real backend import, CUDA-extension and endpoint-readiness
evidence remains pending until a managed environment is deliberately
materialized.

## Latest Paper-1 execution evidence — 2026-08-22

- The current Paper-1 composition slice now binds the fixed Seed-C control
  treatment to the explicit typed Deluxe serving provider; this is wiring
  evidence only and has not been promoted to a live or scientific result.
- The server-only focused Paper-1/Minecraft regression for the current
  paired-execution slice is **37 passed**.
- The current paired scripted smoke completed with
  `comparability.valid=true`, zero failure records, and durable event,
  metric, method-observation and result artifacts. It remains
  `scientific_claim=false` because it uses the scripted planner.
- The model-backed baseline is still gated by completion and verification of
  the Qwen3.6-35B-A3B asset; the resumable platform-managed fetch is active on
  the Ubuntu server.
- The official Qwen3.8-27B BF16 candidate is downloading independently through
  a persistent platform session. It is not yet promoted: the current SGLang
  0.5.10 environment and RTX 3090 host are outside the current official
  Qwen3.8-27B validation matrix, so a separate runtime and qualification gate
  are required.
- Commit `2b22a86` moved the immutable model-stack contracts into the owning
  `model.stack` system, exposed typed Hugging Face acquisition concurrency,
  and passed **47** AI-infra/model-serving tests on the server.
- Commit `288e688` repaired an independent recovery-invariant auditor blind
  spot found by the architecture gate; the post-fix server architecture,
  dependency and no-degradation subset passed **69** tests.
- The next server slice composed direct SSH commands with the same profile
  environment as persistent sessions, fixing a Node 12/Node 22 shebang drift.
  Server evidence: **82 server tests + 4 subtests**, **6 focused profile-bound
  connection tests**, and `ARCHITECTURE_GATE_PASS`. Locked Minecraft bridge
  installation completed with **92 packages** in the latest staging.

## Verified development state

### 2026-08-21 SEM Minecraft execution slice

- The reusable MC experiment-host composition is now present under
  `research_platform/environment/minecraft/composition`.
- The SEM entrypoint consumes that host for source lifecycle, save barrier,
  world cuts and branch runtime creation.
- The focused MC/SEM regression for this slice is **28 passed**.
- No live Minecraft/model/remote execution is claimed; local preflight
  reached the runtime probes and stopped on missing Mineflayer packages.
- The current result writer explicitly marks the control-only path as
  `scientific_claim=false` until candidate materialization and paired study
  execution are wired.

### 2026-08-20 migration revalidation

- The final migration contract and ownership matrix are active.
- The 180-node registry preserves canonical ownership semantics at runtime.
- Architecture gate: **PASS** after the release-composition and Windows path
  fixes.
- Current import scan: **2684** internal edges; package cycles: **0**.
- Workflow invariant findings: **0**.
- CodeGraph circular-dependency check: **0** (one-shot graph-only run; its
  persistent graph database is unavailable in this environment).
- Focused migration regression (`public_api_imports`, `architecture_analyzer`,
  `source_authority_v123`, `release_docs_single_truth_v128`, SEM boundaries,
  and degradation checks): **23 passed** under the available Python 3.11
  runtime; five project-composition firewall checks also passed directly.
- Python syntax compilation for the migrated project and governance surfaces:
  **PASS**.
- Full regression after the migration slices: **not yet rerun**.

- Package version in `pyproject.toml`: `0.41.0`.
- Last verified release baseline: manifest `f18faec8c4970d3b8709db5b6d701db920fe298808edfe7859a2a18f26569fd1`, with `675/675` tests passed.
- Current development test module inventory: **223 modules**; a complete
  collected-test count is not asserted until the post-migration full runner is
  available.
- Current static gates after the migration slice: Architecture **PASS**,
  Silent-Failure **PASS**, and No-Degradation **PASS**. These are static gates
  only; they do not replace the pending complete post-migration regression.
- Current in-memory architecture report after the participant leaf split:
  **2684 import edges, 0 package cycles, 0 workflow findings**; report
  SHA-256 is `ddc6bb9619eb2c3649963974d232dac6a066c463eb9ae2b33bdf0a5ccec8e41b`.
- Current generated seam graph sizes: **6 capability edges, 30 operation edges, 12 event edges**.

`RELEASE_MANIFEST.json` and `RELEASE_EVIDENCE.json` still describe the last verified release. They are intentionally **not** rewritten for an ordinary development snapshot.

## Current architecture shape

```text
composition
├── kernel + stable APIs
│   ├── participant_api / service_api / prompt_api
│   ├── failure_api / effect_api / observability_api
│   ├── model_request_api / scope_api / projection_api
│   ├── directory_api / python_env_api / model_management_api
│   ├── capability_api / workflow_api / status_api
│   └── record_api / fact_api / process_api / diagnostics_api
├── runtime implementations
│   ├── participant_runtime / workflow_runtime
│   ├── model_request_runtime / scope_runtime / projection_runtime
│   ├── capability_runtime / status_runtime
│   ├── directory_runtime / python_env_runtime / model_management_runtime
│   └── service_os / model_os / prompt_os / runtime_manager
├── durable evidence/backends
│   ├── forensics / telemetry
│   ├── effect_journal / state
│   └── process_capture / release
└── scientific implementations
    └── projects/sem_paper/method/self_evolving_memory
```

The platform rule is **API/port across system boundaries, implementation only inside its owning subsystem or a composition root**.


## Runtime asset management

The current development tree now has a mutable operator-management plane that is deliberately separate from scientific qualification/freeze:

- explicit directory layout, lightweight disk overview, workspace allocation, stats, non-destructive cleanup planning and cleanup;
- backend-driven Python environment management (`venv`, `conda`, `mamba`, registered external prefixes), tags, direct command execution, export/clone workflows and centrally managed pip/conda caches;
- model asset registry for external or platform-managed weights, Hugging Face acquisition, origin metadata and named storage pools (default/NVMe/archive/NAS);
- generic executable/argv deployment definitions with optional SGLang/vLLM templates, tags and selector-based fleet management, with per-deployment lifecycle separated from fleet reconcile policy;
- Python-environment and GPU binding;
- separate model-asset, desired-deployment and applied-runtime stores, with safe reconfiguration via `UPDATE_PENDING -> reconcile`;
- a backend-neutral foreground desired-state controller suitable for hosting under tmux/systemd/container supervision;
- multi-deployment start/stop/restart/status/reconcile and `desire/desire-all` operations that separate desired state from immediate effects;
- operational HTTP readiness, stdout/stderr discovery/tail, and GPU PID-to-deployment correlation;
- GPU allocation/conflict/live-runtime visibility without adding a mandatory qualification gate.

A model/environment selected for a scientific run must still be frozen by the existing runtime/release authorities. Ordinary management actions do not rewrite release evidence.

See `docs/infrastructure/ai/RUNTIME_ASSET_MANAGEMENT.md`.

## Harness-pattern adoption

The current development tree absorbs five runtime patterns from the reviewed DeepSeek Harness while preserving this platform's stronger scientific/effect/release boundaries.

### 1. Reconstructable model requests

`PromptRequestBuildTransaction` records a `ModelRequestEnvelope` before the request is considered model-visible. The envelope freezes the full `ImmutableModelIdentity`, prompt generation/id/digest, canonical request-body content reference, compiled prompt reference, optional tool-schema bundle, execution context, and source artifact/state references.

Invariant:

```text
actual model-visible request bytes
==
reconstruct(ModelRequestEnvelope + durable content refs)
```

The returned request body is reconstructed from durable content, not retained from the builder-owned mutable object graph.

### 2. Scope-owned reversible registrations

`scope_api` defines hierarchical scopes and `scope_runtime.ScopedRegistrationRuntime` implements:

- child visibility of ancestor registrations;
- quiescent scope disposal;
- reversible per-registration handles;
- inherited-lease accounting across parent/child lifetime boundaries;
- idempotent concurrent close/dispose behavior.

Agent-turn capability routes are owned by a decision-cycle scope and are disposed in `finally`.

### 3. Capability invocation pipeline

`capability_runtime.CapabilityInvocationPipeline` composes policy around the existing effect-safe execution engine:

```text
monotonic guards
-> approval
-> crash-safe/effect-safe execution
-> post policies
-> final outcome
```

Effect certainty, WAL, reconciliation, retry safety and exactly-once semantics remain owned by the effect subsystem. A post-policy rejection after execution is represented as `execution_completed=True` and `retry_safe=False`.

### 4. Incremental projections

`projection_api.ProjectionTail` binds one exact source identity/version, start watermark, end watermark and item suffix. `projection_runtime` accepts only that tail contract. Source rewind, same-watermark identity drift, projector-version drift or source replacement fails closed and requires rebuild.

Forensics operation projection uses the same cursor semantics.

### 5. Generated seam graphs

The architecture report now derives:

- capability provider/consumer edges;
- operation emission edges;
- event producer/consumer edges.

Dynamic event families declare `EMITTED_EVENT_TYPES` / `CONSUMED_EVENT_TYPES` in source. The analyzer reads these declarations directly; there is no separately maintained graph file.

## Record-plane separation

The platform explicitly separates:

```text
DURABLE_FACT
LIVE_INTERCEPTION
SIDE_PLANE_OBSERVATION
```

Durable facts may participate in reconstruction/replay. Live interception can affect only the current execution unless it emits a durable fact. Side-plane observation is diagnostics/telemetry only and must never become primary operational or scientific authority.

Unknown durable facts fail closed unless explicitly marked ignorable.


## Current boundary debt (actual tree)

The current worktree is materially platformized but not yet the final ideal layering. Current source facts that remain next-step refactor targets include:

- SEM adoption still imports concrete `research_platform.data.state` types (`AtomicStateStore`, `AtomicMutation`, `AggregateValue`, `StateVersionConflict`);
- `projects/sem_paper/method/self_evolving_memory/composition.py` performs
  method-local wiring. This is intentional paper ownership, not a generic
  platform implementation: only the project composition root may bind it to
  platform ports, and the project API firewall must remain clean;
- `projects/sem_paper/method/self_evolving_memory/canonical.py` remains a second canonical helper beside the kernel authority;
- `method_api/runtime.py` still contains executable `MethodRuntimeEndpoint` behavior;
- `method_api/observation_outbox.py` is a lock/buffer/delivery runtime implementation living in the API package;
- `participant_api/checkpoint_runtime.py` performs checkpoint capture/restore execution;
- participant definition, binding and session runtime authorities are now split
  into leaf ownership; the binding resolver consumes only binding API ports and
  receives concrete leaf joins from composition;
- some session/service boundaries remain typed as `object` and should converge on narrow ports rather than a service-locator pattern.

These are current source facts, not architecture-policy exceptions. See `docs/architecture/CURRENT_ARCHITECTURE_EVOLUTION_20260820.md` for the detailed original-vs-current comparison.

## Current optimization order

The project remains **systemization-first**:

1. eliminate authority leakage and over-wide ports;
2. preserve implementation/runtime separation;
3. keep durable truth separate from projections and side-plane observation;
4. keep modules small and independently replaceable;
5. only then optimize algorithms/I/O/serialization/locking with measured complexity or performance evidence.

Current architecture hotspots are treated as inspection priorities, not automatic refactor requirements. High-fan-in API package roots are expected; mutable/lock/I/O concentration receives higher scrutiny.
