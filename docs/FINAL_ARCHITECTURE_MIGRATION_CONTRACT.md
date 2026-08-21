# Final Architecture Migration Contract

Status: active migration contract

This document is the execution contract for the direct migration to the final
platform architecture. It is intentionally incompatible with the historical
layout. The target is a recursively layered platform that can host many
projects, methods, experiments, model assets, runtimes, and servers without
creating a second authority for any of them.

## 1. Completion objective

The migration is complete only when all of the following are true:

1. The registered system and subsystem topology is the only architectural
   authority.
2. Every production responsibility is owned by exactly one target node.
3. Parent systems compose their direct children; they do not implement or
   reach through grandchildren.
4. Cross-node traffic uses the owning node's public API/port contract. Concrete
   provider imports stop at the composition boundary.
5. Runtime state, durable state, projections, diagnostics, and control-plane
   state have distinct ownership and explicit data flow.
6. Every production entry point resolves through the target topology and has a
   reproducible verification record.
7. A migrated historical boundary has no remaining source import, entry point,
   test ownership, packaging reference, documentation authority, or runtime
   responsibility, and is then physically deleted.
8. The final tree contains no compatibility alias, shim, dual-write path,
   silent fallback, or downgraded execution path retained for the old layout.

“The new package exists” is not migration. A node counts as migrated only when
its authority is moved, its callers are rewired, its focused checks pass, and
the old owner is retired.

## 2. Target ownership model

The packaged catalog resource at
`research_platform/governance/system_registry/catalog.json` is the sole runtime
source of system identity, parentage, public shape, ownership, and forbidden
ownership. `docs/VNEXT_SYSTEM_CATALOG.json` is an auditable documentation mirror
and must remain byte-equivalent to the packaged resource. The runtime registry
materializes the packaged catalog; it must not define a competing topology or
silently infer missing semantics.

Each registered node has four explicit surfaces:

- `api`: contracts, identities, ports, and domain-level errors exposed to
  direct children and approved consumers;
- `runtime`: the node's stateful implementation and lifecycle semantics;
- `providers`: infrastructure or external adapters owned by that node;
- `composition`: the only place where concrete providers are bound to APIs.

Dependency direction is from a parent to its direct children and from a
composition root to concrete providers. A child never imports a parent
implementation, a sibling's concrete provider, or a grandchild's internal
module. Shared concepts become contracts at the lowest node that truly owns
them; they are not placed in a catch-all utility or service locator.

### 2.1 Paper methods are project-owned implementations

The `scientific` system owns reusable method identity, configuration,
registration, lifecycle, and provider contracts. It does not own the scientific
truth of a particular paper. A concrete paper method is kept under its project
namespace and is joined to platform systems only through injected contracts:

```text
research_platform/<system>/api/       stable interface/port
projects/<project>/composition/       project-owned binding root
projects/<project>/method/<method>/   concrete paper method
```

For Paper-1, `projects/sem_paper/method/self_evolving_memory` is the owner of
the self-evolving-memory method. The migrated Python files are method
implementation, method runtime, method evidence, and method-local adapters;
they must not be reclassified as generic platform code. The platform exposes
only stable contracts such as `MethodCompositionPorts`, method endpoint/runtime
ports, `MethodObservationOutboxPort`, `LoggingSystemPort`, and `LogWriterPort`.
The project may define its own logging policy, serving provider, state adapter,
and evolution provider behind those seams.

This is not a compatibility exception. The project composition root is the
single legitimate place that binds the platform interfaces to the project's
concrete method implementation. A platform package must not import a concrete
paper method, and a paper method must not import platform concrete
`runtime`/`providers`/unrelated `composition` modules. The project API firewall
and SEM source-authority extension are the executable enforcement of this rule.

The following are different kinds of truth and must not be conflated:

- topology truth: catalog and registry;
- domain truth: the owning system's durable records;
- execution truth: lifecycle/checkpoint/effect receipts;
- observation truth: append-only evidence and telemetry;
- diagnostic truth: derived joins that explain failures;
- control truth: desired state and applied state for operators.

Projections and diagnostics may reference their source identities, but cannot
become a second writer or owner of source truth.

## 3. Migration state machine

Every target node and historical boundary is tracked through this state
machine:

`declared -> implemented -> wired -> verified -> retired`

- `declared`: target contract and owner are recorded in the catalog;
- `implemented`: the target API/runtime/provider surfaces exist and satisfy the
  contract;
- `wired`: all production callers use the target owner and composition path;
- `verified`: source, import, call-graph, architecture, error, and focused
  runtime checks provide evidence for the node;
- `retired`: the historical owner is deleted and no reference remains.

No node may skip `wired` or `verified`. `retired` is forbidden while any old
authority remains reachable, even if tests happen to pass.

## 4. Migration order

Migration proceeds in dependency order, not by file count:

1. topology, governance, scope, platform kernel, and registry authority;
2. data, artifact, resource, environment, model, and runtime foundations;
3. execution, participant, experimentation, scientific, project, and method
   production paths;
4. observability, reliability, operator control, model assets, and server
   management integration;
5. release evidence regeneration, full residual audit, physical deletion of
   all retired historical boundaries, and clean final verification.

Within each node, move the authority before moving convenience helpers. A
directory is not a target subsystem merely because its name resembles the
catalog name; ownership follows the behavior and its callers.

## 5. Required evidence for each migration slice

Before editing a slice, record a compact design packet containing its owner,
interfaces, dependency direction, data flow, state transitions, side effects,
failure semantics, and representative tests. During the slice, capture:

- CodeGraph entry points, dependency graph, callers/callees, and impact;
- AST/import ownership and cross-system dependency audit;
- focused contract and regression tests;
- error identity, diagnostic coordinates, and recovery/rollback behavior;
- persistence/checkpoint/effect evidence where the slice has state or side
  effects;
- updated catalog, migration matrix, and versioned change record.

After rewiring, rerun the same checks from the target root. Evidence from a
new package does not prove that the old package is unused; residual scanning
must independently prove deletion readiness.

## 6. Deletion gate

A historical directory, module, entry point, or ownership record may be
deleted only after all checks below are clean:

- no production or test import targets it;
- no script, packaging metadata, configuration, manifest, or service unit
  starts it;
- no catalog or registry descriptor names it as an owner;
- no docs or operational runbook presents it as authoritative;
- CodeGraph shows no reachable production path through it;
- focused tests and architecture gates pass from the target topology;
- the deletion and its evidence are recorded in the migration log.

An immutable frozen release manifest is historical evidence of the release it
describes. It may retain the retired path as a historical file member, but it
does not start, import, package, or own the current implementation. The current
development snapshot, packaging metadata, configuration, service units, and
operational manifests must contain only the target path. A frozen release
manifest is never edited to make a development migration look like a new
release; a new release manifest requires the complete release-evidence workflow.

Deletion is physical removal, not renaming, re-exporting, forwarding, or
marking a module deprecated. If a check fails, fix the owning dependency before
deleting; do not add a compatibility bridge to make the audit appear clean.

## 7. Non-negotiable quality rules

- Do not weaken assertions, metrics, error propagation, or evaluation to make
  a migration pass.
- Do not add a generic manager, global registry, catch-all context, or
  `object`-typed service locator to hide an ownership problem.
- Do not make correctness-critical lifecycle, effect, checkpoint, evidence,
  or model-request paths optional merely to preserve an old caller.
- Do not mix architecture migration with unrelated cleanup.
- Do not claim a release from stale snapshot metadata; regenerate evidence from
  the current tree.
- Every failure is diagnosed at its actual boundary and corrected at the root
  cause before the migration proceeds.

## 8. Current baseline and blockers

The current repository contains a vNext catalog and a substantial target
surface, but historical production ownership is still present in several
fragmented roots. The first migration work package must therefore produce a
machine-readable ownership matrix covering every registered node, real package
root, entry point, provider, and caller.

The project now has an explicit Git boundary. Migration slices must be recorded
as focused commits after their source, architecture, and regression evidence is
captured. The baseline migration commit is
`d7a6178` (`establish final architecture migration baseline`). Git history is
version control evidence, not a substitute for the deletion gate or runtime
verification.

The current local snapshot metadata is also stale relative to the source tree.
It must be regenerated only after the target topology and real entry points are
reconciled; stale metadata must never be used as release evidence.
