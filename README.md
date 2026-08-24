# Agent Research Platform

`agent-research-platform-system` is a contract-driven platform for building,
running and auditing long-horizon agent research. It is designed for projects
that need all of the following at the same time:

- replaceable agent methods and environments;
- reproducible experiments and paired scientific evaluation;
- explicit model, runtime, server and virtual-environment management;
- durable state, failure evidence and crash-safe recovery;
- detailed observability with fast root-cause diagnosis;
- multiple projects, models, servers and execution backends under one platform.

The current scientific project is a self-evolving-memory agent evaluated in a
Minecraft open world. Minecraft is the first environment, not the limit of the
platform boundary: the same Study, Workload and Method ports also run against
the platform's deterministic, checkpointable state-machine environment base.

> Development status: the repository is in direct migration to the final
> recursive architecture. The Paper-1 implementation and focused migration
> slices are active; a complete post-migration regression or scientific result
> is only claimed when its corresponding evidence is recorded in the current
> baseline and experiment artifacts.

## Design goals

The platform treats a research run as an auditable composition of independent
systems rather than as a script that imports every implementation directly.
The central design goals are:

1. One authoritative owner for each durable state, external effect, runtime
   lifecycle and evidence domain.
2. Recursive ownership: a parent system composes its direct children; it does
   not reach through the global tree to select grandchildren.
3. Replaceability: provider choices are frozen at composition time and narrow
   runtime ports are injected into execution paths.
4. Scientific integrity: baseline, candidate, task, environment, model and
   evidence identities are explicit and comparable.
5. Failure transparency: unknown external effects remain unknown, recovery is
   reconciled explicitly, and no silent quality downgrade is allowed.
6. Debuggability: every important operation can be connected to run, task,
   decision-cycle, model request, effect, state mutation and failure evidence.

## Architecture at a glance

The platform has one topology authority:

```text
research_platform/governance/system_registry/catalog.json
        │
        ├── materialized Python system catalog
        └── docs/architecture/VNEXT_SYSTEM_CATALOG.json
             (checked documentation mirror)
```

Every catalog node follows the same recursive package shape:

```text
<system-or-subsystem>/
├── api/          public contracts, ports, identities and domain errors
├── runtime/      stateful lifecycle and execution semantics
├── providers/    external or infrastructure adapters owned by this node
└── composition/ concrete provider-to-port binding for this node
```

The shape is not a collection of empty folders. It is an ownership rule:
contracts are imported through the owning API, concrete providers are selected
by composition roots, and runtime code receives only the ports it needs.

### The three planes

```text
                    ┌──────────────────────────────┐
                    │     Frozen composition plane │
                    │ capability offers/needs      │
                    │ immutable BindingPlan        │
                    └──────────────┬───────────────┘
                                   │ inject narrow ports
                    ┌──────────────▼───────────────┐
                    │     Runtime execution plane  │
                    │ methods, environments,      │
                    │ models, effects, recovery    │
                    └──────────────┬───────────────┘
                                   │ publish facts/events
                    ┌──────────────▼───────────────┐
                    │       Observation plane      │
                    │ logs, metrics, traces,       │
                    │ projections and diagnostics  │
                    └──────────────────────────────┘
```

#### Frozen composition plane

Typed capability offers and requirements are validated into an immutable
`BindingPlan` with a reproducible digest. The plan contains provider identity
and dependency evidence, but it is not a mutable dependency container: it has
no generic `get`, `resolve` or service-locator operation.

#### Runtime execution plane

The composition root injects narrow protocol ports into hot paths. Runtime code
does not discover a provider, select a fallback or traverse the global system
registry. Changing a provider therefore changes a composition binding and its
evidence, not hidden behavior in a distant runtime module.

#### Observation plane

The event spine carries observation facts for logs, metrics, traces and
disposable projections. It is deliberately not a command bus, dependency
container, scientific-state owner or recovery executor. Commands remain typed
calls on the owning runtime port.

## System topology

The current catalog has these top-level systems:

```text
platform          scope             portfolio
experimentation   execution         participant
scientific        resource          environment
model             runtime           data
artifact          reliability       observability
governance        operator
```

The topology is recursive. For example, the platform does not own every log
implementation: `observability` decomposes logging into independent authorities
for context, record, routing, sink, storage, query, projection, retention and
capture. A project imports the public logging capability it requires and binds
its own project-level view at its composition root.

## Durable truth and evidence

The platform separates three record planes:

```text
DURABLE_FACT
    replayable/reconstructable facts and scientific state

LIVE_INTERCEPTION
    current-execution interception; durable changes require an explicit fact

SIDE_PLANE_OBSERVATION
    telemetry and diagnostics; observer failure cannot change primary truth
```

This separation prevents a fast projection, log line or recovery hint from
becoming an accidental second source of truth. Model-visible requests are also
reconstructable: prompt generation, compiled prompt, tool schema, model
identity and content references are bound into a durable request envelope.

External effects use explicit intent, certainty and reconciliation. An
`UNKNOWN` effect is never treated as a safe blind retry. Release manifests,
runtime bindings, checkpoint identities and model-stack identities are tied to
the exact source and runtime evidence that produced them.

## Paper-1: self-evolving memory in Minecraft

The current project is composed under `projects/sem_paper` and declares two
method treatments:

- `fixed_memory` — the fixed-memory control treatment;
- `self_evolving` — the candidate treatment with method evolution.

The current executable MC and closed-world conformance graphs deliberately bind
a static Seed-X candidate and a disabled evolution controller. They prove the
portable execution, evidence and recovery paths, but they are not evidence that
the production self-evolution stages or the full scientific matrix are complete.

The generic platform does not import the Paper-1 memory implementation. The
project composition root imports platform ports, supplies method-owned
implementations and freezes the project binding. The reusable Minecraft host
owns source-server readiness, quiescence, world cuts, branch runtime and branch
cleanup; the project supplies task, planner, method and evidence composition.

The platform MC action ABI currently exposes 24 typed capabilities across
movement, resources, inventory, combat, interaction and observation. The
Mineflayer provider publishes the same capability manifest during handshake;
startup fails on catalog drift. Every task action emits identity-bound
`applied`, `partial` or `rejected` evidence, and only a verified result carrying
the requested action ID and tool may enter SEM memory. Provider code is split
into independent movement, resource/crafting, inventory/container and combat
modules; combat uses bounded `mineflayer-pvp` pressure with grounded hurt/death
signals and a dependency-free bounded melee fallback.

The intended execution ladder is:

```text
unmodified baseline reproduction
        → small scripted/model-backed smoke
        → full paired experiment
```

The paired study keeps workload identity, task manifest, environment generation
and source cut comparable while keeping control and candidate branch identity
separate. Operational success is not itself a scientific result: the run must
also produce complete manifests, evidence and a valid comparability decision.

## Repository layout

```text
research_platform/                  platform systems and public contracts
projects/sem_paper/                 Paper-1 composition and method code
configs/                            deployment, runtime and server profiles
scripts/                            operator, release, server and experiment CLIs
tests/                              architecture and behavior regression tests
docs/                               hierarchical documentation root
```

The executable memory method is owned by:

```text
projects/sem_paper/method/self_evolving_memory/
```

Reusable capabilities are owned by their platform system, for example:

```text
research_platform/environment/minecraft/
research_platform/environment/runtime/       # generic state-machine base
research_platform/model/stack/
research_platform/model/serving/
research_platform/runtime/server/
research_platform/runtime/session/
research_platform/observability/
research_platform/reliability/
```

## Installation

The project requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

The platform intentionally does not commit server credentials, model tokens or
machine-specific paths. Use environment-bound profiles and deployment
configuration for those values.

## Common commands

Install the package and expose the platform CLIs:

```bash
research-platform-architecture-gate
research-platform-manage --help
evoctl-next --help
```

Generate a read-only architecture report or development snapshot:

```bash
python scripts/architecture_report.py
python scripts/generate_development_snapshot.py
```

Run the Paper-1 experiment entry point:

```bash
cd research_platform/environment/minecraft/providers/assets/mineflayer_bridge
npm ci
cd ../../../../../..

python scripts/run_sem_minecraft_experiment.py --mode preflight \
  --acquire-java-runtime \
  --acquire-server-jar
python scripts/run_sem_minecraft_experiment.py --mode scripted-smoke \
  --acquire-java-runtime \
  --acquire-server-jar \
  --accept-minecraft-eula \
  --generate-ephemeral-rcon-secret
python scripts/run_sem_minecraft_experiment.py --mode baseline \
  --server-jar "$SEM_MC_SERVER_JAR" \
  --accept-minecraft-eula \
  --qualified-model-closure "$SEM_MC_QUALIFIED_MODEL_CLOSURE"
```

`--acquire-server-jar` resolves the selected `--minecraft-version` through
Mojang's official manifests, streams the artifact into the ignored
`.runtime-assets` cache and verifies the published SHA-1 and size before atomic
publication. It is explicit: an absent asset is never downloaded unless this
flag is supplied. EULA acceptance is a separate operator decision and is never
implied by acquisition.

`--acquire-java-runtime` uses the platform runtime-toolchain port to resolve an
official Eclipse Temurin build for the current Linux architecture. It verifies
Adoptium's published SHA-256 and byte size, materializes the single-root tar
archive through the bounded path-safe archive provider, executes the exact
materialized `java -version`, and publishes `java_runtime_artifact.json`.
Verified archive, tree and receipt reuse is network-free; any archive, tree,
executable or version-output drift fails closed. Host Java remains injectable
with `--java-executable` when acquisition is not selected.

`scripted-smoke` defaults to a deterministic source-world scenario plus five
typed tasks that exercise collection, crafting, placement and melee combat.
Every scenario mutation has a server-side RCON assertion; its receipt is bound
to the environment identity and written before paired world cuts execute.
Custom tasks and scenarios remain independently injectable with `--tasks` and
`--scenario`.

Run the same SEM project interfaces on the deterministic non-Minecraft
conformance environment:

```bash
python scripts/run_sem_non_minecraft_experiment.py \
  --run-id sem-portability-v1 \
  --matrix-profile core-6 \
  --repetitions 12
```

Resume an interrupted MC run from its durable source-cut/checkpoint index. The
original run id and output directory are part of the frozen identity:

```bash
python scripts/run_sem_minecraft_experiment.py --mode baseline \
  --run-id "$ORIGINAL_RUN_ID" \
  --output-dir "$ORIGINAL_RUN_ROOT" \
  --resume-index "$ORIGINAL_RUN_ROOT/resume_index.json" \
  --qualified-model-closure "$SEM_MC_QUALIFIED_MODEL_CLOSURE"
```

`baseline` is intentionally strict: it requires a persisted platform-qualified
model deployment closure, Java, Node.js, a valid Minecraft server asset and a
valid task manifest. A missing dependency is reported as a configuration error;
the runner does not silently substitute a weaker model, shorter context or
different method. The production matrix is Core-6 (Seed-C/Seed-X ×
Fixed/RuleBased/SelfEvolve, 12 repetitions). A scientific claim additionally
requires the externally produced `--live-evidence` receipt and the typed
`--scientific-auxiliary-evidence` receipt containing TDP, ELCE, HPEF and GAG,
both digest-bound to the exact plan, binding and checkout. Missing evidence
keeps the run reproducible but claim-ineligible.

Verify the two external evidence contracts independently before a claim run:

```bash
python scripts/verify_sem_paper_live_evidence.py "$SEM_MC_LIVE_EVIDENCE" \
  --source-tree-digest "$SEM_PAPER_SOURCE_TREE_DIGEST" \
  --require-claim-eligibility

python scripts/verify_sem_paper_scientific_auxiliary_evidence.py \
  "$SEM_MC_SCIENTIFIC_AUXILIARY_EVIDENCE" \
  --source-tree-digest "$SEM_PAPER_SOURCE_TREE_DIGEST" \
  --plan-digest "$SEM_PAPER_PLAN_DIGEST" \
  --protocol-digest "$SEM_PAPER_PROTOCOL_DIGEST" \
  --binding-digest "$SEM_PAPER_BINDING_DIGEST"
```

The complete SEM run procedure, artifact identities and fail-closed release
conditions are documented in
`docs/projects/sem_paper/SEM_FINAL_RUNBOOK.md`.

## Server and AI infrastructure

Server identity, health, persistent sessions, release publication and recovery
are managed through the server system. Profiles contain environment-variable
references rather than committed secrets. Useful operator surfaces include:

```bash
python scripts/server_doctor.py list
python scripts/server_doctor.py --help
python scripts/server_health.py --help
python scripts/server_session.py --help
python scripts/server_runtime.py --help
```

Model assets and serving are managed as a stack rather than as an ad-hoc model
download. The stack binds:

```text
logical model identity
    + immutable artifact closure
    + executable runtime build identity
    + qualified host/capacity evidence
    + placement and endpoint declaration
    = frozen model-stack identity
```

The runtime asset manager supports workspaces, Python environments, model
assets and deployment desired state. See
`docs/infrastructure/ai/AI_INFRASTRUCTURE_SYSTEM.md` and
`configs/runtime_management.example.json`.

## Verification policy

Verification is performed in proportion to the change and, for server-backed
work, on the target server environment. The normal order is:

1. source and import/call-chain inspection;
2. focused architecture, dependency and no-degradation checks;
3. server-side baseline or smoke validation;
4. full paired experiment only after the preceding evidence is valid.

The project does not claim a passing experiment from a partial log, a scripted
planner, an unreachable model or a recovered process whose effect status is
unknown. Root causes are fixed at their owning boundary; fallbacks that reduce
quality or hide a failure are prohibited.

## Documentation map

The documentation is intentionally hierarchical rather than a flat changelog:

- [`docs/INDEX.md`](docs/INDEX.md) — complete documentation ownership map;
- [`docs/architecture/`](docs/architecture/) — final architecture and topology;
- [`docs/governance/`](docs/governance/) — gates, forensics and invariants;
- [`docs/infrastructure/`](docs/infrastructure/) — reusable runtime systems;
- [`docs/research/memory/`](docs/research/memory/) — memory-method research;
- [`docs/projects/sem_paper/`](docs/projects/sem_paper/) — current Paper-1 docs;
- [`docs/history/`](docs/history/) — historical round evidence;
- [`docs/status/`](docs/status/) — current baseline and version status.

The current development truth is
[`docs/status/CURRENT_DEVELOPMENT_BASELINE.md`](docs/status/CURRENT_DEVELOPMENT_BASELINE.md).
Historical changes are intentionally kept out of this README; consult the
status and history trees when an audit trail is needed.

## Contributing a new research project

Create a project composition root under `projects/<project_id>/` and make it
depend on platform API ports only. A new project should:

1. declare its identity, required capabilities and method identities;
2. bind concrete method, environment, model, logging and evidence providers in
   its own composition package;
3. keep scientific state and method semantics project-owned;
4. reuse server, model, runtime and observability systems through their public
   ports;
5. record manifests, checkpoints, failure evidence and comparability results;
6. add a project README under `docs/projects/<project_id>/` and link its
   research method documents under `docs/research/` when appropriate.

This keeps the platform extensible to new agent methods, environments and
servers without turning the generic runtime into a project-specific framework.
