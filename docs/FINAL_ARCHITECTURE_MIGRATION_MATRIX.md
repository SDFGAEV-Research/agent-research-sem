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
| scientific | 6 | 0 | 0 | 6 | scientific production authority still lives under `methods/` |
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
| `methods.self_evolving_memory` | `scientific/implementation` and `scientific/method` | connect project/method production root before deleting local composition |

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
wrappers under `projects/sem_paper/composition/` currently wrap
`methods.self_evolving_memory.composition` but have no confirmed production
caller; this is a wiring gap, not evidence that the project layer is complete.

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
