# Final Architecture Migration Matrix

Status: baseline captured on 2026-08-20

This matrix is the first work package of the final migration. “Implemented”
below is a structural inventory of substantive Python owned by the deepest
registered package prefix; it is not a claim that the node is production
wired. A node is complete only under the state machine in
`FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md`.

## Top-level ownership baseline

| Top-level system | Registered nodes | Substantive nodes | Thin nodes | Declaration-only nodes | Immediate migration concern |
|---|---:|---:|---:|---:|---|
| artifact | 7 | 2 | 0 | 5 | catalog/content/lineage/reference authorities need physical ownership audit |
| data | 8 | 3 | 0 | 5 | state/record/projection roots exist; SEM still reaches concrete state |
| environment | 12 | 3 | 1 | 8 | instance/runtime/python roots are fragmented across host/runtime code |
| execution | 7 | 3 | 1 | 3 | decision/lifecycle/participants/workflow implementations are outside target nodes |
| experimentation | 10 | 6 | 1 | 3 | catalog/evaluation roots and run composition need one production path |
| governance | 9 | 4 | 0 | 5 | registry semantics are split between Python topology and JSON catalog |
| model | 15 | 5 | 1 | 9 | request/prompt and serving/asset management need final provider boundaries |
| observability | 27 | 6 | 3 | 18 | logging/diagnostic implementations are not yet distributed to leaf owners |
| operator | 8 | 3 | 0 | 5 | management CLI and operator control roots are separate entry surfaces |
| participant | 7 | 2 | 0 | 5 | participant core owns real runtime/catalog behavior outside leaf declarations |
| platform | 4 | 1 | 0 | 3 | kernel/composition is still a large binding root |
| portfolio | 5 | 1 | 0 | 4 | project/workspace ownership is mostly declaration-only |
| reliability | 23 | 4 | 1 | 18 | diagnostics/forensics/recovery implementations need leaf ownership completion |
| resource | 7 | 3 | 0 | 4 | directory/compute/resolution are real roots; server resource integration remains |
| runtime | 18 | 5 | 1 | 12 | host/process/session/service are real but still composition-heavy |
| scientific | 6 | 0 | 0 | 6 | generic scientific contracts exist; concrete SEM is now project-owned but production root wiring remains |
| scope | 7 | 1 | 0 | 6 | scope registry is real; hierarchy/ownership/resolution remain to migrate |

Totals: 180 registered nodes; 52 substantive nodes; 12 thin nodes; 116
declaration-only nodes. These counts are inventory heuristics and must not be
used as completion metrics.

## Completed foundation slices

| Slice | Result | Evidence |
|---|---|---|
| `governance/system_registry` semantic materialization | `declared -> implemented -> wired -> verified` | 180 descriptors preserve catalog ownership fields; direct registry self-check passed |
| packaged system catalog resource | `declared -> implemented -> wired -> verified` | package resource loads without `docs/`; documentation mirror is byte-identical |
| release quality provider boundary | `declared -> implemented -> wired -> verified -> retired` for the old governance composition entry | architecture gate PASS; package cycles 0; old import reference absent |
| workflow dispatch authority portability | `implemented -> verified` | Windows path normalization fixed; workflow invariant findings 0 |

The completed slices do not imply that their parent systems are fully
migrated. Their residual deletion and package-distribution concerns remain in
the final audit until the whole topology is verified.

## Real roots that currently bypass a leaf node

The following roots are not historical names to preserve. They are current
production ownership that must be assigned to an explicit target node and then
deleted or physically moved:

| Current root | Target family | Required decision |
|---|---|---|
| `research_platform.execution.decision` | `execution/admission` or `execution/scheduling` | split decision policy from scheduling authority |
| `research_platform.execution.lifecycle` | `execution/operation` / `experimentation/run/lifecycle` | assign lifecycle by state owner, not by call convenience |
| `research_platform.execution.participants` | `participant/binding` / `participant/session` | remove execution-owned participant authority |
| `research_platform.execution.workflow.implementations` | `execution/workflow` | keep implementation behind workflow API and composition |
| `research_platform.experimentation.catalog` | `experimentation/study` / `experiment` / `run` | split hierarchy authority by owning state |
| `research_platform.experimentation.evaluation` | `experimentation/variant` or `scientific/measurement` | identify whether it owns treatment state or measurement |
| `research_platform.model.request.prompt` | `model/request/input` and `scientific/prompt` | separate request materialization from scientific prompt policy |
| `research_platform.participant.core` | `participant/definition`, `binding`, `session` | move implementation/catalog/config/checkpoint authority to leaves |
| `research_platform.platform.kernel` | `platform/identity`, `lifecycle`, `configuration` | retain only platform-kernel primitives at the parent |
| `research_platform.reliability.primitives` | `reliability/failure`, `effect`, `reconciliation` | move semantics to the owning reliability child |
| `research_platform.resource.core` | `resource/catalog`, `allocation`, `resolution` | remove generic resource catch-all ownership |
| `research_platform.runtime.host.bootstrap` | `runtime/host` | make host bootstrap a host composition/provider boundary |
| `research_platform.runtime.process.capture` | `runtime/process` and `observability/capture` | separate process truth from observation capture |
| `projects.sem_paper.method.self_evolving_memory` | project-owned `projects/sem_paper/method/self_evolving_memory`, registered through `scientific/implementation` and `scientific/method` | connect project/method production root before deleting the top-level `methods` namespace |

## Production entry and composition roots

The current graph has real entry points for release, architecture gates,
operator maintenance, tmux/runtime commands, environment commands, model
management, method event handlers, and platform composition. It does not yet
show one unambiguous production root that binds:

`ProjectDefinition -> scientific method -> participant binding -> experiment /
run -> environment/runtime -> model request -> effect/evidence -> telemetry /
diagnostics`.

The first executable migration slice must establish this root through explicit
composition, then delete direct method-local construction paths. Project
composition under `projects/sem_paper/composition/` now provides an explicit
Paper-1 binding root, but no platform host caller has been confirmed yet. The
remaining gap is host wiring from the project contract into the experiment/run
path, not the ownership of the scientific method.

## Required audit artifacts

For each row above, the migration log must record:

1. target node and owner;
2. source files and current entry points;
3. CodeGraph dependency/caller/impact evidence;
4. target API/runtime/provider/composition design packet;
5. rewired callers and focused checks;
6. deletion-gate scan and physical deletion revision.

The matrix is intentionally incomplete at the file level until the automated
ownership scan is regenerated from the current worktree. It is a control
document, not a substitute for source evidence.

## Next slice design packet: Paper-1 project composition

### Owner and interfaces

`projects/sem_paper/composition/project.py` is the Paper-1 project composition
root. It receives only:

- `research_platform.participant.method.api.MethodCompositionPorts`;
- `research_platform.observability.logging.api.LogSinkPort`;
- a Paper-1 `SessionServingFactory`;
- an explicitly selected Paper-1 `SessionEvolutionFactory` and provider id.

The returned binding record contains the project definition, the project-owned
logging sink, and the two method endpoints. It does not expose a platform
provider catalog or a generic service locator.

### Dependency direction and data flow

```text
platform API/ports
        -> sem_paper composition root
        -> sem_paper method implementation/runtime
        -> MethodEndpointPort
```

The platform port objects enter once at composition time. The method runtime
receives its observation-outbox port through `MethodCompositionPorts`; the
logging policy receives `LogSinkPort`. Scientific mutation/evolution remains
inside the Paper-1 method and is not moved into the platform.

### State, side effects, and failure semantics

Composition is pure binding: it opens no session, writes no scientific state,
starts no model/server process, and performs no Minecraft action. A missing
self-evolution factory or blank provider identity is rejected at composition;
method execution failures remain method/runtime failures and are not converted
into a generic project success.

### Verification

The focused project test must prove that custom logging and method ports are
injected through the project root, that fixed and self-evolving treatments are
both bound, and that the project API firewall has no concrete-platform import.

## Concrete scientific implementation placement

`research_platform.scientific` owns reusable method identity, configuration,
registration, lifecycle and provider contracts. A concrete paper or project
owns its implementation under its project namespace:

```text
research_platform/scientific/       # generic scientific authority
projects/sem_paper/method/          # concrete Paper-1 implementation
projects/another_project/method/    # another independently replaceable method
```

The retired top-level `methods/` namespace is not replaced by a generic
platform import path. Project composition binds its own implementation to the
Scientific/Participant APIs, while the platform discovers only the declared
project contract. This prevents a future project from becoming a hidden
platform dependency.
