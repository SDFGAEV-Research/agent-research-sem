# Current Architecture and Evolution — 2026-08-20

This document describes the **actual current development worktree** and compares it with the earliest architecture shape that is still explicitly documented in this repository. It is a development-state description, not release evidence.

## 1. Current architecture

The current system is no longer organized around a single SEM/Minecraft execution path. The primary architecture is a contract-driven research platform with explicit API, runtime, composition, durable-truth, scientific-method, and operator-management planes.

```text
                         Composition Roots
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
 Stable Contract Plane     Runtime Plane       Scientific Implementations
         │                     │                     │
 kernel / *_api           *_runtime / *_os      projects/sem_paper/method/self_evolving_memory
         │                     │                     │
         └─────────────── explicit ports ────────────┘
                               │
                     Durable Truth / Evidence
                               │
       state / effect_journal / forensics / release / process capture
                               │
                    Side-plane Observation
                               │
                    telemetry / diagnostics
                               │
                    Operator Management Plane
                               │
       directories / Python envs / model assets / deployments / controller
```

### Stable contract plane

The platform exposes narrow contracts through packages such as:

- `participant_api`, `method_api`, `environment_api`, `capability_api`;
- `service_api`, `runtime_api`, `status_api`, `diagnostics_api`;
- `effect_api`, `failure_api`, `observability_api`;
- `prompt_api`, `model_request_api`;
- `scope_api`, `projection_api`, `record_api`, `fact_api`, `process_api`;
- `directory_api`, `python_env_api`, `model_management_api`.

The intended dependency rule is that cross-system code consumes these contracts rather than unrelated concrete implementations.

### Runtime plane

Concrete runtime behavior is separated into packages including:

- `participant_runtime`, `workflow_runtime`, `capability_runtime`;
- `model_request_runtime`, `scope_runtime`, `projection_runtime`, `status_runtime`;
- `service_os`, `model_os`, `prompt_os`, `runtime_manager`;
- `server_session`, `process_capture`;
- `directory_runtime`, `python_env_runtime`, `model_management_runtime`.

### Composition plane

`research_platform/composition/` is the intended cross-domain wiring boundary. It assembles unrelated concrete authorities and passes narrow ports into consumers rather than allowing Study, Method, Runtime Manager, or Operator code to construct arbitrary backends internally.

### Participant/runtime identity

The system now treats functional/scientific implementation identity separately from runtime/session identity and binding. The generic participant layer is the common lifecycle abstraction for replaceable participants rather than giving Method, Agent, Environment, and Capability completely unrelated lifecycle semantics.

### Scientific method plane

`projects/sem_paper/method/self_evolving_memory/` remains the concrete Paper-1 scientific implementation. Its internals are already substantially decomposed into serving, evidence, task, session, evolution, adoption, materialization, generation, persistence, and snapshot responsibilities rather than one monolithic memory runtime.

### Effect, recovery, and failure plane

External effects are no longer represented by a simple success/failure boolean. Effect phase, certainty, reconciliation, retry safety, failure taxonomy, operation correlation, and recovery evidence are separate concepts. Failure semantics are separated from forensic persistence, while diagnostics consumes durable evidence to build operator-facing causal/triage views.

### Model-visible request plane

The current Harness-pattern integration records model-visible request material durably before invocation and reconstructs the actual request from durable content. Scoped registrations, capability policy, incremental projections, and Durable-Fact / Live-Interception / Side-Plane-Observation semantics are also explicit subsystems rather than informal conventions.

### Runtime asset management plane

The latest development work adds a mutable operator-management plane that is deliberately separate from scientific release/qualification:

```text
Directory authorities
├── layout
├── workspaces
├── inspection
└── cleanup

Python environment authorities
├── registry
├── lifecycle
├── execution
└── packages

Model management
├── asset registry/storage/source
├── desired deployment catalog
├── applied runtime snapshot
├── single-deployment runtime
├── fleet reconcile
├── launch materialization
├── log reader
├── GPU/resource view
└── desired-state controller
```

This plane supports day-to-day server operations without making every management action a scientific qualification gate.

## 2. Earliest documented architecture shape

The repository's Round 06 notes explicitly describe the new method plugin architecture as a **replacement**, not a compatibility wrapper around the old `memory_runtime / evolution / mc_runtime` packages. That is the earliest architecture boundary that can be stated directly from the repository history.

The earlier shape can therefore be summarized as:

```text
Experiment / task entry
        │
        ├── memory_runtime
        ├── evolution
        └── mc_runtime
              │
          Minecraft-specific execution
```

The system center was the current paper method and its execution environment. Scientific method logic, environment execution, state handling, experiment orchestration, model calls, persistence, recovery, and debugging were much closer to the same execution path.

## 3. What fundamentally changed

| Axis | Earliest documented shape | Current development shape |
|---|---|---|
| System center | SEM + Minecraft experiment flow | Generic research platform contracts and authorities |
| Method boundary | Memory runtime was a central runtime subsystem | SEM is one concrete scientific implementation behind generic method/participant boundaries |
| Environment | Minecraft runtime was part of the main architecture | Environment is a replaceable participant/host boundary |
| Runtime identity | Implementation and execution substrate were closely tied | Implementation identity, runtime identity, configuration, and binding are separate concepts |
| Cross-domain dependencies | Concrete packages could be reached directly | API/port boundaries plus composition-root wiring are the target rule |
| State | Runtime-owned/concrete stores were easier to expose across layers | Durable state ownership, versioning, state writers, projections, and backend boundaries are explicit |
| External effects | Mainly operational success/failure handling | Effect intent, phase, certainty, reconciliation, retry safety, and mutation semantics are explicit |
| Failure handling | Logging/exception-oriented debugging | Stable failure taxonomy, durable failure truth, causal diagnostics, last-writer/why/triage paths |
| Model calls | Prompt/model call was mainly an execution concern | Model-visible requests are durable and reconstructable with explicit model/prompt/runtime identity |
| Prompt | Prompt construction was local execution logic | Prompt OS / prompt API / promotion / trace / generation are explicit authorities |
| Service/model serving | Process startup was part of runtime scripts | Service OS, Model OS, process capture, qualification, deployment, management, and runtime views are separated |
| Server persistence | Server process management was operational glue | Persistent session API, tmux backend, exact process identity, crash handoff, and controller/runtime truth are separate |
| Observability | Logs around execution | Structured operation/event/metric/failure correlations plus side-plane non-interference |
| Architecture checks | Primarily human structure | Import, cycle, authority, source-invariant, capability, operation, event, and hotspot reports |
| Release | Source package was primarily a deliverable | Manifest/evidence/regression/package self-verification distinguish frozen release from development snapshot |
| Asset management | Paths/envs/models were mostly deployment prerequisites | Explicit directory, Python environment, model asset, deployment, GPU, logs, and desired-state management |
| Extensibility | Replacing the method/environment implied broad rewiring | Goal is replace Method/Agent/Environment/LLM/runtime/storage without rewriting surrounding systems |

## 4. The most important architectural evolution

The deepest change is this inversion:

```text
Original direction:
SEM / Minecraft runtime
        ↓
owns or reaches most surrounding concerns

Current direction:
Generic contracts + authorities
        ↓
composition binds concrete participants
        ↓
SEM and Minecraft become replaceable implementations
```

The project has therefore moved from a **paper-specific agent codebase** toward a **research operating platform**.

## 5. Current verified development baseline

At the time this document was generated from the actual worktree:

- package version: `0.41.0`;
- production Python files under `research_platform/` + `projects/`: 1937;
- test modules: 223 (`tests/test_*.py`);
- platform subpackages under `research_platform/`: 64;
- tests collected: **not rerun after the final-architecture migration**;
- focused migration regression: **23 passed** across the current project,
  architecture, source-authority, SEM, and degradation checks;
- Architecture Gate: **PASS**;
- Silent Failure Audit: **PASS**;
- No-Degradation Audit: **PASS**;
- architecture import edges: **2676**;
- package cycles: **0**;
- import/declared-authority/source-authority/source-invariant violations: **0**;
- capability graph: **6 edges**;
- operation graph: **30 edges**;
- event graph: **12 edges**;
- architecture report internal SHA-256: `dd7576b9456a4e0bf8bd6976098e0be3b3a33711c3f39c998493ca43a4dbf2a9`.

## 6. Important remaining gaps in the actual tree

The current system is much more decoupled than the original architecture, but it is **not yet at the final target**. The following are visible in the actual worktree and should remain future refactor targets rather than being described as completed work.

### 6.1 SEM still reaches the concrete platform state package

Several SEM adoption modules still import `research_platform.data.state` concrete types such as `AtomicStateStore`, `AtomicMutation`, `AggregateValue`, and `StateVersionConflict`.

Target:

```text
SEM scientific/adoption logic
        ↓
method-owned narrow state port
        ↓
composition/runtime adapter
        ↓
platform state backend
```

### 6.2 SEM still contains a local composition module

`projects/sem_paper/method/self_evolving_memory/composition.py` performs
method-local wiring by design: the self-evolving-memory implementation is the
Paper-1 method, not a generic platform component. The final architecture keeps
this method-owned wiring inside the project/method seam and requires the outer
project composition root to inject only platform interfaces. Unrelated
platform backend/runtime joining must remain outside the method package.

### 6.3 Some API packages still contain runtime implementation

Examples currently present include:

- `participant_api/checkpoint_runtime.py`;
- `method_api/observation_outbox.py`;
- executable runtime behavior in API-adjacent modules that should be reviewed against the strict API/runtime separation rule.

These are not catastrophic coupling, but they are inconsistent with the final four-layer discipline.

### 6.4 SEM retains a local canonical helper

`projects/sem_paper/method/self_evolving_memory/canonical.py` still exists while the platform kernel also owns canonical serialization/digest primitives. Canonical identity should eventually have one authority unless the method helper is demonstrably a distinct scientific encoding domain.

### 6.5 Management decomposition is still in progress

Directory and Python-environment management have already been split into narrow authorities. Model management has also been decomposed significantly, but `model_management_runtime/assets.py` remains a natural next hotspot for separating catalog/query/source/statistics responsibilities if it continues to grow.

## 7. Bottom line

The original architecture was essentially:

```text
paper method + Minecraft runtime + experiment execution
```

The current architecture is much closer to:

```text
Contract-Driven Research Platform
├── replaceable scientific participants
├── replaceable runtimes/backends
├── explicit composition roots
├── durable state/effect/failure/release truth
├── reconstructable model requests
├── diagnostics/observability side planes
└── operator asset/service management
```

The next work should no longer focus on creating more top-level subsystems. The platform already has enough system surface area. The higher-value work is now to finish the remaining **authority leaks and API/runtime mixing**, then continue performance and scientific-provider optimization on top of stable boundaries.
