# Paper-1 Minecraft Production Root Audit — 2026-08-21

## Scope and evidence

This audit concerns the production path for the current SEM Paper-1 method,
not the scientific validity of a completed experiment. It is based on direct
source and call-chain inspection of:

- `projects/sem_paper/composition/project.py`;
- `projects/sem_paper/composition/minecraft_branch.py`;
- `projects/sem_paper/composition/minecraft_workload_executor.py`;
- `research_platform/environment/minecraft/{composition,runtime,providers}`;
- `projects/sem_paper/method/self_evolving_memory/{composition,runtime,evolution}`.

No Minecraft server, model service, remote host, or experiment was started by
this audit.

## What is real today

```text
source MC world
  -> verified world cut
  -> isolated filesystem branch
  -> paired branch runner
  -> environment-owned branch runtime binder
  -> project-owned workload binding factory
  -> task runner
  -> environment / method / evidence / planner [all injected seams]
  -> branch receipt and comparability proof
```

The following pieces are implemented and tested independently:

1. `MinecraftPairedBranchRunner` captures one source cut, materializes each
   branch, enforces control/candidate roles, and releases branch storage.
2. `MinecraftWorkloadBranchExecutor` runs every declared task and aggregates
   branch metrics, while preserving binding-close failure as an error.
3. `MinecraftWorkloadEnvironmentAdapter` rejects malformed observations rather
   than inventing state.
4. `SEMMinecraftEvidenceIngestor` routes normalized MC events into the method
   and audit seams.
5. `compose_sem_paper` produces a project-scoped frozen capability plan and
   binds fixed and self-evolving method endpoints without opening a session.

The branch runtime binder, Paper workload binding factory and
`SemPaperMinecraftProductionRoot` are now explicit composition seams. They
freeze the world-cut → paired runner → workload executor → evaluator graph but
do not open a live resource. The host caller, qualified planner and server
deployment manifest are still not wired.

## Blocking gaps proved by the current data flow

### 1. The host production inputs are not wired

`MinecraftWorldBranch.workdir` is now mapped by
`MinecraftBranchRuntimeFactory` to a branch-specific `MinecraftServerSpec`, an
explicit endpoint allocation, an exact injected server lifecycle port and a
Minecraft environment session. The project
`SemPaperMinecraftWorkloadBindingFactory` then opens the method and evidence
surfaces over that runtime. No platform host caller yet supplies the frozen
server contract, endpoint candidates, bridge command and lifecycle provider.

The remaining gap is host/run input composition, not a missing branch-runtime
or project paired-evaluation abstraction.

### 2. The source world and a branch cannot safely share the source endpoint

`FilesystemMinecraftWorldCutProvider.capture` deliberately resumes the source
server after the copy. A branch server launched on the same host/port would
conflict with that live source process. Replacing the source service or
stopping it implicitly would invalidate the cut protocol and make recovery
ambiguous.

The production design must give each branch an explicit operational endpoint
lease (or an equally explicit source-to-branch handoff protocol). It may not
rely on a reused TCP address or a best-effort stop/start sequence.

### 3. Scientific environment identity currently contains operational address

`MinecraftEnvironmentImplementation.identity` hashes the complete
`MinecraftEnvironmentSpec`, including the endpoint host and port. A correct
branch runtime needs distinct leased ports while preserving equal scientific
conditions for control and candidate. Under the current shape, distinct ports
produce distinct environment generations and force the comparability proof to
fail even when world, server artifact, bridge ABI and tasks are identical.

This is a model-boundary problem, not a metric exception to waive.

### 4. Candidate architecture is not yet materialized into the candidate
method session

`CandidateArchitecture` is carried through the paired-runner and workload
factory protocols, but no concrete provider maps `target_spec` and its
materialization contract to the candidate's `MethodEndpointPort`/
`MethodSession`. The current SEM composition constructs fixed or
self-evolving endpoints from configured factories; it does not select a
candidate-specific runtime architecture.

Passing a candidate into the existing executor without this materialization
would evaluate the baseline twice while labeling one branch "candidate".

### 5. There is no production workload planner binding

The only concrete planner in the Paper workload package is
`ScriptedMinecraftPlanner`, deliberately suitable for deterministic smoke and
baseline scripts. No project-owned adapter currently binds a frozen qualified
model/request/prompt identity to `MinecraftPlannerPort` for scientific runs.

## Final ownership split to implement

The next implementation must establish these owners before connecting the
branch runner to live infrastructure:

```text
experimentation/run/manifest
    exact run identity, including frozen composition and model evidence

environment/minecraft
    branch runtime realization:
    branch workdir -> server configuration -> endpoint lease -> exact service
    -> environment session -> deterministic teardown evidence

runtime/server + resource/allocation
    target-host endpoint allocation and lifecycle truth; no project-local port
    registry

projects/sem_paper/composition
    Paper-only assembly:
    treatment selection + candidate materialization + workload tasks +
    evidence + planner + diagnostics, consuming the above interfaces

projects/sem_paper/method/self_evolving_memory
    candidate architecture materialization into a method implementation;
    it does not start servers or allocate endpoints
```

The concrete environment model is now split into two immutable values:

1. **Scientific MC environment identity**: server artifact/configuration,
   cut manifest, world seed, bridge ABI, game version and task-relevant rules.
   This is part of `environment_generation` and must match across paired
   branches.
2. **Operational endpoint binding**: target host, leased host/port and
   process/session identity. It is recorded as execution evidence but is not
   a scientific treatment difference.

`MinecraftEnvironmentImplementation.identity` now derives its artifact digest
from the scientific value only. `MinecraftEndpointSpec` holds host/port, while
`MinecraftAgentSpec` holds username/auth/version; bridge command/cwd remain
operational transport configuration. Endpoint allocation and branch lifecycle
are now implemented and tested. A durable host-scoped allocation store is
still required before concurrent or recoverable multi-process server runs.

The branch runtime must derive both from one branch request. It must never
mutate the source environment object or hide a port selection in a global
manager.

## Required migration order

1. **Complete** — add a resource-owned endpoint lease port to the MC
   scientific/operational endpoint split.
2. **Complete** — implement an environment-owned branch runtime binder with
   exact start/readiness/open/close/stop ordering and failure reconciliation.
3. **Complete** — add a Paper-owned candidate-treatment materializer; reject a
   candidate when no exact candidate session can be built.
4. Bind a frozen model/request/prompt planner as a Paper composition input;
   keep `ScriptedMinecraftPlanner` only for explicitly labeled smoke paths.
5. Compose the finished branch binding factory at the Paper production root,
   then add a layered server smoke ladder. No live paired scientific run occurs
   before all five are verified.

## Explicit non-solutions

- Do not reuse the source MC port for a branch.
- Do not make comparability ignore environment-generation mismatch.
- Do not map a candidate to the existing baseline endpoint as a fallback.
- Do not treat scripted planners as scientific model-policy evidence.
- Do not add a global service locator or project-local server registry.
