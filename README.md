# Agent Research Platform

[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-active%20architecture%20migration-orange)](docs/status/CURRENT_DEVELOPMENT_BASELINE.md)
[![Scientific claims](https://img.shields.io/badge/scientific%20claims-live%20evidence%20required-red)](docs/projects/sem_paper/SEM_FINAL_RUNBOOK.md)

A contract-driven platform for building, running, recovering and auditing
long-horizon agent research.

The first research project is a self-evolving-memory agent evaluated in an
open-world Minecraft setting. The platform boundary is intentionally broader:
the same study, workload, method, model, runtime, evidence and recovery
contracts can also run against a deterministic non-Minecraft environment and
future environments.

This repository is designed for research that must remain:

- reproducible across projects, models, environments and servers;
- replaceable without hidden provider discovery;
- recoverable after process, host or network interruption;
- debuggable from a single run/task/action/failure identity;
- scientifically honest about the difference between plumbing, execution and
  claim-eligible evidence.

> Current release snapshot: 0.42.6.
>
> Current state: the recursive platform migration and SEM live-runtime hardening are active. Real Minecraft 1.21.8 source/branch execution and Qwen3.8 serving capability have been exercised, but the latest scripted smoke still fails closed and no full Core-6 scientific run is claimed. See `docs/status/CURRENT_EXECUTION_STATUS_20260828.md`.

Historical changes are intentionally kept out of this README; the current
development truth is maintained under `docs/status/`.

## Table of contents

- [Project scope](#project-scope)
- [Current status](#current-status)
- [Architecture in one page](#architecture-in-one-page)
- [Authoritative topology](#authoritative-topology)
- [The three execution planes](#the-three-execution-planes)
- [Recursive subsystem contract](#recursive-subsystem-contract)
- [System map](#system-map)
- [Runtime data flow](#runtime-data-flow)
- [Paper-1 SEM project](#paper-1-sem-project)
- [Minecraft implementation](#minecraft-implementation)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Server-first workflow](#server-first-workflow)
- [Recovery and resume](#recovery-and-resume)
- [Model and AI infrastructure](#model-and-ai-infrastructure)
- [Verification and release gates](#verification-and-release-gates)
- [Evidence and artifact model](#evidence-and-artifact-model)
- [Repository layout](#repository-layout)
- [Documentation map](#documentation-map)
- [Adding a project or provider](#adding-a-project-or-provider)
- [Security and data handling](#security-and-data-handling)
- [Known limitations](#known-limitations)
- [Contributing](#contributing)
- [License](#license)

## Project scope

### What the platform owns

The platform owns reusable execution and governance concerns:

1. composition and provider binding;
2. experiment identity, study protocols and variant plans;
3. workload execution and action/effect boundaries;
4. environment lifecycle and checkpoints;
5. model identity, deployment qualification and request envelopes;
6. server, process, virtual-environment and toolchain lifecycle;
7. logs, metrics, traces, diagnostics and evidence projections;
8. failure classification, recovery and effect reconciliation;
9. release manifests, architecture gates and source-tree invariants.

### What a research project owns

A project owns its scientific meaning:

- method semantics and memory architecture;
- task definitions and success predicates;
- method-specific prompts and model roles;
- candidate generation and scientific estimands;
- project-level provider composition;
- interpretation of results.

The generic platform does not import the SEM implementation to decide what memory
means. The SEM composition root imports platform ports and binds its own
method-owned implementations.

### What this repository is not

This repository is not:

- a generic service locator or mutable dependency container;
- a command bus that hides all calls behind strings;
- a collection of independent scripts with undocumented state;
- permission to claim a scientific result from a scripted planner or partial log;
- a fallback mechanism that silently changes model quality, context length,
  task budget or method behavior.

## Current status

The status below is deliberately split into engineering completion and
scientific completion. A green static gate is not a green live experiment. The detailed live server/model/Minecraft state is maintained in `docs/status/CURRENT_EXECUTION_STATUS_20260828.md`.

| Area | Current state | Meaning |
| --- | --- | --- |
| Recursive topology and leaf contracts | Implemented in the current migration slice | The catalog and architecture gates govern the migrated structure. |
| Composition graph and narrow runtime ports | Implemented and enforced in the migrated paths | Providers are selected at composition time; runtime code receives ports. |
| Durable session state | Implemented | WAL, checksums, primary/backup recovery, locking and observed-digest CAS are present. |
| Minecraft checkpoints and resume identity | Implemented as typed infrastructure | World state, projections, observations, action ledger and task boundaries are bound into checkpoint identity. |
| MC task manifest and study matrix | Declared and compiled | Six primary task families and the Core-6 protocol are represented in code. |
| Static architecture and contract validation | Recorded as passing in the checked-in validation artifact | This is source/regression evidence, not live MC evidence. |
| Real Minecraft live path | In active scripted-smoke hardening | Source server, world cut, branches, Mineflayer actions, evidence and checkpoints execute live; the current smoke still fails closed before claim eligibility. |
| Qwen3.8 model track | Asset complete; serving capability verified; scientific closure pending | Qwen3.8-27B is the primary track, but container-local health is verified, but the readiness evidence must still be published through the platform deployment/runtime qualification closure before baseline launch. |
| Real SEM evolution authorities | Not fully bound | Proposal, paired evaluation, adoption and reconciliation remain required. |
| SEM memory inside the live MC cognition path | Bound through the MethodSession composition | The current architecture audit verifies the cognition path uses the injected SEM method-session recall authority. |
| Scientific result | Not claimed | No live Minecraft result is currently eligible for a paper claim. |

The checked-in CURRENT_VALIDATION.json is a recorded development snapshot,
including architecture gates and contract audits; it does not replace rerunning
the current tree. Release evidence is regenerated from the current source
manifest and regression inventory by `scripts/generate_release_evidence.py`.

The checked-in `.local/t2b-gate/T2B_GATE_RESULT.json`, when present, is a
machine-local live-gate record and is not release evidence. A missing or stale
local record must not be used to claim or reject a qualified deployment.

The current managed Docker runtime now has the official Minecraft 1.21.8 server artifact, Java 21, Node 22 and the lockfile-pinned Mineflayer bridge, and those components have been exercised in live source/branch runs. The remaining blockers are behavioral/runtime qualification issues, not the old missing-toolchain prerequisites.

The current operational audit is `docs/status/CURRENT_EXECUTION_STATUS_20260828.md`; historical audits remain evidence for their own dates.

## Architecture in one page

The platform has one topology authority and three strictly separated planes.

~~~text
topology catalog
      │
      ▼
composition root ── freezes ── BindingPlan + digest
      │
      │ injects narrow ports
      ▼
runtime execution ── owns commands, state transitions and external effects
      │
      │ publishes facts only
      ▼
observation spine ── logs, metrics, traces, diagnostics and projections
~~~

The central dependency rule is:

~~~text
parent system
    └── composes direct child systems through their public API
            └── runtime receives only the narrow port it needs
~~~

A parent must not reach through the topology to select a grandchild
implementation. A runtime module must not discover a provider from a global
registry. An observation consumer must not become a second source of truth.

### Architectural invariants

1. Every durable state has one owner.
2. Every external effect has an explicit intent, receipt and certainty state.
3. Unknown effects are reconciled; they are never silently retried.
4. Provider identity is frozen before execution.
5. Runtime dependencies are narrow protocol ports.
6. Observations are side-plane facts, not commands or state authority.
7. Scientific identity includes source, protocol, plan, method, environment and
   model digests.
8. A failed gate remains visible as a classified failure.
9. Quality is never silently reduced to make a run pass.
10. Historical documents report evidence but do not override current ownership.

## Authoritative topology

The unique system-topology authority is:

~~~text
research_platform/governance/system_registry/catalog.json
~~~

The checked documentation mirror is:

~~~text
docs/architecture/VNEXT_SYSTEM_CATALOG.json
~~~

The source catalog is the authority for system membership and recursive
ownership. The documentation mirror is checked against it; it is not a second
runtime registry.

Each catalog node follows the same conceptual shape:

~~~text
<system>/
├── api/          public contracts, ports, identities and domain errors
├── runtime/      stateful lifecycle and execution semantics
├── providers/    adapters owned by this node
└── composition/ provider-to-port binding for this node
~~~

These directories are ownership boundaries, not a promise that every leaf is a
complete business implementation. The current migration audit reports
structural Runtime owners separately from behavioral completion.

## The three execution planes

### 1. Frozen composition plane

The composition plane resolves capability requirements and provider offers into
an immutable BindingPlan.

A binding contains, at minimum:

- capability identity and version;
- provider identity and implementation digest;
- dependency and environment evidence;
- port compatibility;
- configuration digest;
- source and release identity.

The BindingPlan is created before the hot path starts. It is inspectable,
serializable and reproducible. It is not a mutable service locator and it does
not expose a universal resolve operation.

### 2. Runtime execution plane

Runtime code uses only injected ports. Examples include:

- MethodSession for method-owned recall, update and evolution;
- environment ports for observation, action execution and world lifecycle;
- model endpoint ports for qualified requests;
- checkpoint ports for durable resume;
- failure and reconciliation ports for uncertain effects;
- artifact ports for durable publication.

Runtime code does not ask the topology catalog which provider to use. Provider
replacement happens in the composition root and changes the binding digest.

### 3. Observation plane

The observation spine carries facts to:

- structured logs;
- metrics and counters;
- traces and timing records;
- failure fingerprints;
- diagnostic projections;
- evidence indexes;
- release and audit reports.

The observation spine is intentionally not:

- a command bus;
- a mutable dependency container;
- an alternative scientific-state database;
- a recovery executor;
- a hidden fallback selector.

Commands remain typed calls on the owning runtime port. Durable facts are
written through the owning state authority. Observers can fail without changing
the primary execution truth.

## Recursive subsystem contract

A system boundary exposes a small public surface:

- API contracts and value objects;
- runtime ports;
- composition contracts;
- typed domain failures;
- evidence and identity types.

An implementation belongs to exactly one owner. A sibling imports the owner API,
not the sibling implementation. A project composition root may bind multiple
owned ports, but it must not move ownership into a convenience utility.

### Interface rules

Use an interface when a dependency represents a capability or a replaceable
boundary:

- a model endpoint;
- a filesystem or remote artifact store;
- a Minecraft environment;
- a process supervisor;
- a state store;
- a log/event sink;
- a checkpoint publisher;
- a failure reconciler.

Do not create an interface merely to hide a local algorithm. An adapter is a
real seam only when the implementation can be replaced or when the boundary
protects an external effect, state owner or scientific comparison.

### State ownership rules

A state owner must define:

- identity and schema;
- read and write authority;
- generation/version semantics;
- crash and corruption behavior;
- evidence references;
- recovery and reconciliation behavior.

A projection may accelerate queries, but it cannot become authoritative by
accident.

## System map

The following are the current top-level systems in the catalog.

| System | Responsibility |
| --- | --- |
| platform | kernel identities, execution context, configuration and lifecycle primitives |
| scope | hierarchy, membership, ownership and scope resolution |
| portfolio | projects, programs, workspaces and membership |
| experimentation | study, run, branch, variant, workload and checkpoint orchestration |
| execution | command, operation, scheduling, admission and workflow effects |
| participant | agent, capability, method and participant runtime |
| scientific | protocols, methods, prompts, measurements and implementation contracts |
| resource | resource and capacity catalogs |
| environment | environment specification, binding, instance, resolution and readiness |
| model | model catalog, revision, request, deployment closure and serving identity |
| runtime | process, session, supervision, control, history and toolchain lifecycle |
| data | durable state, query and cross-scope data access |
| artifact | references, lineage and retention |
| reliability | failures, incidents, recovery, replay, reconciliation and policy |
| observability | events, logs, diagnostics, metrics, traces, projections and health |
| governance | topology, architecture authority, dependency rules, schema and security |
| operator | commands, maintenance, incidents, queries and operational views |

A system can recursively own subsystems. For example, observability can own
recording, capture, storage, projection, retention and diagnostic paths without
making one global logging implementation responsible for every project.

## Runtime data flow

A normal research run follows this identity-preserving path:

~~~text
1. project composition root
       │
       ├── selects method, environment, model and observer providers
       └── freezes BindingPlan and provider digest
2. study protocol
       │
       ├── declares variants, seeds, repetitions, metrics and task manifest
       └── compiles a complete ExperimentPlan
3. run admission
       │
       ├── validates source, model, environment and resource identities
       └── creates run/branch/task/cycle/action identities
4. environment and method startup
       │
       ├── opens source world or deterministic environment
       ├── opens MethodSession and serving cut
       └── publishes startup evidence
5. task loop
       │
       ├── observe
       ├── recall through the method port
       ├── select a registered skill/action
       ├── execute through an environment capability
       ├── verify the effect and persist evidence
       └── update method state and checkpoint
6. interruption or failure
       │
       ├── classify the failure
       ├── preserve unknown effects
       ├── reconcile the external state
       └── resume only when the identity contract matches
7. finalization
       │
       ├── close world/process/session resources
       ├── publish manifests and evidence
       ├── compute comparability and metrics
       └── apply the scientific claim gate
~~~

Every important record is connected to the same run context. This is what makes
root-cause debugging possible: a failure can be traced from a task to a
decision cycle, action, effect receipt, environment generation, method
generation, model request and artifact reference.

## Paper-1 SEM project

The current project is under projects/sem_paper. Its scientific target is a
self-evolving memory method for long-horizon agents.

### Method treatments

The protocol declares:

- FixedSeed: fixed-memory control;
- RuleBasedEvolver: deterministic rule-based candidate treatment;
- SelfEvolve: evidence-bound self-evolving candidate treatment.

The seed factor has two explicit architecture configurations:

- Seed-C: the baseline seed;
- Seed-X: the changed seed used to test seed-sensitive behavior.

The minimum paired protocol is Core-6:

~~~text
Seed-C × {FixedSeed, RuleBasedEvolver, SelfEvolve}
Seed-X × {FixedSeed, RuleBasedEvolver, SelfEvolve}
~~~

Each primary arm has 12 repetitions. The claim-ready extension also declares an
external baseline and explicit adoption/reconciliation ablations. Declaring
these arms is not the same as executing them.

### Metrics

The current registry includes:

- success rate;
- mean utility;
- total steps;
- total duration;
- total memory queries;
- task failures;
- task blocks.

The complete claim-ready protocol is expected to add the project-specific
estimands and attribution evidence documented in the SEM runbook, including
trajectory, backfill and governance-integrity evidence. A result is claim
eligible only when the required evidence contracts and digest comparisons pass.

### Method/evidence boundary

The method owns memory semantics. The platform owns:

- the run context;
- checkpoint publication;
- action/effect evidence;
- artifact references;
- telemetry transport;
- recovery and reconciliation boundaries.

A task result is not automatically a scientific result. The project must prove:

1. the declared provider was the provider that ran;
2. the method and environment generations are identified;
3. the source cut and branch identity are valid;
4. all required actions and outcomes have evidence;
5. comparator arms are complete and comparable;
6. external model and live-world evidence are qualified;
7. the final claim gate accepts the complete evidence bundle.

### Current SEM integration gap

The current generic Minecraft cognition runner still creates
InMemoryAgentMemory inside the generic MC composition path. The current code
therefore does not yet prove that a live MC cognition run reads and updates the
SEM MethodSession memory. This is a high-priority integration item. It must be
fixed through an explicit injected AgentMemoryPort/MethodSession adapter, not
through a global lookup or hidden fallback.

The evolution graph is also deliberately fail-closed until real proposal,
paired evaluator, adoption and reconciliation authorities are bound. The
existence of a factory or a study variant is not evidence that the scientific
evolution stage has executed.

## Minecraft implementation

Minecraft is the first live environment and has a reusable platform binding.

### Environment components

The MC composition includes:

- official server.jar acquisition and digest verification;
- Java runtime acquisition and exact version probing;
- Node/Mineflayer bridge;
- server process lifecycle;
- TCP/RCON readiness;
- source-world scenario setup;
- world quiescence and source cuts;
- branch world copying;
- branch-local server lifecycle;
- typed action capabilities;
- observation and effect receipts;
- task checkpoint and resume;
- logs, artifacts and evidence publication.

The environment is deliberately split into ownership boundaries. World state,
server process state, bridge state, task state, method state and evidence
projection are not allowed to become one opaque mutable object.

### Primary task families

The current primary manifest contains six families:

1. resource collection;
2. crafting and technology progression;
3. navigation and return to an anchor;
4. combat survival;
5. simple building;
6. long-horizon mixed gathering/crafting.

The manifest is digest-bound to the protocol and run. Custom tasks can be
provided only through an explicit task manifest; the runner does not silently
replace a missing task with a shorter or scripted substitute.

### Cognition loop

The intended generic loop is:

~~~text
observe
  → recall
  → select a registered skill
  → expand a typed action sequence
  → execute through the MC action ABI
  → verify/evidence
  → persist experience
  → replan or complete
~~~

Reactive modes can request a typed replan, preemption or abort. Unregistered
actions and malformed urgent actions fail closed. The system does not enable
arbitrary model-generated shell or code execution.

### MC live-gate ladder

The live validation ladder is:

1. static source and architecture checks;
2. Java/Node/bridge/server-asset preflight;
3. T2A bridge and capability smoke;
4. T2B one real server process with Seed-C and Seed-X;
5. small model-backed smoke;
6. unmodified baseline reproduction;
7. full paired Core-6/claim-ready study.

T2B is strict. It requires the same real server process for both seed runs,
persistent world evidence, server logs, level.dat, bridge evidence and
digest-bound seed receipts. A blocked or partial gate cannot unlock a scientific
claim.

## Installation

The platform requires Python 3.11 or newer.

~~~bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e .
# Optional regression dependencies:
python -m pip install -e ".[test]"
~~~

The Minecraft bridge has its own Node dependency environment:

~~~bash
cd research_platform/environment/minecraft/providers/assets/mineflayer_bridge
npm ci
cd ../../../../../..
~~~

Live MC execution is intended for the Ubuntu/server environment with the
required Java, Node, Minecraft asset and bridge closure. Windows can be used
for source inspection, documentation and static checks; the current live
Minecraft process provider requires a POSIX host.

## Configuration

Configuration is split by ownership. Do not create a second project-local
registry for values already owned by the platform.

### Research run configuration

Important SEM inputs can be supplied as CLI arguments or environment variables:

| Concern | Examples |
| --- | --- |
| Minecraft version | SEM_MC_VERSION |
| server host/ports | SEM_MC_SERVER_HOST, SEM_MC_SOURCE_PORT, SEM_MC_BRANCH_PORTS |
| Java/Node | SEM_MC_JAVA, SEM_MC_NODE |
| player identity | SEM_MC_USERNAME |
| world seed | SEM_MC_SEED |
| model endpoint | SEM_MC_MODEL_BASE_URL, SEM_MC_MODEL_ID |
| model family and limits | SEM_MC_MODEL_FAMILY, SEM_MC_MODEL_TIMEOUT_S, SEM_MC_MODEL_CONTEXT_LENGTH |
| RCON secret name | SEM_MC_RCON_PASSWORD_ENV |
| qualified model receipt | SEM_MC_QUALIFIED_MODEL_CLOSURE |
| live evidence | SEM_MC_LIVE_EVIDENCE |
| auxiliary evidence | SEM_MC_SCIENTIFIC_AUXILIARY_EVIDENCE |

Secrets are read from the named environment variable. The secret value is not
part of the command line, repository, profile or log.

### Server profiles

Copy the example profile to an ignored local file:

~~~text
configs/server_profiles/sem-ubuntu.example.env
→ configs/server_profiles/sem-ubuntu.local.env
~~~

The profile binds the logical server id to:

- host, port and user;
- SSH key/config/known-hosts identity;
- remote platform, repository and release roots;
- managed Python, Node, Java and tmux paths;
- toolchain and package digests;
- persistent session name;
- controller-local binding directory.

The profile must not contain a password. The server system accepts key or agent
authentication for unattended operations and fails closed when the identity is
unavailable. See docs/infrastructure/server/SERVER_CONNECTIONS.md.

### Model and runtime profiles

Model deployment and runtime management use checked examples under configs/:

- configs/model_deployment.example.json;
- configs/runtime_management.example.json;
- configs/models/;
- configs/server_profiles/.

Machine-specific values belong in ignored local files or the platform's
environment-bound management store. They must not be hard-coded into project
composition.

## Usage

### Inspect the architecture

~~~bash
python scripts/architecture_report.py
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/sem_paper_architecture_audit.py
~~~

The reports are read-only. A gate failure is a classified engineering finding,
not a reason to remove the gate.

### Run the deterministic non-Minecraft conformance environment

~~~bash
python scripts/run_sem_non_minecraft_experiment.py \
  --run-id sem-core6-reference \
  --matrix-profile core-6 \
  --repetitions 12 \
  --output-dir runs/sem_paper_non_minecraft/sem-core6-reference
~~~

This validates protocol compilation, adapter dispatch, checkpointable workload
execution, artifact separation and metrics wiring. It is useful for platform
conformance, but it is not a Minecraft live-evidence receipt.

### Run Minecraft preflight

~~~bash
python scripts/run_sem_minecraft_experiment.py \
  --mode preflight \
  --acquire-java-runtime \
  --acquire-server-jar \
  --output-dir runs/sem_paper_minecraft/preflight
~~~

The acquisition switches are explicit. The runtime resolves official metadata,
verifies digest/size/platform identity, materializes assets safely and
publishes receipts. An absent asset is never silently downloaded.

### Run a plumbing-only scripted smoke

~~~bash
python scripts/run_sem_minecraft_experiment.py \
  --mode scripted-smoke \
  --acquire-java-runtime \
  --acquire-server-jar \
  --accept-minecraft-eula \
  --generate-ephemeral-rcon-secret \
  --output-dir runs/sem_paper_minecraft/scripted-smoke
~~~

This is only a plumbing and recovery check. It must never be reported as a
scientific result or used to bypass model qualification.

### Run a strict baseline

~~~bash
python scripts/run_sem_minecraft_experiment.py \
  --mode baseline \
  --run-id sem-core6-minecraft \
  --server-jar "$SEM_MC_SERVER_JAR" \
  --qualified-model-closure "$SEM_MC_QUALIFIED_MODEL_CLOSURE" \
  --live-evidence "$SEM_MC_LIVE_EVIDENCE" \
  --scientific-auxiliary-evidence "$SEM_MC_SCIENTIFIC_AUXILIARY_EVIDENCE" \
  --accept-minecraft-eula
~~~

The strict mode fails before starting Minecraft if the qualified model closure,
evolution authority, Java/Node runtime, server asset, task manifest or evidence
contract is incomplete.

### Run the canonical T2B gate

~~~bash
python scripts/t2b_local_gate.py \
  --server-jar /absolute/path/to/server.jar \
  --workdir /absolute/path/to/t2b-workdir \
  --bridge-dir research_platform/environment/minecraft/providers/assets/mineflayer_bridge \
  --java /absolute/path/to/java \
  --node /absolute/path/to/node
~~~

The gate writes T2B_GATE_RESULT.json. A PASS requires one persistent server
process, both Seed-C and Seed-X live smokes, persistent level.dat, bridge
evidence and a complete digest-bound result.

### Resume an interrupted run

~~~bash
python scripts/run_sem_minecraft_experiment.py \
  --mode baseline \
  --run-id "$SEM_RUN_ID" \
  --output-dir "$SEM_RUN_ROOT" \
  --resume-index "$SEM_RUN_ROOT/resume_index.json" \
  --qualified-model-closure "$SEM_MC_QUALIFIED_MODEL_CLOSURE" \
  --live-evidence "$SEM_MC_LIVE_EVIDENCE" \
  --scientific-auxiliary-evidence "$SEM_MC_SCIENTIFIC_AUXILIARY_EVIDENCE"
~~~

Resume requires the original run id, output directory and compatible identity.
A changed task manifest, protocol, method generation, candidate, source cut,
environment or model identity fails closed.

### Verify claim evidence

~~~bash
python scripts/verify_sem_paper_live_evidence.py \
  "$SEM_MC_LIVE_EVIDENCE" \
  --source-tree-digest "$SEM_PAPER_SOURCE_TREE_DIGEST" \
  --require-claim-eligibility

python scripts/verify_sem_paper_scientific_auxiliary_evidence.py \
  "$SEM_MC_SCIENTIFIC_AUXILIARY_EVIDENCE" \
  --source-tree-digest "$SEM_PAPER_SOURCE_TREE_DIGEST" \
  --plan-digest "$SEM_PAPER_PLAN_DIGEST" \
  --protocol-digest "$SEM_PAPER_PROTOCOL_DIGEST" \
  --binding-digest "$SEM_PAPER_BINDING_DIGEST"
~~~

## Server-first workflow

The intended workflow is local source control plus server-side execution:

~~~text
local inspection/edit
      → commit and push to GitHub
      → exact revision sync on the managed server
      → server-side compile/gate/smoke/experiment
      → export evidence and exact revision
      → review locally
~~~

Do not manually SSH into an arbitrary directory or run unjournaled project
commands. Use the platform server scripts.

### Inspect a configured server

~~~bash
PROFILE=configs/server_profiles/sem-ubuntu.local.env

python scripts/server_doctor.py list --profile-file "$PROFILE"
python scripts/server_doctor.py inspect sem-ubuntu --profile-file "$PROFILE"
python scripts/server_health.py sem-ubuntu --profile-file "$PROFILE"
~~~

### Use a persistent operator session

~~~bash
python scripts/server_session.py ensure sem-ubuntu --profile-file "$PROFILE"
python scripts/server_session.py status sem-ubuntu --profile-file "$PROFILE"
python scripts/server_session.py attach sem-ubuntu --profile-file "$PROFILE"
~~~

The operator session is for durable interactive control. It is not itself
evidence that a model, Minecraft server or scientific run is healthy.

### Sync an exact Git revision

~~~bash
python scripts/server_repository_sync.py \
  sem-ubuntu \
  https://github.com/SDFGAEV/agent-research-platform-system.git \
  agent-research-platform-system \
  40-character-commit-sha \
  --profile-file "$PROFILE"
~~~

Repository synchronization is profile-bound, clean-checkout aware, journaled
and revision-verified. If an operation is interrupted, inspect the operation and
repository status before retrying:

~~~bash
python scripts/server_repository_status.py \
  sem-ubuntu agent-research-platform-system \
  --profile-file "$PROFILE"
~~~

Execute a server-side command only through the exact revision-bound command
entrypoint:

~~~bash
python scripts/server_repository_command.py \
  sem-ubuntu \
  agent-research-platform-system \
  40-character-commit-sha \
  --cwd projects/sem_paper \
  --profile-file "$PROFILE" \
  -- python -m compileall -q .
~~~

The server command is recorded with the profile, repository, revision, command
argv and result evidence.

## Recovery and resume

The platform treats interruption as a state transition, not as a reason to
blindly restart.

### Durable state

Durable session state uses:

- append-first WAL;
- checksummed primary and backup snapshots;
- corruption detection;
- interprocess locking;
- observed-digest compare-and-swap;
- explicit generation and lineage identities.

### External effects

Every important external action carries:

- request and operation identity;
- intent;
- start and finish evidence;
- effect certainty;
- environment generation;
- reconciliation status.

The states are not interchangeable:

~~~text
CONFIRMED  = effect is proven
REJECTED   = effect is proven not to have happened
UNKNOWN     = effect status is not proven
~~~

UNKNOWN is preserved until reconciliation proves the outcome. The platform does
not turn a timeout into a safe retry.

### Minecraft recovery

An MC checkpoint binds:

- run and study identity;
- protocol and plan digest;
- task and candidate identity;
- source cut;
- environment and method generations;
- world provider payload;
- state projection;
- observation sequence;
- action verification ledger;
- task prefix.

Recovery validates the entire envelope before mutating the environment. The
normal order is stop bridge, restore world, restore method/session state,
reconnect bridge, verify identity and continue. Any mismatch is a classified
failure.

## Model and AI infrastructure

Model deployment is treated as a qualified infrastructure closure, not as a
single downloaded weight file.

A qualified model identity includes:

~~~text
model family and revision
    + artifact files and digests
    + Python environment and package closure
    + CUDA/GPU/host facts
    + serving backend and build identity
    + tensor parallelism / placement
    + endpoint readiness
    + prompt generation
    = immutable model deployment closure
~~~

The model system provides reusable boundaries for:

- model family and revision catalogues;
- artifact and cache management;
- Python environment management;
- host/GPU/CUDA qualification;
- backend selection;
- endpoint allocation and readiness;
- request envelopes and prompt identity;
- model run state and recovery.

The SEM baseline cannot use an unqualified endpoint. A model that merely
responds to a test request is not automatically a claim-eligible model.

See:

- docs/infrastructure/ai/AI_INFRASTRUCTURE_SYSTEM.md;
- docs/infrastructure/ai/NATIVE_RUNTIME_ASSET_SYSTEM.md;
- configs/model_deployment.example.json;
- configs/runtime_management.example.json.

## Verification and release gates

Verification is performed in stages and at the owning boundary.

### Recommended order

1. inspect source ownership and call chains;
2. run architecture and public-contract audits;
3. run no-degradation and silent-failure audits;
4. compile the exact target checkout;
5. run focused regression tests;
6. run server-side preflight;
7. run T2A/T2B;
8. run non-claim smoke;
9. reproduce the unmodified baseline;
10. run the complete paired study;
11. verify evidence and scientific closure.

### Static checks

~~~bash
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/sem_paper_architecture_audit.py
python -m compileall -q research_platform projects scripts
~~~

### Regression checks

~~~bash
python -m pytest -q
~~~

The target server is the canonical validation environment for server-backed
execution. Local Windows checks are useful for source and contract inspection,
but they do not substitute for Ubuntu process, Java, Node, GPU, model or
Minecraft validation.

### Claim gate

A scientific claim requires all of the following:

- exact source-tree digest;
- complete protocol and plan;
- qualified model deployment closure;
- valid environment and server identity;
- complete task/effect/evidence streams;
- live T2B receipt where required;
- auxiliary scientific evidence;
- complete comparator and ablation matrix;
- valid paired statistics and comparability decision.

If any item is missing or mismatched, the run remains a reproducible blocked
artifact rather than a claim.

## Evidence and artifact model

The platform separates three record planes:

~~~text
DURABLE_FACT
  replayable facts, scientific state and authoritative snapshots

LIVE_INTERCEPTION
  current execution interception; durable mutation requires an explicit commit

SIDE_PLANE_OBSERVATION
  telemetry, logs, traces and diagnostics
~~~

Artifacts are addressed by stable references and linked by lineage. A release or
evidence bundle binds:

- relative member name;
- schema and record count;
- source references;
- SHA-256 digest;
- run and provider identity;
- derivation relation;
- environment/model/method generation.

Raw event streams and query projections are separate. A projection may be
rebuilt, discarded or rotated without becoming a hidden authority.

## Repository layout

~~~text
agent-research-platform-system/
├── research_platform/                 reusable platform systems
│   ├── platform/                      kernel, identity, configuration, lifecycle
│   ├── governance/                    topology, architecture, schema and security
│   ├── experimentation/               studies, runs, variants, branches, workloads
│   ├── execution/                    commands, operations, scheduling and effects
│   ├── participant/                   agent, capability and method ports
│   ├── scientific/                    reusable scientific contracts
│   ├── environment/                  generic and Minecraft environments
│   ├── model/                        model catalogue, requests and deployment
│   ├── runtime/                      process, session, supervision and toolchain
│   ├── data/                         durable state and query
│   ├── artifact/                     references, lineage and retention
│   ├── reliability/                  failures, recovery and reconciliation
│   ├── observability/                logs, events, diagnostics and projections
│   ├── resource/                     resource and capacity catalogues
│   ├── portfolio/                    projects, programmes and workspaces
│   ├── scope/                        hierarchy and ownership
│   └── operator/                     maintenance and operational commands
├── projects/sem_paper/                SEM method and project composition
├── configs/                           non-secret configuration examples
├── scripts/                           thin, persistent operator entrypoints
├── tests/                             architecture and behavior regression
├── docs/                              hierarchical documentation
├── CONTEXT.md                         vocabulary and architectural context
├── CURRENT_VALIDATION.json             current recorded validation snapshot
├── RELEASE_EVIDENCE.json               release evidence metadata
└── RELEASE_MANIFEST.json               digest-bound source manifest
~~~

The public entrypoint of a subsystem belongs under its api package. Concrete
implementations belong under providers or runtime according to ownership.
Composition belongs at the outer edge of the dependency graph.

## Documentation map

The documentation root is docs/INDEX.md. Its authority order is:

1. research_platform/governance/system_registry/catalog.json;
2. docs/architecture/VNEXT_SYSTEM_CATALOG.json;
3. current architecture and governance documents;
4. project and research documents;
5. history and status snapshots.

Important entrypoints:

| Path | Purpose |
| --- | --- |
| docs/architecture/ | final recursive architecture, topology and composition |
| docs/governance/ | invariants, gates, debugging, forensic policy and documentation-change policy |
| docs/status/CURRENT_EXECUTION_STATUS_20260828.md | current server/model/Minecraft/SEM execution truth |
| docs/infrastructure/ | reusable server, AI, runtime and Minecraft infrastructure |
| docs/research/memory/ | SEM memory method research |
| docs/projects/sem_paper/ | SEM implementation and experiment runbooks |
| docs/status/ | current development truth and version status |
| docs/history/ | immutable round-by-round evidence |
| CONTEXT.md | architecture vocabulary and non-negotiable design decisions |

Historical notes are evidence, not a replacement for current source ownership.
When a design changes, update the current owner document and add a new dated
history note.

## Adding a project or provider

### Add a new research project

Create a project composition root under projects/<project_id>/.

The project should:

1. declare project, study, method and environment identities;
2. declare required capabilities and model roles;
3. import platform API contracts only;
4. bind concrete providers in the project composition root;
5. use narrow runtime ports;
6. publish manifests, checkpoints, evidence and comparability decisions;
7. keep scientific state and semantics project-owned;
8. add project documentation under docs/projects/<project_id>/;
9. add research-level method documents under docs/research/ when reusable.

### Add a new environment

A new environment should provide:

- typed environment specification;
- identity and digest;
- observation port;
- action/effect port;
- readiness and lifecycle ports;
- checkpoint and restore port;
- effect certainty and reconciliation behavior;
- evidence references for every external mutation.

The generic workload and experiment systems should be reused. Do not copy the
Minecraft runner merely to change the environment.

### Add a new method

A method should provide:

- method identity and generation;
- MethodSession recall/update boundary;
- serving cut;
- method-owned durable state;
- method-specific evidence and lineage;
- evolution authority ports if the method changes itself.

The method should not import the concrete server, model or logger. Those are
composition concerns.

### Add a new model provider

A model provider must expose:

- immutable model and revision identity;
- qualified deployment closure;
- request envelope and prompt generation;
- endpoint readiness;
- usage/cost metadata;
- failure and timeout evidence.

It must not silently select a weaker model or alter context/budget parameters.

## Security and data handling

Never commit:

- SSH private keys;
- passwords or RCON secrets;
- API tokens;
- machine-specific private paths;
- model credentials;
- unreviewed run artifacts containing secrets.

Use:

- ignored local server profiles;
- environment variables for secrets;
- key or agent authentication for unattended server operations;
- redacted error projections;
- digest references instead of raw credentials.

The repository's server scripts disable interactive password prompts for unattended
operations and journal remote mutations. Only the explicit operator attach
operation is interactive.

If a secret is accidentally written to a tracked file, rotate it first, then
remove it in a dedicated audited change. Do not rely on deletion from the
working tree alone.

## Known limitations

The following limitations are intentional and visible:

1. The current live Minecraft T2B gate is blocked by environment prerequisites.
2. A generic MC cognition runner still needs an explicit SEM MethodSession
   memory adapter before live MC results measure SEM memory.
3. Real evolution proposal, paired evaluation, adoption and reconciliation
   authorities still need to be composed for claim-eligible self-evolution.
4. Structural Runtime owners in the migration catalog are boundaries, not
   proof that each leaf already contains a full domain implementation.
5. A deterministic non-Minecraft run validates platform wiring, not Minecraft
   behavior or scientific superiority.
6. A scripted smoke validates plumbing and recovery, not method quality.
7. The live experiment requires the target Ubuntu/server environment; Windows
   is not a substitute for POSIX process and toolchain validation.
8. The repository does not infer missing credentials, model closure or EULA
   consent.

These limitations are not bypassed by weakening gates. They are resolved by
binding the missing authority or environment at its owning boundary and
re-running the corresponding validation stage.

## Contributing

Before changing code:

1. read CONTEXT.md and the relevant owner documents;
2. inspect the composition root and runtime call chain;
3. identify the single state/effect/evidence owner;
4. define or reuse the narrowest required port;
5. update the current architecture/project document in the same change set;
6. update `docs/status/CURRENT_EXECUTION_STATUS_20260828.md` when runtime/model/server/SEM state changes;
7. add a dated history note for a completed slice.

Before committing:

1. run git diff --check;
2. run focused architecture and contract checks;
3. inspect generated artifacts for secrets and stale absolute paths;
4. use the server-side validation ladder for server-backed changes;
5. record what was actually verified and what remains blocked.

Do not:

- add a global service locator;
- put project-specific semantics in generic runtime code;
- hide failures behind fallback behavior;
- claim an experiment from a partial or scripted run;
- modify an unrelated subsystem while fixing a local bug;
- delete evidence merely because it is inconvenient.

## License

No license file has been declared in this repository yet. Until the repository
owner adds a license, treat the source as available for evaluation and
collaboration only, not as implicitly granted for redistribution or commercial
use.
