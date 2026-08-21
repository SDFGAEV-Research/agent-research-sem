# Current Development Version Notes — 2026-08-19

## 2026-08-21 frozen Paper model planner and endpoint seam

- Added the declared `model/serving/endpoint` API with an exact deployment
  request/response contract. It carries the reconstructable model request,
  deployment generation and model text response without owning scientific
  result semantics or a concrete HTTP client.
- Added `SemPaperModelPlannerFactory`, which freezes one planner prompt
  resolution, schema/policy, immutable model identity, deployment identity and
  request recorder, then exposes only `MinecraftPlannerPort` to the workload.
- Planner requests record task/state/method provenance, and response handling
  rejects identity drift, malformed JSON, undeclared fields, illegal completion
  claims and invalid Minecraft action payloads. There is no model or scripted
  fallback in this scientific adapter.
- Added a frozen-resolution path to `PromptRequestBuildTransaction` and fixed
  the MC workload boundary to consume the explicit
  `MinecraftBranchRuntimePort.environment_generation` property instead of
  inspecting an environment implementation object.
- Verification: 11 focused tests and Python compilation passed. No live model,
  server, Minecraft process or experiment was run; host-qualified endpoint
  composition remains the next step.
- Extended the endpoint seam with an exact deployment-bound route and an
  injected JSON HTTP transport. The OpenAI-compatible provider validates route
  identity before transport, requires exactly one response choice and exposes
  only transport text/token facts to the project.
- Verification: endpoint/provider, planner, prompt-binding and MC boundary
  tests passed; architecture gate passed. The provider was exercised only with
  a fake transport; no network request was sent.
- Added `FrozenDeploymentEndpointBinder`, which resolves a planner/model role
  only through the immutable `FrozenDeploymentSet`, checks route generation
  against the frozen deployment digest, and creates the endpoint only after
  exact identity validation. Missing or ambiguous routes have no fallback.
- Verification: 13 focused endpoint/planner/prompt/MC tests and architecture
  gate passed. No qualified host manifest was loaded and no endpoint network
  call was made.
- Closed a Minecraft branch-runtime concurrency hole: when RCON is enabled,
  the branch request must carry a second explicit endpoint allocation. The
  binder leases and rebinds the RCON endpoint together with the server port,
  releases both in reverse order, and rejects a template/allocation mismatch.
- Verification: 15 focused MC/endpoint/planner tests and architecture gate
  passed. No Minecraft server or RCON connection was opened.
- Hardened branch composition failure handling so a failed RCON-lease release
  cannot prevent the primary server lease from being attempted; cleanup errors
  are aggregated with the original composition cause.
- Added `SemPaperMinecraftHostInputs` and
  `SemPaperMinecraftBranchRequestFactory`. Host deployment now supplies all
  absolute server/bridge paths, server/RCON port candidates and ownership
  scope; the project creates only deterministic branch request identities and
  never allocates or selects a fallback port itself.
- Verification: 18 focused MC host/runtime, endpoint, planner and binding
  tests plus architecture gate passed. No host process or network endpoint was
  opened.
- Completed the environment-owned MC server lifecycle factory over the generic
  exact service runtime. It prepares server files under an explicit EULA policy,
  hashes the exact server artifact, creates a branch-specific service contract,
  and contributes only TCP readiness; process spawn, capture, identity, stop and
  recovery remain in the platform service OS.
- Verification: 23 focused MC server/environment/branch/host tests and
  architecture gate passed. The factory was constructed with an injected fake
  process backend; no Java, Minecraft or RCON process was started.
- Sanitized RCON secret-provider failures at the server composition boundary;
  provider exception text is preserved only as the private cause and cannot
  enter the public error message.
- Verification: 21 focused MC server/environment/branch tests and architecture
  gate passed. No secret provider connected to a real secret store.

## 2026-08-21 resource lease authority and MC endpoint allocation

- Migrated generic resource identity/ownership/lease contracts and the in-memory
  lease implementation from the old `resource/core` ownership into the declared
  `resource/lease` node; old files and imports were deleted.
- Fixed the lease invariant so one resource cannot have two active leases.
- Implemented the declared `resource/allocation` node for explicit, ordered
  network endpoint allocation. MC branches can now receive independent logical
  endpoint allocations through a platform port backed by the lease authority
  and an injected OS availability probe.
- Added structured rejection evidence and tests for deterministic candidate
  order, lease conflict, release/reallocation and probe failure. No server,
  Minecraft process, model or experiment was run.

## 2026-08-21 MC branch runtime binder

- Added the environment-owned `MinecraftBranchRuntimeFactory`. It binds a
  materialized branch work directory and level to an explicitly allocated
  endpoint, then injects a narrow server lifecycle port and MC environment
  runtime.
- Start order is server start -> readiness verification -> bridge/session open;
  cleanup is session close -> server stop -> endpoint lease release. Any start
  failure releases the endpoint without falling back to another runtime.
- The binder has no project/method imports and does not choose a model or task
  planner. Candidate/control method binding remains a project composition
  responsibility. Verification: 24 focused MC/resource tests and architecture
  gate PASS. No live service or experiment was run.

## 2026-08-21 Paper Minecraft workload binding root

- Added `SemPaperMinecraftWorkloadBindingFactory` as the project-side
  composition root between branch runtime, method endpoint, evidence routing,
  task manifest, planner and diagnostics interfaces.
- The factory opens the MC environment through the branch runtime before opening
  the method session, then closes method before environment. It requires an
  explicit candidate materializer for candidate branches and never falls back to
  the control endpoint.
- Planner, method-observation sink, branch runtime request construction and
  workload diagnostics are all injected project ports; no model, task policy or
  server concrete implementation is hidden in the binder.
- Verification: 8 focused workload/branch/candidate tests and Python
  compilation. No live service, server, model or experiment was run.

## 2026-08-21 Paper Minecraft production composition root

- Added `SemPaperMinecraftProductionRoot`, which freezes the single
  world-cut → paired-branch runner → workload executor → paired evaluator graph
  without opening a server, model or Minecraft session.
- The root takes all host/project seams explicitly, so the remaining server
  phase supplies qualified model/planner, branch request and lifecycle inputs
  rather than introducing another project-local execution path.
- Verification: production-root/workload binding/executor tests and architecture
  gate passed. No live service or experiment was run.

## 2026-08-21 candidate method materialization boundary

- Added `SemPaperCandidateMethodMaterializer`, which converts a validated
  `CandidateArchitecture` into an actual Deluxe method endpoint using its typed
  target architecture and complete node materialization contracts. Missing,
  tampered or incomplete candidate data fails explicitly; the control endpoint
  is never used as a candidate fallback.
- Candidate architecture digest is now part of the SEM implementation identity,
  so control and candidate method configurations cannot silently share one
  scientific identity.
- Fixed platform canonical encoding for `set`/`frozenset` values with stable
  normalized ordering. This was required for architecture candidate digests and
  is covered by candidate materialization tests.
- Verification: candidate materializer, architecture factory, project firewall,
  Python compilation and architecture gate. No live model, server or experiment
  was run.

## 2026-08-21 Minecraft scientific identity / operational endpoint split

- Split the MC environment contract into `MinecraftAgentSpec` (username,
  auth mode and game version) and `MinecraftEndpointSpec` (host and port).
  The JSONL bridge receives both explicitly.
- `MinecraftEnvironmentImplementation.identity` now hashes only scientific
  agent conditions and the environment ABI/provider settings. Host/port and
  bridge launch placement are instead represented by a separate operational
  binding digest.
- This makes independently leased control/candidate ports possible without
  concealing a scientific identity mismatch; a change to game version still
  changes `environment_generation`.
- Verification: Python compilation; 26 Minecraft environment/world-cut/SEM
  branch-workload tests; architecture gate PASS. No live service, server,
  model or experiment was run.

## 2026-08-21 Paper-1 Minecraft production-root audit

- Added `PAPER1_MINECRAFT_PRODUCTION_ROOT_AUDIT_20260821.md`, which separates
  implemented paired-branch/workload components from the still-missing live
  production composition root.
- Confirmed four architectural blockers before any server work: no branch
  runtime realization, endpoint conflict with the resumed source world,
  scientific identity coupled to operational endpoint, and no
  candidate-specific method-session materializer or production planner.
- The next migration is therefore an environment/runtime identity split and
  branch-runtime binder, not a project-local factory patch. No runtime or
  experiment was executed.

## 2026-08-21 run-manifest authority and remote controller identity

- Moved the sole `RunLaunchManifest` contract to
  `experimentation/run/manifest/api`; deleted the release-owned launch record
  and the runtime-manager `FrozenRuntimeManifest` rather than preserving
  compatibility aliases.
- Runtime control, model/service/participant verification, persistent-session
  binding and run-process identity now consume only the read-only
  `RuntimeLaunchManifestPort`; the host-level composition boundary alone
  receives the concrete experiment-owned record.
- A frozen launch now carries canonical capability-composition-plan references,
  exact controller argv, target-launcher SHA-256 and a secret-free controller
  environment digest. Any one of these changes produces a different
  run-process generation.
- `ServerRuntimeBootstrap` no longer receives a competing controller argv; it
  consumes the manifest and rejects environment-digest drift before creating a
  tmux session. This fixes the root cause of a Windows controller attempting
  to read the target Ubuntu path locally.
- The architecture gate initially exposed an `execution -> experimentation`
  cycle. The final repair moved only the shared controller-environment identity
  semantic to `runtime/session` and replaced execution's concrete import with
  the narrow port; no cyclic dependency was declared or whitelisted.
- Verification: Python compilation; architecture gate PASS; 75 focused
  launch/runtime/server/tmux tests; 124 Paper/SEM tests; and 63 platform
  boundary tests (one existing Windows symlink-privilege case deselected).
  No remote server, model, Minecraft or scientific experiment was run.

## 2026-08-21 Deluxe D3 diagnostic plane

- Rebuilt the current-project neutral diagnostic plane in
  `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py`.
- Added typed query/task observations, explicit incident facts, immutable
  diagnostic snapshots, ontology-free slices, bounded structural probes,
  evidence-linked hypotheses and an observation-only slow clock.
- Kept diagnostics read-only with respect to `J_mem`, candidate acceptance,
  verification, adoption and experiment comparison; no legacy runtime import
  is present.
- Verification: 3 focused tests passed, Python compilation passed, and the
  targeted legacy-import scan passed. This does not claim Deluxe completion or
  any live Minecraft/server experiment.

## 2026-08-21 paired evaluation and MC branch composition

- Added the current-contract `PairedBranchEvaluator` for control/candidate
  receipts and explicit metric deltas.
- Added `MinecraftPairedBranchRunner`, which enforces one prepared source-world
  cut, isolated branch materialization, injected workload execution and
  mandatory cleanup.
- Hardened platform comparability proof to reject reused branch identities.
- Verification: 22 focused tests and compilation passed. The concrete
  service/participant/Planner/SEM/workload executor and live server ladder are
  still not implemented or run.

## 2026-08-21 MC workload ABI adapter

- Added `MinecraftWorkloadEnvironmentAdapter` to translate the generic MC
  environment session into the Paper workload contract.
- Missing or malformed authoritative state now fails explicitly; no empty
  state is fabricated.
- Verification: 9 workload/branch/adapter tests and compilation passed. The
  concrete server-to-workload executor and live ladder remain pending.

## 2026-08-21 branch workload executor

- Added `MinecraftWorkloadBranchExecutor` for task-manifest execution through
  injected environment, SEM, evidence, Planner and diagnostics bindings.
- Added explicit aggregate branch metrics and close-failure propagation.
- Verification: 6 executor/adapter/branch tests and compilation passed. Real
  service, participant, Deluxe and model bindings remain pending.

## 2026-08-21 current SEM architecture presets and typed builder

- Added current-project `SemPaperArchitecturePreset.C/X` builders under the
  SEM architecture namespace; old v034 seed YAML remains reference evidence,
  not a runtime import.
- Added `ArchitectureDrivenTypedNodeBuilder` and an explicit injected semantic
  transform seam. It routes only declared J_mem event types and architecture
  upstream records, with no flat or empty fallback.
- Added the current-project live Deluxe factory composition over a selected
  preset and exact materialization contracts.
- Fixed Deluxe capability projection to deduplicate repeated field output
  types while preserving the full typed schema.
- Verification: 19 architecture/materialization/projection tests, 30 focused
  Deluxe/MC/evolution tests, compilation, diff check and legacy-import scan
  passed. No live model, server or Minecraft experiment was run.

The current development worktree remains package version `0.41.0` but is **ahead of the last verified release**. Release evidence remains frozen at the prior release; this file describes development-state changes only.

## Final architecture migration foundation

The direct final-architecture migration is now an active workstream governed
by `FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md` and
`FINAL_ARCHITECTURE_MIGRATION_MATRIX.md`.

- The 180-node system registry now materializes `owns`, `must_not_own`, and
  the standard `api/runtime/providers/composition` shape from the canonical
  catalog instead of silently dropping those fields at runtime.
- The canonical catalog is now packaged under
  `research_platform/governance/system_registry/catalog.json`; the `docs/`
  copy is checked as an exact mirror, so installed/server runs do not depend
  on the repository working directory.
- Release quality evidence is now a release API port injected by the platform
  composition root. The reverse dependency from governance release runtime to
  platform composition was removed, and the old governance composition entry
  was physically deleted.
- Workflow dispatch authority checks are now path-separator independent on
  Windows; the previous false failures were caused by comparing backslash
  paths with slash-separated authority records.
- Current structural verification: architecture gate PASS, package cycles 0,
  workflow invariant findings 0, CodeGraph circular-dependency check 0, and
  the four architecture analyzer unit tests PASS.

The full regression suite has not been rerun after these migration slices, so
the historical 709-test result below is not being promoted to current proof.
The local worktree has no Git repository; these changes therefore cannot yet
be committed or tagged.

## Harness-pattern integration

Added without adopting Cordis or an everything-is-a-plugin runtime:

- `model_request_api/runtime`: content-addressed, reconstructable model-visible requests bound to full immutable model identity and prompt generation.
- `scope_api/runtime`: hierarchical, reversible, quiescent registration lifetime management.
- `capability_runtime`: monotonic guards + approval + post-policy wrapped around the existing effect-safe execution engine.
- `projection_api/runtime`: source/version/watermark-bound incremental tails with fail-closed rebuild requirements.
- `record_api` + `fact_api`: Durable Fact / Live Interception / Side-Plane Observation semantics and fail-closed unknown required facts.
- architecture seam graphs: generated capability/operation/event producer-consumer views.

## Current verification

- 709 tests collected.
- 709 passed + 4 subtests in the latest complete development regression.
- Architecture gate PASS.
- Silent-Failure audit PASS.
- No-Degradation audit PASS.
- Architecture report SHA-256: `a5a7148a7d1d88b17105e85aef5a6bc6db9a4f48111316f1ff52fe0059f9ad70`.

## Policy unchanged

No compatibility layer is retained merely to preserve pre-run APIs. No lower-quality fallback is introduced. Runtime/backend changes must not silently change scientific identity, model identity, effect semantics, prompt identity or release reproducibility.

## 2026-08-21 host OS and target-path routing / Windows durability slice

- Promoted host OS identity and conventions to the `runtime/host` API/provider
  route (`OperatingSystemRoute`), and promoted cross-controller target-path
  semantics to `scope/path`. Session, service, tmux, artifact, server and
  Minecraft contracts now use one absolute-target-path authority.
- Local service composition now routes the process backend by host OS and
  refuses to silently use Linux `/proc` semantics on unsupported hosts.
- Windows interprocess locking now uses a path-derived named Mutex; the marker
  file remains observable but is not held open, preventing abandoned leases
  from pinning temporary trees while preserving one lock domain.
- Model-request ledgers and prompt publication reuse the platform lock
  authority. Raw/capture byte writers explicitly use binary mode on Windows;
  telemetry retries close failed writer sessions while retaining pending rows.
- Release regression process cleanup now has a Windows process-tree route;
  remote POSIX tmux paths are preserved instead of being rewritten by the
  controller's local `Path` flavor.
- Verification: 74 focused architecture/durability/forensics/prompt/path
  tests passed; 17 focused capture/telemetry/release/path tests passed after
  the binary and OS-route fixes. The full suite is not yet promoted: remaining
  failures are isolated to Linux `/proc`/signal assumptions, Windows symlink
  privilege, cross-host server-launcher fixtures, and direct test-owned SQLite
  connections that are not closed on Windows.

For historical Round 02 notes, use the repository history or older round documents; this file now serves as the current development summary.

## 2026-08-21 typed composition plan and explicit host injection slice

- Added a frozen, typed capability-composition core with explicit offer,
  requirement, scope, interface-digest, provider-selection, locality and
  cycle semantics. `BindingPlan` is metadata-only and cannot act as a runtime
  resolver.
- Migrated the first concrete runtime slice: host OS route selection is owned
  only by `runtime/host` composition; server identity consumes the explicit
  host port and emits its own binding evidence; logging emits record/storage
  leaf binding evidence.
- Removed the old construction APIs instead of preserving aliases. Minecraft
  JSONL, generic service runtime and model service runtime now require injected
  `OperatingSystemRoute`.
- Added architecture invariants that reject capability graph imports from
  runtime modules and direct local-OS provider selection outside host
  composition.
- The initial implementation placed the graph under the outer
  `platform/composition` root and the package-cycle gate correctly rejected
  the resulting reverse leaf-to-root dependency. The graph was moved to the
  architecture system and then split into `governance/architecture/api`
  (immutable plan contracts and planner port) and
  `governance/architecture/runtime` (concrete validator). This prevents a
  project from depending on a system composition implementation while keeping
  the import graph acyclic. The repair changed the ownership boundary rather
  than weakening the cycle gate.
- Focused verification: 39 capability/logging/host/server/MC/project tests
  passed. A wider 56-test run exposed one pre-existing Windows symlink
  privilege failure in a model-asset test; it was not worked around or used as
  evidence for this slice. No server, model or Minecraft experiment was run.

## 2026-08-21 project-safe capability composition follow-up

- Added a `CompositionSubject` distinction between catalog-governed systems
  and independently versioned projects. A project may compose only itself and
  can consume platform capability offers only through a recorded import; it is
  not silently inserted into the platform system tree.
- Moved the logging and Participant/Method binding result values into their
  public APIs. Paper-1 now receives `LoggingSystemBinding`,
  `MethodSystemBinding`, and the public planner port; it no longer imports a
  concrete platform composition module or planner.
- Declared the resulting real dependencies locally in the canonical topology:
  `governance/architecture -> scope` and
  `participant/method -> governance`. No top-level dependency cycle was
  introduced.
- Verification: architecture gate PASS; 22 catalog/capability/project-firewall
  tests and 48 host/server/logging/MC/management tests passed (one unrelated
  Windows symlink privilege test was deliberately deselected). No live server,
  model, or Minecraft experiment was run.

## 2026-08-21 managed server identity and SSH connection route

Server connection is now a runtime/server identity concern rather than an
ad-hoc shell command in a project or script:

- `runtime/server/identity/api` owns the non-secret server profile, command
  result and health report contracts.
- `runtime/server/identity/providers/ssh.py` is the OpenSSH provider. It
  receives the host OS route and owns only argv construction plus remote
  command/result semantics; it never places a password in argv or invokes a
  local shell.
- `EnvironmentSSHServerConnectionFactory` reads one logical server profile
  from `RP_SERVER_<ID>_HOST`, `_PORT`, `_USER`, optional `_KEY_PATH`,
  `_KNOWN_HOSTS`, `_SSH_CONFIG` and `_SSH`. The repository contains no server address,
  account, password or private key.
- `scripts/server_health.py` is the operational entry point. It returns a
  machine-readable health report and non-zero status on an unreachable host.
  Automated operation requires an SSH key or agent; `--interactive` can be
  used when OpenSSH must prompt on a terminal.

The provider is explicitly composed with `runtime/host`'s OS route and is
covered by the source-authority architecture gate. The server route is
designed for multiple logical servers; changing the target means selecting a
different environment profile, not editing Python.

The persistent operator shell is owned by `scripts/server_session.py`: it
ensures a named remote tmux session, reports its pane identity/current path,
and provides an explicit interactive attach operation. A verified
`research-platform-shell` session now survives SSH disconnects on `sem-ubuntu`.
This shell is operator state only and is deliberately not used as scientific
run-health evidence.

The Windows OpenSSH route initially failed before authentication because the
user config contained a stale unresolved SID. The local ACL was repaired by
removing inherited entries and granting only the current user, SYSTEM and
Administrators. OpenSSH parsing and the managed session status command then
returned successfully. No credential or host secret was added to the
repository.

## 2026-08-21 Minecraft world-copy capability boundary

The first Ubuntu scripted smoke reached Minecraft startup, TCP readiness, RCON
and the save barrier, then failed because the `/data` filesystem does not
support `cp --reflink=always`. The world-cut provider now keeps strict reflink
behavior by default and accepts an explicitly injected filesystem copier only
for a declared capability fallback. The SEM composition records the fallback
as `WORLD_COPY_COPIER_FALLBACK`; all unrelated copy errors remain fail-closed.
The branch error also preserves its underlying cause and cleanup cause in the
top-level message. The failed run is infrastructure evidence only and is not
counted as a scientific result.

## 2026-08-21 Minecraft RCON readiness contract

The source Minecraft service no longer reports ready solely from its game TCP
port. When RCON is configured, `MinecraftServerReadinessProbe` also requires a
successful read-only `list` command and binds both evidence references into
the readiness identity. This fixes the observed startup race where TCP was
open before the RCON listener accepted `save-off`; refusal is retried within
the service readiness window and never produces a false ready state.

## 2026-08-21 Minecraft username protocol contract

The Minecraft agent contract now rejects usernames outside the protocol
language `[A-Za-z0-9_]{3,16}` before bridge composition. The previous default
`ResearchPlatformBot` was 19 characters and caused the remote bridge to be
kicked after the server was otherwise ready. The platform and Mineflayer
bridge default is now `ResearchBot`; no truncation or fallback identity is
used. A focused regression test covers the invalid default and invalid
characters.

## 2026-08-21 server-side Minecraft smoke closure

Commit `6a1bb31` passed the server-side focused Minecraft suite (`30 passed`)
and completed the fourth scripted Minecraft smoke with zero durable failure
rows. The smoke result remains explicitly `scientific_claim=false`. The
server audit also recorded that the exact paper Minecraft artifact and model
deployment are still missing; no model-backed baseline was started against a
version-mismatched or unqualified environment.

The exact vanilla Minecraft 1.21.8 artifact was subsequently downloaded from
Mojang's content-addressed URL and verified on the server with SHA-256
`2349d9a8f0d4be2c40e7692890ef46a4b07015e7955b075460d02793be7fbbe7`.
Its preflight and scripted smoke both passed with zero durable failure rows.
The model-backed baseline remains intentionally blocked until a model
deployment is qualified and frozen.

The server management attempt also removed the stale console entry point that
referenced the deleted pre-migration operator module. `research-platform-manage`
now resolves directly to the current runtime-management composition root; no
old alias was retained.

Management commands now fail closed when a managed Python subprocess returns a
nonzero code. This prevents `env check`, package installation, and related
environment operations from being reported as successful envelopes while the
underlying command failed.

## 2026-08-21 recursive governance gate system

Governance gates now have their own registered `governance/gate` subsystem.
`GatePort`, `GateRequest`, `GateFinding` and `GateReport` form the only public
contract. `CompositeGate` recursively aggregates explicitly injected child
gates, preserves child reports as provenance and fails closed when a child
cannot produce a report. The parent does not discover a global rule registry.

The existing architecture analyzer is exposed through this contract by the
governance composition root. Future quality, security, release, server and
project gates can be supplied by each parent system through the same port and
can define their own child hierarchy without importing gate implementations
from unrelated systems. The old analyzer remains the architecture provider;
this slice changes ownership and composition, not the analyzer's scientific or
runtime semantics.

## 2026-08-21 typed composition graph and logging boundary decision

- Accepted the three-plane architecture in
  `docs/COMPOSITION_GRAPH_AND_EVENT_SPINE_DESIGN.md`: typed capability
  composition graph, direct runtime ports, and a separate event spine.
- Explicitly rejected a universal mutable runtime bus/service locator. The
  composition graph centralizes requirements, provider selection, validation,
  freeze/digest and recursive binding; runtime modules receive direct typed
  ports and cannot perform ambient capability lookup.
- Migrated the current logging project seam to `LoggingSystemPort` and
  `LogWriterPort`; project policy remains an adapter and reliability remains
  the failure authority.
- Verification: architecture gate PASS; 22 focused logging/project/Minecraft
  tests passed; 59 architecture/source/authority/release tests passed.

## 2026-08-21 server health ownership cutover

- Removed live-health semantics from `runtime/server/identity`: the identity
  connection port now exposes only non-secret profile identity and remote
  command execution, while `ServerHealthReport` and the health probe port are
  owned by `runtime/server/health`.
- Added `SSHServerHealthProbe` and a health composition function. The existing
  operational `server_health` entry point now composes identity and health
  explicitly; it does not call a health method hidden inside the connection
  provider.
- Physically removed the old identity health contract and provider method. No
  compatibility export or alternate health path was retained.
- Verification: 8 focused server/path tests, 38 server/MC/runtime tests,
  Python compilation and architecture gate passed. No remote host, server,
  model or Minecraft process was started.

## 2026-08-21 server file transfer and immutable release publication

- Added a separate `ServerFileTransferPort` and OpenSSH/scp provider. Server
  identity composition now exposes command execution and file transfer as two
  explicit ports, with a new capability identity; no password is represented
  in either profile or argv.
- Implemented `runtime/server/lifecycle` immutable release publication:
  explicit POSIX target layout, digest-named incoming/staging/release paths,
  exact package transfer, remote SHA-256 verification, ZIP path-traversal
  rejection, required release manifest/evidence checks, and atomic directory
  publication. A matching marker is the only idempotent reuse path; a
  conflicting or incomplete release stops with a typed phase error.
- No project, Minecraft, model or health module owns SSH, scp, release paths or
  deployment state.
- Verification: 13 server/transfer/release/path tests, 25 MC/model/production
  root tests, compilation and architecture gate passed. No remote host or
  release was contacted.

## 2026-08-21 server/session runtime ownership migration

- Moved frozen controller command identity and persistent-session host mapping
  from `execution/runtime/manager` into `runtime/session` with narrow API
  ports.
- Moved immutable release lookup, session-policy validation and controller
  bootstrap from `platform/composition/runtime_control` into
  `runtime/server/lifecycle/runtime`.
- Deleted both old modules and rewired all callers without compatibility
  aliases. Server lifecycle now receives a session host port rather than a
  concrete session runtime.
- Verification: 37 focused server/session/tmux/release tests, compilation and
  architecture gate passed. No live server or remote host was used.

## 2026-08-21 runtime-control composition retirement

- Moved the cross-system operation executor binding to
  `platform/composition/operation`.
- Moved release consumer probes and the quiescence proof join to
  `governance/release/composition`.
- Physically removed the historical `platform/composition/runtime_control`
  modules, generated bytecode, and source guardrails; no compatibility path was
  retained.
- Verification: 61 focused tests passed with 4 subtests, Python compilation
  passed, and no live server/model/Minecraft process was used.

## 2026-08-21 Hugging Face model acquisition boundary repair

- Fixed the model asset provider to avoid the incompatible Hugging Face CLI
  combination `--local-dir` plus `--cache-dir`; the managed cache is now
  supplied through `HF_HOME` while the model remains materialized in the
  selected platform storage pool.
- Corrected the server management configuration to use the absolute `hf`
  executable from the verified `qwen36-sglang` environment.
- Root cause was confirmed from the platform-managed fetch log. No model asset
  was registered or downloaded by the failed attempt. Server-only regression
  and fixed-revision model acquisition are the next verification gate.
- Corrected the focused test fixture to address the nested directory-layout
  path exposed by the first server rerun; the production provider was not
  changed by that correction.
