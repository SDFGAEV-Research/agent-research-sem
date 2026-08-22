# Refactoring vNext — Hierarchical Systems, Deep Decoupling, and Diagnosable Architecture

## 1. Non-negotiable direction

This refactor is intentionally incompatible with the historical API surface. No compatibility aliases, legacy adapters, migration shims, or dual-write bridges are required.

The target is a system that remains understandable when the platform contains:

- many workspaces and research programs;
- many projects, studies, experiments and runs;
- many methods and participant implementations;
- many model families, model revisions and deployments;
- many environments and remote hosts;
- many servers/processes active at the same time;
- failures that must be debugged from platform scale down to one component invocation.

The design therefore optimizes for **structural isolation**, not short-term feature velocity.

## 2. Hierarchical management rule

A higher-level system owns only its direct responsibility and composes lower-level systems through narrow contracts.

```text
Platform
└── Workspace
    └── Research Program
        └── Project
            └── Study
                └── Experiment
                    └── Run
                        ├── Branch
                        ├── Participant
                        │   └── Session
                        └── Operation
```

The organizational tree is owned by the Scope System. Portfolio metadata, experiment semantics, runtime state, model state, environment state, and diagnostics are different authorities.

No lower-level component is allowed to reach upward into a parent system's internal state. Parent systems may depend on child APIs, but child systems do not depend on parent implementations.

## 3. System tree

The platform is decomposed into independent systems:

```text
Platform System
├── Portfolio System
├── Experimentation System
├── Execution System
├── Participant System
├── Scientific Method System
├── Resource System
├── Environment System
├── Model System
├── Runtime System
├── Data System
├── Artifact System
├── Reliability System
├── Observability System
├── Governance System
└── Operator System
```

Each system is allowed to contain smaller systems/components/providers, but the same rules repeat recursively:

```text
System
└── SubSystem
    └── Component
        └── Provider / backend
```

`SystemRegistry` is a topology authority only. It describes ownership and dependencies; it does not execute business behavior.

## 4. Contract / runtime / implementation / composition

Every independently replaceable concern follows:

```text
Stable Contract
      ↓
Runtime orchestration
      ↓
Implementation / Provider
      ↓
Backend
```

Composition is outside all four. A composition root is the only place allowed to choose concrete providers and wire systems together.

A public API package must therefore contain contracts, identities, value objects, and ports — not locks, worker loops, buffering, process control, storage mutation, or provider-specific branching.

## 5. State authority

There is exactly one durable authority per mutable/effect domain.

```text
State Authority      → canonical durable state
Effect Authority     → external-effect intent/certainty/reconciliation
Artifact Authority   → immutable artifact identity/content
Failure Authority    → durable failure envelope/taxonomy
Projection           → disposable read model
Telemetry            → observation
Log                  → observation
Diagnostics          → read-side correlation/debugging
```

A fast index is never promoted to authority merely because it is easier to query.

## 6. Logging system

Logging is a first-class internal system, not a helper around `print()` or a global singleton.

The logging system has independent contracts for:

```text
Logger creation/context
Structured log record
Log sink
Log query
Log projection/index
Log retention
Raw byte/event capture
```

The logger only writes structured observations. It does not own failure taxonomy, state mutation, recovery, or scientific truth.

Every log record carries a stable diagnostic address:

```text
Scope path
System path
Component
Operation
Trace
Span
```

This makes the same record queryable from multiple scales without duplicating business-specific log formats.

## 7. Exception and failure separation

An exception is not itself the durable failure model.

```text
Python/runtime exception
        ↓
SafeExceptionDescriptor
        ↓
Failure materialization
        ↓
FailureEnvelope
        ↓
Forensics / incident / recovery projections
```

`SafeExceptionDescriptor` is responsible only for safe description/redaction/digesting.

`FailureEnvelope` is responsible for stable failure identity, taxonomy, operation/correlation references, risks and recovery semantics.

`Diagnostics` is read-only over these authorities. It does not manufacture a second failure authority.

## 8. Debug hierarchy

A single failure must be traceable without knowing the implementation layout.

```text
Platform
  → system
    → subsystem
      → workspace/program/project
        → study/experiment/run
          → participant/session
            → operation
              → component
                → model request / effect / state mutation
                  → failure / log / evidence
```

The diagnostic system therefore provides at least these query dimensions:

```text
by scope
by system/subsystem
by component
by trace/span
by operation
by failure
by model request
by effect
by state writer
by artifact/evidence reference
```

Higher-level debugging is a projection over lower-level facts; it never requires those lower-level systems to know the debugging UI.

## 9. No-fallback design

Operational policy must be encoded into the domain contracts and identity bindings rather than spread across supervisory gates.

Examples:

- a run owns an exact model/deployment identity;
- recovery receives the frozen launch contract, not a generic "best model" selector;
- a checkpoint binds its runtime identity;
- an environment binding is immutable for the run once frozen;
- effect execution returns certainty instead of allowing callers to infer success from exceptions;
- projection drift invalidates the projection instead of patching it.

A small architecture test suite may exist as verification, but correctness must primarily arise from the dependency graph, ownership model, type boundaries, and frozen identities.

## 10. Refactor order

The new codebase is reorganized in this order:

1. Recursive System Registry and Scope Kernel
2. Portfolio → Project → Study → Experiment → Run ownership chain
3. Environment system and environment bindings
4. Model system and exact deployment/serving identity
5. Data / Artifact authorities
6. Runtime orchestration and server/process management
7. Reliability: failure, recovery, forensic evidence
8. Observability: logs, telemetry, status and projections
9. Operator read/command surfaces
10. Scientific implementations and SEM integration
11. Architecture intelligence and optimization

The logging/failure/diagnostics foundation is introduced early because every later system must be debuggable from its first implementation.

## 11. Current vNext foundation

The following foundations now exist in the development tree:

- recursive `SystemRegistry` ownership traversal;
- `DiagnosticAddress` carrying hierarchical scope/system context;
- storage-neutral structured `LogRecord`;
- narrow `LogSinkPort` and `LogQueryPort`;
- independently replaceable `StructuredLogger`;
- independent fan-out and in-memory log backends;
- read-only `DiagnosticLogQueryAdapter`;
- safe exception descriptors remain in kernel and are not coupled to logging storage.

This establishes the correct seam for the larger migration without introducing a compatibility layer.
