# Global architecture and Paper-1 implementation audit — 2026-08-23

## Status

This is the consolidated audit and remediation record for the current
development worktree. It does not claim a live Minecraft run, a model result,
a server deployment, or a completed final-architecture migration. Structural
remediation batches recorded below do not substitute for execution evidence.

The audit combines two scopes that must be repaired together:

1. the final recursive platform architecture; and
2. the current Paper-1 self-evolving-memory production path, which must run on
   both Minecraft and a non-Minecraft environment through the same generic
   base contracts.

## Audit evidence

The following read-only checks were executed against the current tree:

| Check | Result | Interpretation |
|---|---:|---|
| Registered recursive catalog nodes | 182 | The declared topology is broad and structurally complete. |
| Standard node shapes present | 182/182 | Directory shape exists; this is not proof of implementation. |
| Deepest-owner inventory: declaration-only | 81 | These nodes still contain only declarations/skeletons under the recursive leaf audit heuristic. |
| Deepest-owner inventory: thin | 12 | These nodes have only one meaningful implementation file. |
| Deepest-owner inventory: substantive | 60 | Substantive files exist, but wiring and production ownership still require proof. |
| Internal import edges | 3,445 | Used for static dependency inspection. |
| Package cycles | 0 | No package-level cycle was found. |
| Existing architecture checks | 0 findings in all six checks | Existing gates are clean but do not cover the gaps below. |
| Python/bridge syntax compilation | Passed | Current edited tree is syntactically compilable. |

The six zero-finding checks are import rules, source invariants,
cross-subsystem concrete dependencies, declared system dependencies, public
facades, and typed capability-composition boundaries. They are necessary
guards, not a production-completeness proof.

The packaged `catalog.json` and the runtime descriptor fields currently agree
exactly. The remaining authority concern is architectural: structural topology
and capability metadata are assembled from `_SYSTEM_TOPOLOGY`, `_NODE_METADATA`,
and packaged catalog semantics in
`research_platform/governance/system_registry/api/topology.py`. This is
consistent today because drift is checked, but it is still a split declaration
surface rather than one generated source of truth.

The report-only audit is executable at
`scripts/sem_paper_architecture_audit.py`. It recursively identifies catalog
leaves while ignoring the standard `api/runtime/providers/composition`
implementation layers, and it checks the actual `build_runtime(...)` call
instead of matching an optional function signature. The pre-slice machine-
readable result was `blocking_open=13`; after the run-parent slice below the
generic run bypass is expected to close. The qualified model closure call
chain is structurally closed, while the topology and Paper scientific/runtime
findings remain open until their live owners are migrated and server-verified.
The
opaque-payload subscan currently reports 54 contract-level occurrences after
excluding implementation-only `object.__setattr__` calls; the full API tree
still contains broader `object` use that requires semantic classification.

## Consolidated findings

### A. Topology and ownership

#### A1. Directory topology is ahead of real ownership

The catalog creates the expected `api/runtime/providers/composition` shape for
all nodes, but 81 deepest registered nodes do not own a meaningful
implementation. The final migration contract requires a node to progress
through `declared -> implemented -> wired -> verified -> retired`; directory
creation alone cannot advance that state.

#### A2. Production ownership still sits in coarse or unregistered owners

The deepest-owner inventory still assigns substantial real code directly to
coarse roots, including:

- `execution`: decision, lifecycle, participant operations, and runtime-manager
  implementation remain beside the declared leaf topology;
- `platform`: kernel and a large multi-domain composition surface remain under
  one root;
- `experimentation`: evaluation implementation is outside the declared
  branch/run/study leaf ownership;
- `participant`: the old `core` surface remains a large shared owner;
- `runtime`: shared service/runtime files remain beside the leaf system
  topology.

These are not merely empty parents. They are still live owners and therefore
the old architecture has not reached zero residual ownership.

#### A3. Existing gates do not prove owner completeness

The current gates detect forbidden dependency forms, but do not answer:

- which catalog node owns every production file;
- whether every declared authority has a real implementation;
- whether every production entry point targets the catalog topology;
- whether an old owner can be physically deleted after migration;
- whether a project capability declaration is fully bound in its actual plan.

The next governance slice must add these as first-class audit outputs rather
than treating a clean import graph as migration completion.

### B. Composition and interface boundaries

#### B1. Capability closure was false and is now fail-closed for the current surface

The initial audit found eight declared system capabilities but only two frozen
composition requirements. The current source now removes the six unbound
claims and adds a composition assertion that the project definition and plan
must have the same capability set. This closes the false-positive declaration
for the current surface. It does not authorize adding the six future
capabilities back as labels: each one must return only with a real offer,
injected Interface, and production call-chain evidence.

#### B2. The Paper operator is still a wide composition root with its own platform

The real outer composition remains in
`scripts/run_sem_minecraft_experiment.py`. The attempted relocation into a
project/operator or platform/operator owner was reverted because the
architecture firewalls correctly identified that it would move concrete
diagnostic, error, host, route and external-service authorities across system
boundaries. The script is still over 1,000 lines and
directly owns or assembles input/path resolution, service environment construction, model
prompt/request/endpoint wiring, MC host wiring, diagnostics, manifest output,
result output, cleanup output, and logging export. It also imports concrete
providers. Concrete provider selection is valid at an outer composition root,
but this root is too wide to be a reusable project interface and still mixes
operator parsing, run identity, lifecycle, scientific publication and provider
construction in one file.

The required end state is a thin project operator that loads an immutable
project/run specification and invokes one platform composition port. Project
policy remains project-owned; storage, diagnostics, path, model qualification,
and run lifecycle implementations must not remain scattered in the operator.

#### B3. Narrow interfaces are not yet strong enough

The platform API tree contains 208 occurrences of `object` across 70 API files.
The most consequential examples are participant session/services, experiment
task/input payloads, MC branch/session lifecycle, diagnostics, and forensics.
These are catch-all seams, not typed replaceable interfaces. They hide the
actual dependency graph and make non-MC substitution difficult to verify.

The remediation must replace the highest-leverage catch-all ports with typed
contracts. `object` may remain only where the contract explicitly declares an
opaque payload and separately freezes its identity, schema, and codec.

#### B4. API/implementation separation still needs a physical audit

Several API packages contain executable or stateful-looking contract surfaces,
including method observation delivery seams, participant lifecycle/checkpoint
operations, and broad endpoint services. Each must be classified as one of:

- pure contract `Interface`;
- owning `Implementation` under its node runtime/provider;
- a composition-only `Adapter`.

The final migration cannot rely on package names alone. It must inspect the
actual write, lock, process, and lifecycle behavior and move it to the owning
node before deleting the old surface.

### C. Generic experiment and environment reuse

#### C1. Generic experiment infrastructure had two competing orchestration surfaces

The repository had a participant-centric `ExperimentSpec`/`RunCoordinator`
surface and a newer `ExperimentRunSpec`/`StudyMatrix`/generic-workload surface.
The Paper entrypoint used the latter pieces but let each environment root own
study assignment expansion and publication. That left two real orchestration
authorities even though both were called generic.

The concentrated run-parent slice now places `ExperimentRunApplication` under
`experimentation/run`. It validates the immutable run/protocol identity,
composes the direct Study child, owns assignment expansion, matrix execution
and study publication, and returns a run-owned result envelope. MC and non-MC
roots receive only `ExperimentRunExecutionPort` plus a unit adapter. The old
participant-centric runtime remains an explicitly tracked migration surface;
it is not silently declared equivalent to the new run parent.

#### C2. The current workload is SEM-specific, not a reusable MC harness

`projects/sem_paper/composition/minecraft_workload.py` couples one Module to:

- `MinecraftTaskSpec` and Minecraft success predicates;
- `MethodSession` and `RecallRequest`;
- `memory_context` retrieval;
- MC state shape, action vocabulary, task anchors, and evidence admission.

This cannot serve a non-open-world environment without cloning the whole
runner. The reusable base must own a generic task graph, action/observation
cycle, completion evaluator, evidence sink, diagnostics port, and checkpoint
port. Minecraft and non-Minecraft environments must implement only their
environment `Adapter` and action/state contracts. SEM must provide the method
strategy through an injected `Interface`.

#### C3. MC runtime currently leaks Paper semantics

`research_platform/environment/minecraft/runtime/session.py` owns
`begin_task/end_task`, `task_event`, active task metadata, goals, task lineage,
and anchors. It also injects those fields into action payloads. The MC bridge
contract simultaneously describes bridge envelopes as architecture-neutral and
free of task/memory/evolution fields. These two contracts are inconsistent.

The environment Module may carry generic correlation and opaque caller
metadata, but it must not understand SEM goals, lineage, anchors, treatment, or
memory channels. Those belong to the project workload Adapter and evidence
composition.

#### C4. Hidden capability downgrade in entity observation

If a bridge does not declare `observe_entities`, the MC session silently emits
an acknowledged empty result with `bridge_capability_not_declared`. Entity
observation is part of the state used by success/evidence logic; silently
skipping it is a correctness downgrade. The capability must be explicit in the
bridge contract and either be implemented or fail closed with a typed cause.

### D. Data, diagnostics, and lifecycle authority

#### D1. Multiple output authorities remain in the Paper entrypoint

The entrypoint directly writes `events.jsonl`, `metrics.jsonl`,
`failures.jsonl`, `method_observations`, `run_manifest.json`, `result.json`,
`cleanup_failure.json`, and `logs.json`. This creates a parallel project-local
record plane beside platform observability, telemetry, reliability/forensics,
artifact content, and run-manifest systems.

The target design has one owner for each durable truth domain. Project policy
may enrich records through a logging/evidence `Interface`, but it may not own a
second persistence authority for failures, run state, or platform logs. The
run runtime now owns atomic publication of manifest, preflight, result,
cleanup, and log artifacts through `RunArtifactStorePort`; model request blobs,
method observations, and evidence exports still need to move behind their
own platform artifact interfaces.

#### D2. Diagnostics are improved but not crash-durable platform evidence

The current Paper diagnostic adapter records timestamps, sequence, traceback,
and cause chains. That is useful evidence, but it remains a local JSONL
implementation and uses an in-memory logging store until final export. It is not
the platform forensic ledger, does not provide exact crash resume, and does not
join every record to a frozen run/checkpoint identity.

#### D3. `J_eval` is exported but not populated

`EvalEvidenceStore` is created in the Paper workload binding and exported on
close, but the current ingest path appends audit evidence and never appends an
evaluation row. The resulting `J_eval` file can be structurally present while
scientific evaluation evidence is empty. The audit must reject this state as
incomplete rather than treating export existence as evidence completeness.

#### D4. Failure scope is not explicit

`MinecraftWorkloadBranchExecutor` converts `MinecraftWorkloadFailure` into a
failed task and continues with later tasks. That is only valid for a local task
failure. A bridge disconnect, environment state loss, unreconciled effect, or
failed cleanup can invalidate the entire branch. The generic execution system
needs a typed failure-scope policy distinguishing task, participant, branch,
run, and host failures; no implicit continuation may cross a wider scope.

#### D5. Generic checkpoint/resume is not wired into this production path

The platform has checkpoint contracts, but the current Paper production root
does not create a durable run checkpoint store or expose an exact resume entry
point. A process interruption therefore cannot resume the current paired
workload from a verified joint cut and method/environment state.

### E. Model, environment, and path binding

#### E1. Planner identity is now consumed through a qualified closure

The Paper planner now consumes a platform-published qualified deployment
closure. The reader reconstructs the model/deployment/route/runtime-qualification
objects and validates their identity before the MC host is opened. The endpoint
uses the qualified route timeout rather than an operator override. The closure
reader receives its durable store implementation through an injected factory.
The remaining limitation is operational: a real closure file and a live
qualification receipt still must be produced by the model-serving system before
baseline execution is scientifically eligible.

#### E2. Paper still owns path and process resolution

The entrypoint still resolves repository-relative paths, output layout,
Node/Java executables, server paths, ports, and environment variables. It now
uses the platform resource-resolution Interface for normalized paths and
executables, but the operator script remains a wide composition root and must
be reduced to a typed project/run-spec facade.

#### E3. Live evidence is still absent

The current source contains the host/branch/planner composition needed for a
live path, but no server-backed baseline, smoke ladder, full paired study, or
model qualification proof is claimed by this audit. Structural tests cannot
replace those execution proofs.

### F. Paper scientific completeness

The following are still scientific implementation gaps, not merely platform
gaps:

1. the live entrypoint requires an explicitly injected evolution factory, but
   the real Meta/Evolver stage providers and their session-scoped adoption/live
   serving authority are not yet composed;
2. the current model-backed comparison is control versus a static Seed-X
   candidate, not the full registered baseline matrix;
3. a concrete Meta Architect, RuleBased Evolver, candidate proposal pipeline,
   candidate gate, and adoption/activation path are not connected to the live
   workload;
4. Core-6, independent repetitions, statistical aggregation, full ablations,
   external baselines, and budget-tier execution are not connected to the
   production root;
5. the current claim gate correctly refuses to call the partial path a full
   scientific result, but a refusal is not an implementation.

Previously completed structural work—task graph validation, source/world-cut
composition, branch identity split, candidate materializer, strict planner
response handling, evidence timestamps, and branch cleanup—must be retained
and verified again after the generic-base migration. They must not be rebuilt as
parallel project-local systems.

## Unified remediation contract

The next implementation batch follows this hierarchy:

| Architecture term | Required decision |
|---|---|
| Module | Generic experiment/run, task graph, evidence, diagnostics, model binding, path/environment, and MC host responsibilities each receive one catalog owner. |
| Interface | Projects consume only typed public contracts; opaque payloads carry an explicit schema/digest/codec. |
| Implementation | Concrete JSONL, filesystem, Mineflayer, Java, vLLM/SGLang, and server providers remain behind their owning runtime/provider node. |
| Depth | A parent composes only direct children and exports a smaller facade; no parent reaches into a grandchild. |
| Seam | Synchronous hot-path calls use injected ports; observations use the event/record plane; commands use typed command/query ports. |
| Adapter | MC and non-MC implementations translate their environment-specific action/state formats at the environment seam, never inside SEM or generic orchestration. |
| Leverage | Fix the generic run/evidence/failure contracts once so every later project inherits durable behavior. |
| Locality | Project-specific treatment, memory semantics, prompts, and scientific acceptance remain in the project composition/method Module. |

The single source of truth must be a machine-readable topology/authority
document from which runtime descriptors, package-shape checks, owner mapping,
and documentation mirrors are generated or verified. A clean mirror is not a
second authority.

## Concentrated migration order

1. Freeze the owner matrix and add audits for deepest owner, production entry
   points, declared-capability closure, API object seams, and deletion readiness.
2. Introduce and wire the generic experiment/task/evidence/failure/checkpoint
   interfaces. Make the Paper root use them before any scientific run.
3. Move Paper diagnostics, manifest, model qualification binding, path layout,
   and result persistence behind platform interfaces; reduce the script to an
   operator facade.
4. Remove task/memory/evolution semantics from the MC runtime and bridge;
   provide a generic correlation/effect seam and MC/non-MC adapters.
5. Populate `J_eval`, add explicit failure-scope policy, and connect the
   durable checkpoint/resume path.
6. Connect the real SEM evolution and registered scientific protocol only after
   the shared runtime is correct; then add the complete baseline and study
   matrix.
7. Migrate coarse owners into recursive leaf nodes, verify all callers and
   gates, and physically delete the retired owner/entry/compatibility paths.
8. Only after source and server verification, perform the server-first
   baseline -> smoke -> full experiment ladder.

No step may introduce a generic service locator, a hidden fallback, a second
durable truth store, or a project-specific copy of a reusable platform
Implementation.

## Batch 1 outcome

The first concentrated remediation batch has landed without starting a live
experiment:

- task dependency ordering, cycle detection and execution-cut closure are now
  implemented by `experimentation.experiment.api.tasks`; the Minecraft task
  object only translates its MC-specific success/script fields into this
  generic identity;
- `experimentation.experiment.api.failure` now defines failure scope as a
  reusable runtime contract; MC workload failures that can invalidate branch
  state escape the task loop and trigger branch cleanup instead of being
  reported as an ordinary failed task;
- the Paper binding now has a typed evaluation-evidence seam and records a
  `J_eval` row for every completed or task-scoped failed task.
- append-only JSONL diagnostics, sequence allocation, exception-chain capture
  and fsync are now owned by the experimentation run runtime; the Paper
  script consumes `RunDiagnosticsPort` instead of implementing that provider.

These changes close only the first high-risk runtime gaps. The project
capability mismatch was subsequently made fail-closed by aligning the current
declaration with the two real composition edges. They do not close generic
`ExperimentSpec` production wiring,
MC semantic leakage, platform-owned persistence, qualified model/path binding,
or the scientific protocol gaps listed above. Those remain explicit blockers
for the next batch and no full-result claim is permitted.

## Completeness matrix after the first workload migration slice

The following matrix is the current worklist. “Implemented” means a real
Module/Implementation exists; “wired” means the current Paper call graph uses
it; “verified” means source and focused contract checks pass. A declaration or
an old v034 report is not evidence of completion.

| Surface | Module owner | Status | Evidence / remaining work |
|---|---|---|---|
| Recursive topology and owner registry | `governance/system_registry` | Partial | 182 nodes and six structural gates exist; topology metadata remains split and coarse live owners remain. |
| Generic task graph | `experimentation/experiment` | Implemented / wired / source-verified | `ExperimentTaskSpec` is the identity and dependency authority; MC manifests translate into it. |
| Generic run parent | `experimentation/run` | Implemented / MC-wired / non-MC-wired / server verification pending | `ExperimentRunApplication` owns assignment expansion, Study Matrix execution and publication; roots receive only `ExperimentRunExecutionPort`. |
| Generic failure scope | `experimentation/experiment` + `experimentation/workload` | Implemented / MC-wired / source-verified | The generic runner receives an explicit `WorkloadFailurePolicyPort`; MC currently classifies execution faults as branch-invalidating. A richer task/participant policy remains for later adapters. |
| Generic workload loop | `experimentation/workload` | Implemented / MC-wired / source-verified | The platform owns recall/decision/action/completion sequencing and boundary injection; MC supplies adapters. Non-MC production composition remains. |
| Generic environment ABI | `environment/runtime` | Implemented / partially wired | Observation/action contracts exist; payload schema still requires adapter-owned schema/digest evidence. |
| Paired evaluation | `experimentation/evaluation` | Implemented / Paper-wired | Receipts and comparability are shared; durable evaluation publication and general branch runner remain. |
| Project capability closure | project composition + governance planner | Closed for current surface / expansion pending | The project definition now declares only the two capabilities actually frozen by its plan; future experiment, measurement, capture, forensics, artifact, and state capabilities must be added only together with real offers and runtime use. |
| Diagnostics | `experimentation/run` | Implemented / Paper-wired | Append/sequence/exception-chain logic and event/metric/failure paths now use the run artifact interface; platform forensic ledger and full identity join remain. |
| Run manifest and path authority | `experimentation/run` + `resource/directory` | Partially wired | Manifest/preflight/result/cleanup/log and Paper evidence publication now use `RunArtifactStorePort`; model/method paths and host input resolution remain in the entrypoint. |
| Durable checkpoint/resume | `experimentation/checkpoint` | Implemented / seam-wired / Paper runtime optional | A workload-level store/coordinator now binds environment + method payloads to one task execution cut; MC exposes both component adapters and an explicit batch cut observer. The production root still needs an authoritative checkpoint provider and operator resume entry. |
| Model qualification closure | `model/qualification` + `model/deployment` | Partial / fail-closed | Strict response/deployment identity and a persisted-closure provider exist; baseline composition now rejects a missing binding before host construction, but the operator entrypoint still does not load and inject the persisted closure. |
| MC environment isolation | `environment/minecraft` + `resource/allocation` | Partial | Branch endpoint split and cleanup exist; durable host-scoped leases and a complete host caller remain. |
| MC semantic isolation | `environment/minecraft` | Partial | Active Paper task metadata was removed from MC session/action payloads and undeclared entity observation now fails closed; generic task-boundary API and remaining bridge payload review remain. |
| Non-MC environment seam | `environment/runtime` + project adapters | Implemented / source-verified | Paper now has a typed non-Minecraft production composition over the same generic task/batch runner; no scientific non-MC result has been run. |
| J_eval | Paper evidence adapter + `experimentation/run` | Implemented / partially wired | Per-task rows are created on the binding and published through the run-artifact Interface; full platform evaluation artifact and metric schema remain. |
| Deluxe live evolution | Paper SEM method | Not wired | Live script still selects `DisabledSessionEvolutionFactory`; stage providers are not composed into the live path. |
| Candidate materialization | Paper composition | Implemented / structurally verified | Candidate-specific typed Deluxe session is built; it is not driven by a real proposal/adoption cycle. |
| Scientific protocol | `experimentation/study` + Paper composition | Partial / matrix-wired | Frozen variants, assignments, completeness-checked aggregation, artifact publication, and a reusable repetition-group matrix executor are used by both MC/non-MC roots; the current protocol is still one control/treatment pair and the full Core-6/baseline/ablation matrix is not declared. |

The generic workload change is a `Leverage` improvement: it removes the
duplicated execution `Implementation` from the Paper Module while retaining
MC-specific state, action, completion, and evidence behavior in `Adapter`s.
Rows marked partial or not wired remain blocking.

## Batch 2 outcome — generic workload execution seam

The reusable workload loop now lives under
`research_platform/experimentation/workload`. It owns task lifecycle ordering,
method recall, planner decision transport, action identity, observation
ingestion, completion invocation, metrics, and typed failure scope. Its public
interfaces are environment-neutral; state projection, action vocabulary,
completion predicates, evidence adaptation, and planner policy are injected.

`MinecraftWorkloadRunner` is now only an MC `Adapter` over this platform
`Implementation`. The MC module retains success predicates, state projection,
action translation, and evidence translation, but no longer owns a second
task loop. This closes the direct MC/non-MC reuse violation in C2. The non-MC
Paper composition and the remaining capability/run/checkpoint/scientific
bindings are still open; no execution claim is made.

## Audit checkpoint — concentrated gaps to repair before scientific execution

The source was re-audited after the generic workload slice. The following is
the frozen repair list; a clean syntax check does not close any of these rows.

| ID | Seam | Direct evidence | Classification | Required repair |
|---|---|---|---|---|
| G1 | Workload/environment boundary | The generic runner previously called `begin_task/end_task` on the environment port. | Boundary violation | Keep task-boundary evidence in an injected workload boundary Adapter; the generic environment port exposes only observe/act. |
| G2 | Failure attribution | Generic runner assigned `BRANCH` for every initial-observe, decision, action, completion, and end error. | Hidden policy | Inject a typed failure-scope policy and make invalid policy output fail closed. |
| G3 | Evidence persistence | `projects/sem_paper/composition/minecraft_binding.py` wrote `j_audit`, `j_eval`, and the evidence manifest directly through `Path.open/write_text`. | Duplicate storage owner | Publish evidence through the platform run-artifact Interface; project code may only construct records. |
| G4 | MC task semantics | `environment/minecraft/runtime/session.py` stored active task metadata and copied goal, task lineage, and anchors into action payloads. | Environment owns Paper semantics | Remove active Paper metadata from MC session; retain only generic task correlation and boundary status. |
| G5 | MC capability truth | Missing `observe_entities` was converted into an acknowledged empty result. | Silent capability downgrade | Require an explicit bridge capability and raise a typed environment failure when absent. |
| G6 | Paper root | `scripts/run_sem_minecraft_experiment.py` still resolves host paths/processes and operator-declared model identity, and does not construct the generic run/checkpoint coordinator. | Composition-root overreach | Move path/model/checkpoint binding behind platform Interfaces and reduce the script to an operator facade. |
| G7 | Generic non-MC production | The non-MC Paper root now binds the same generic workload batch and study matrix through typed environment/planner/state/completion/evidence seams; no concrete closed-world provider is bound in the production entrypoint. | Adapter seam exists; provider absent | Bind a real non-MC environment implementation through the existing unit/assignment contract and verify paired initial-state reproducibility. |
| G8 | Resume authority | `experimentation/checkpoint` remains participant-centric and is not bound to the paired MC branch cut plus method snapshot. | Incomplete recovery contract | Add one Paper-independent paired-workload checkpoint seam carrying world cut, environment generation, method snapshots, and task execution cut. |
| G9 | Model qualification | `_build_planner` consumes the strict binding when present, and baseline composition now fails before host construction when it is absent; the entrypoint still has no persisted-closure loader/injection. | Provider exists; production composition absent | Load the persisted platform qualification/deployment closure through the model-serving provider and inject it before runtime construction. |
| G10 | Evolution treatment | The live root no longer constructs a disabled provider, but its operator call does not yet supply a real `SessionEvolutionFactory`; production composition now fails closed at that seam. | Scientific path absent / fail-closed | Port and compose the real Meta/RuleBased/Deluxe stage providers through the current typed evolution ports and one session-scoped adoption/serving authority; do not use the disabled provider for the treatment. |
| G11 | Scientific protocol | The frozen protocol, deterministic assignments, completeness checks, aggregation, publication, and MC/non-MC matrix adapters are connected; the protocol still declares only one control/treatment pair and one repetition. | Partial protocol | Declare and bind Core-6, ablations, external baselines, budget tiers, repetitions, and their environment-specific adapters without silently collapsing variants. |
| G12 | Recursive owner migration | Catalog shape is complete but 81 deepest nodes are declaration-only and coarse roots remain live owners. | Migration incomplete | Create an owner matrix, migrate live files to leaf owners, verify callers, then delete retired roots and compatibility paths. |
| G13 | Contract precision | Generic/environment APIs still use intentional but broad opaque payloads and several `object` return types. | Weak seam | Replace highest-leverage payloads with schema-id/digest/codec-bearing contracts; retain opaque values only where the codec is explicit. |

G1–G5 are now structurally repaired in source: the generic runner has an
injected boundary Adapter and failure policy, run evidence uses the artifact
Interface (including method-observation append records), MC task metadata is
no longer copied into action payloads, and missing entity capability fails
closed. These changes are source-level and
focused-contract-level only; no live run or scientific result is claimed.
G6, G7, G9, G10, G11, G12 and G13 remain blocking. G8 now has its generic
workload seam and MC adapter, but the current composition still lacks an
authoritative Minecraft world checkpoint provider and resume operator path;
it therefore remains blocking for execution.

## Batch 3 outcome — generic batch and non-MC seam

The platform now owns both the per-task loop and the ordered batch executor in
`research_platform/experimentation/workload`. The batch executor owns
dependency blocking, task-scoped continuation, binding cleanup, result
aggregation, and typed close failure; a binding Adapter supplies the domain
runner and result/evidence projection. The Minecraft branch executor now only
adapts its MC binding to this batch Interface.

A closed-world/non-MC contract test runs the same generic batch executor with a
non-Minecraft environment, planner, state projection, completion predicate,
method, and evidence Adapter. This is a source-level substitution proof, not a
claim that a scientific non-MC benchmark has been run. A concrete Paper
non-MC experiment manifest and provider remain part of G7/G11.

## Batch 4 outcome — joint workload checkpoint seam

The participant-centric checkpoint implementation is no longer the only
checkpoint contract. `experimentation/checkpoint/api/workload.py` defines a
workload checkpoint as the product of one run/study/workload/branch identity,
one task execution cut, and a unique set of codec-labelled component payloads.
`DirectoryWorkloadCheckpointStore` reuses the existing content-addressed blob
authority and adds only a workload manifest namespace. The coordinator rejects
identity, codec, generation, source-cut, task-manifest, and component-topology
drift before restore.

The MC Paper binding now exposes the environment session checkpoint and the
method snapshot through two explicit adapters. `GenericWorkloadBatchExecutor`
can notify an injected execution-cut observer after each committed task, and
the MC branch adapter can publish those cuts through the workload checkpoint
coordinator. This is a structural and import/contract verification result;
the current MC composition does not yet provide an authoritative world
checkpoint provider or an operator resume command, so no live recovery claim
is made.

The next blocking scientific issue is intentionally not hidden: enabling a
pipeline factory alone would still be incorrect because the current SEM live
Deluxe serving source is fixed to Seed-C while the adoption aggregate and
candidate materializer are separate authorities. The evolution treatment must
first share one session-scoped architecture/adoption source and switch the
serving projection only after atomic adoption; a dummy active pipeline would
be a false implementation and is therefore not being introduced.

## Batch 5 outcome — resource, study and model-binding seams

The next concentrated batch repaired three reusable boundaries and made one
scientific downgrade impossible:

- `resource/resolution` now exposes an immutable named path/executable binding.
  The Paper entrypoint resolves its run paths and Node/Java tools through that
  Interface instead of carrying a second `_resolve_executable` and scattered
  path-normalization policy. The resolver is side-effect free; it does not
  start processes or install packages.
- `experimentation/study` now owns a frozen variant/repetition/seed/metric
  protocol, deterministic assignment expansion, and basic mean/variance
  aggregation. This is the reusable contract that Paper must bind before a
  full baseline/ablation/repetition claim can be made.
- The Paper composition now has a real non-Minecraft workload Adapter over
  the same `GenericWorkloadBatchExecutor`. Its environment, planner, state,
  completion, evidence and result ports are typed injection points; no MC
  state or action vocabulary is copied into the closed-world path.
- The model endpoint API now has a `QualifiedModelEndpointBinding` contract.
  The model-backed Paper planner refuses to start without this binding and no
  longer accepts operator-declared revision/engine/dtype fields as scientific
  identity. A future platform composition must supply the binding from the
  persisted deployment and runtime qualification closure.

These changes are source-level and focused-contract-level only. The baseline
entrypoint is intentionally fail-closed until a qualified endpoint binding is
composed. No model, server, Minecraft, or scientific run is claimed.

## Remaining blocking findings after Batch 5

The full audit is not complete merely because these seams exist. The remaining
blocking work is:

1. the Paper project operator still owns the outer CLI/environment policy and
   must be reduced to a thin facade that loads a frozen project/run spec;
2. the generic `experimentation/run` participant-centric coordinator remains a
   separate legacy orchestration surface from the generic workload executor;
3. the qualified binding has an API contract but no production provider that
   loads the server-side qualified deployment closure;
4. the workload checkpoint seam still lacks an authoritative MC world/session
   checkpoint provider and resume operator path;
5. the SEM serving projection and the atomic adoption aggregate still need a
   shared session-scoped architecture authority before real evolution can be
   enabled;
6. the Paper production roots now bind `StudyProtocol` to the reusable
   `StudyMatrixExecutor` through MC and non-MC `StudyUnitExecutionPort`
   adapters. The current protocol still declares only one control and one
   treatment variant with one repetition; Core-6, external baselines,
   ablations, and repeated statistical runs remain intentionally unbound;
7. 81 catalog leaves remain declaration-only and coarse roots remain live
   owners; physical owner migration and deletion are still pending;
8. the broad opaque payload inventory (54 contract-level occurrences in the
   current selected API subscan, plus broader API-tree uses) still requires a
   staged, schema/codec-bearing replacement audit.

## Audit round after Batch 5 — concrete call-chain review

The second audit did not treat the existence of a port as proof that the
production call graph uses the port correctly. It followed both the MC and
non-MC workload paths from treatment selection through task execution and
artifact publication. This exposed the following additional defects:

| ID | Evidence | Root cause | Required repair |
|---|---|---|---|
| P14 | `SemPaperNonMinecraftWorkloadBinding` always opened `composition.bindings.fixed_memory`, even for a candidate role. | The first non-MC adapter copied the generic loop but omitted the project treatment-selection seam. | Select control through fixed endpoint and treatment through the candidate materializer, with no fallback. |
| P15 | `StudyProtocol` and its services existed only as isolated contracts/tests. | The Paper production root did not freeze the protocol or expand assignments. | Make protocol, assignment expansion, aggregation, and publication required production-root dependencies. |
| P16 | The root generated branch receipts but no platform study observation/aggregate artifacts. | The script remained the second scientific record authority. | Publish protocol, observations, and aggregates through `experimentation/study` over `RunArtifactStorePort`. |
| P17 | The current SEM adapter accepts one control and one treatment variant but the protocol can declare multiple variants of the same kind. | The paired adapter cannot represent a larger matrix without silently dropping assignments. | Fail closed for the paired adapter; the platform matrix executor is now wired, and the remaining work is to declare and bind the full Core-6/ablation adapters. |

These findings are now repaired in source. They are structural repairs only;
no workload or experiment was run. The remaining audit is therefore about
authority migration, exact recovery, live qualified deployment loading, and
scientific treatment implementation rather than this already-verified
control/treatment selection path.

## Batch 6 outcome — protocol binding and cross-environment treatment correctness

- `SemPaperMinecraftProductionRoot` now requires and retains a frozen
  `StudyProtocol`, deterministic assignment port, metric aggregation port, and
  study artifact publication port. The task-manifest digest is checked against
  the generic `ExperimentTaskSpec` projection before the root is built.
- Both control and treatment variants are required by kind, not by a
  project-specific identifier. A one-pair execution rejects a protocol with
  multiple variants of the same kind instead of silently omitting a baseline
  or ablation.
- A reusable Paper study builder declares control/treatment identities and the
  metric schema without embedding Minecraft action semantics.
- The non-Minecraft Adapter now receives a study assignment and selects the
  control endpoint or candidate materializer by `VariantKind`. It cannot label
  a fixed method as a candidate, and it cannot fall back when candidate
  materialization is absent.
- `experimentation/study` now publishes protocol, observations, and aggregates
  through the run artifact Interface. The Paper script only translates branch
  receipts into typed study observations and invokes those interfaces.
- `experimentation/study` now also owns a reusable `StudyMatrixExecutor`: it
  groups exact assignments by repetition, delegates one complete repetition
  to an environment-neutral adapter, and refuses missing/duplicate assignment
  observations or incomplete metric schemas. This is a platform capability;
  it does not claim that the current MC entrypoint has executed the full matrix.

Validation after Batch 6: architecture gate passed, all changed Python files
compiled under the repository Python 3.12 interpreter, and focused manual
contract/import checks passed. The repository does not currently have `pytest`
available in that interpreter, so no pytest result is claimed.

## Remaining blocking findings after Batch 6

1. The Paper operator script still owns the outer CLI/environment policy and
   must become a thin facade over a frozen project/run specification.
2. The participant-centric `experimentation/run` coordinator and the generic
   workload executor remain two live orchestration surfaces; one must become
   the parent composition over the other before the old authority can be
   retired.
3. A provider now loads the qualified endpoint projection from a persisted
   deployment closure (`QualifiedDeploymentManifest`, route table, and live
   runtime qualification receipt). The Paper operator supplies this closure
   before host construction; a real closure artifact is still required at
   execution time, so model-backed execution remains intentionally fail-closed
   when it is absent.
4. Workload checkpoint capture still has no authoritative MC world provider or
   operator resume path. A client-state snapshot alone must remain rejected.
5. SEM evolution is still disabled: the session-local serving projection and
   atomic adoption aggregates have not been unified into one session-scoped
   architecture source with post-adoption serving projection switching.
6. The study system now has a completeness-checked matrix executor, and the
   Paper MC/non-MC roots delegate through environment-specific unit adapters.
   The complete Core-6/baseline/ablation/repetition matrix is not yet
   declared, so the current implementation remains a complete paired matrix,
   not the final scientific matrix.
7. The topology still has 81 declaration-only leaves and coarse roots remain
   live owners. Owner migration, caller verification, and deletion are not
   complete.
8. The API inventory still contains 54 selected contract-level opaque
   payloads/returns and broader object uses;
   the highest-leverage environment, method, run, and checkpoint seams need
   schema/codec-bearing contracts.

## Batch 7 outcome — qualified deployment closure and matrix completeness

- `model/serving/endpoint/providers/qualified_binding.py` now provides the
  missing read-side closure adapter. It requires a role manifest, exact
  qualified deployment manifests, endpoint routes, and a runtime qualification
  evidence store; it rejects deployment/route/stack/certificate/role drift
  before returning a `QualifiedModelEndpointBinding`. No readiness URL or
  operator-declared model metadata is promoted into scientific identity.
- Endpoint completion path and timeout are carried by the qualified binding,
  so the endpoint composition no longer silently replaces a qualified route
  with a default route policy.
- `BasicStudyMetricAggregator` now validates the complete deterministic
  assignment set and exact declared metric schema before calculating any
  aggregate. A missing repetition or metric is a hard error.
- `StudyMatrixExecutor` is a reusable platform runtime. It groups the frozen
  matrix into repetition units and delegates only environment/branch mechanics
  to an injected `StudyUnitExecutionPort`.

Validation after Batch 7: `ARCHITECTURE_GATE_PASS`, Python 3.12 syntax
compilation for the changed study/endpoint surfaces, a matrix executor
contract invocation, a qualified deployment closure invocation, and
`git diff --check` completed. The repository Python 3.12 environment still has
no `pytest`; no pytest, server, model, Minecraft, or scientific run is claimed.

## Batch 8 outcome — matrix execution moved behind the project interface

The Paper MC entrypoint no longer calls `PairedBranchEvaluator` directly. The
platform now supplies a `StudyMatrixExecutionPort`; the Paper MC root binds a
`SemPaperMinecraftStudyUnitAdapter`, and the non-MC root binds a
`SemPaperNonMinecraftStudyUnitAdapter`. The project packages import only the
study API/port surface; the concrete matrix runtime is supplied by the outer
composition root.

Each MC repetition creates a fresh source-cut runner, so a repeated study
cannot silently reuse one world cut. The MC adapter refuses to emit an
observation when paired comparability fails. The non-MC adapter passes the
full unit and assignment seed into the environment/planner seams, which is
the minimum contract needed for a future closed-world provider to reproduce a
paired initial state.

The machine audit now reports `STUDY_MATRIX_ADAPTER=closed` and the generic
architecture gate remains green. This closes the “matrix exists but the live
Paper call graph bypasses it” finding. It does not close the scientific
matrix requirement: the current protocol still declares one control, one
treatment, and one repetition; Core-6, external baselines, ablations, and
statistical repetitions remain a separate declaration/composition task.

## Batch 9–11 outcome — fail-closed treatment and qualified model composition

- Batch 9 removed direct construction of the disabled evolution provider from
  the production entrypoint. A candidate treatment now requires an explicitly
  injected `SessionEvolutionFactory`; this is a fail-closed boundary, not a
  claim that the real Meta/Evolver pipeline is complete.
- Batch 10 moved the baseline qualification check before MC host/service
  construction. Missing qualification cannot start a server and be discovered
  only after resource allocation.
- Batch 11 added the durable qualified-model-closure reader and injected the
  runtime-qualification store factory at the outer composition root. The
  Paper baseline resolves the planner binding from the closure before host
  construction and uses the closure's route timeout.

An attempted Batch 12 ownership relocation was deliberately reverted. The
project/operator and platform/operator placements violated the existing
system firewalls because they would have made a project or platform node own
MC host, diagnostic, error and external-service composition details. The
correct next step is interface extraction from the application entrypoint,
not moving the same concrete composition into another owner.

The machine audit currently reports twelve open blocking findings:

| Finding ID | Current evidence | Required end state |
|---|---|---|
| `PAPER_OPERATOR_ENTRYPOINT` | 1,048-line script, 24 functions, 29 environment reads | typed operator/run-spec facade |
| `SEM_EVOLUTION_PRODUCTION_BINDING` | production call permits no real evolution factory | real session-scoped evolution/adoption authority |
| `WORKLOAD_CHECKPOINT_RESUME` | generic seam exists; no MC provider/resume composition | authoritative MC world/session restore |
| `DECLARATION_ONLY_TOPOLOGY_LEAVES` | 81 of 182 registered leaves are declaration-only | leaf ownership migration and old-owner deletion |
| `OPAQUE_API_PAYLOADS` | 54 selected API payload sites use `object` | typed schema/digest/codec contracts |
| `PAPER_NON_MINECRAFT_EXECUTION` | only protocols/tests, no executable non-MC path | real non-MC adapter and entrypoint |
| `SEM_EVOLUTION_STAGE_BINDING` | `PipelineSessionEvolutionFactory` is never constructed by production code | all seven real stage providers wired |
| `SEM_SCIENTIFIC_MATRIX_COMPLETENESS` | two variants and one repetition; no Core-6/RuleBased/ablations | frozen confirmatory and comparator matrix |
| `SEM_SCIENTIFIC_METRIC_REGISTRY` | seven smoke metrics, no complete lifetime/edit/cost registry | typed full estimand and provenance registry |
| `MC_WORLD_CHECKPOINT_RESUME` | duplicate detailed checkpoint finding at MC adapter boundary | MC world provider plus typed resume operation |
| `LIVE_EXECUTION_EVIDENCE` | no closure artifact or T2B result in checkout | qualified model and live-world evidence |
| `TOPOLOGY_SINGLE_AUTHORITY` | topology is declared in both Python and JSON | one generated topology authority |

The typed `ExperimentRunSpec` is now present and used in the Paper manifest;
the remaining operator finding is the still-wide outer composition root. The
two evolution rows and two checkpoint rows are intentionally retained as
separate findings: one checks the project scientific authority, while the
other checks the generic/MC boundary where that authority must be composed.

The qualified model closure call chain, study matrix call chain, import graph,
cycle check, and existing architecture gates are structurally closed. A real
qualification artifact, model service, Minecraft server, non-Minecraft
environment, or scientific run has not been executed from this checkout.
