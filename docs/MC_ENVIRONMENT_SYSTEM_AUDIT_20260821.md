# Minecraft Environment System Audit — 2026-08-21

## Conclusion

The current platform now contains a contract-level Minecraft environment
system with an executable provider/session path, but it is not yet qualified
for a live server or scientific run. The distinction is important: the
provider can be exercised with a deterministic process double and the generic
participant endpoint can now be composed, while a real Java server, Node
dependency installation and server-side readiness qualification are still absent.

It contains a generic environment ABI and management foundation:

- `research_platform.environment.runtime.api` defines `EnvironmentSession`,
  `ActionRequest`, `ActionResult`, observations, identity and recovery
  contracts;
- `research_platform.environment.catalog` owns logical environment specs,
  scoped resolution, instances and bindings;
- `research_platform.environment.python` owns Python/Conda environment
  management;
- the generic action workflow owns effect intent, dispatch, reconciliation and
  crash-recovery semantics;
- runtime process/service modules provide reusable process and service seams.

`research_platform.environment.minecraft` now owns Minecraft-specific
contracts, action validation, state projection, Mineflayer/JSONL transport,
readiness probes, server-file preparation and service composition. It is
registered in the system topology and is reachable through a generic
participant endpoint composition adapter. It still does not own Java process
supervision or scientific task orchestration.

The former `memory-evolving/v034_work/mc_runtime` tree contains a useful
reference implementation, including a Mineflayer JSONL bridge, verified state,
server preparation and task execution. It is an old architecture and is not a
current production authority. It must be migrated through current interfaces,
with ownership and deletion evidence, rather than imported as a second runtime.

## Target ownership

```text
environment                         generic specs, bindings and instances
└── minecraft                       Minecraft semantics and provider family
    ├── api                         MC contracts and provider seams
    ├── runtime                      MC session lifecycle and action/observation semantics
    ├── providers                    Mineflayer/JSONL and future transport adapters
    └── composition                  joins MC adapters to generic Environment ABI

runtime/process or runtime/service   process/server lifecycle and capture
environment/minecraft                must not own generic process supervision
projects/sem_paper                   task manifests and paper-specific workloads
```

The MC module may know Minecraft action and observation semantics. It must not
know SEM architecture generations, treatment assignment, prompt qualification,
memory evidence ownership, model serving internals, or concrete telemetry
storage. It receives process/service and diagnostic interfaces at composition.

## Required first executable slice

The first slice will provide:

1. an immutable MC endpoint/agent specification with a stable digest;
2. an MC bridge interface independent of Mineflayer;
3. a generic `EnvironmentImplementation` adapter and session implementing
   `observe`, `act`, `checkpoint`, `restore`, `reconcile` and `close`;
4. explicit action identity and verified/unverified outcome semantics;
5. a timeout-bounded JSONL Mineflayer adapter with complete stdout/stderr
   capture and explicit failure classification;
6. an injected world-checkpoint/reconciliation seam that fails closed when the
   environment cannot prove recovery;
7. architecture and integration tests using an in-memory bridge double, without
   pretending that a double is a Minecraft result.

The Java server lifecycle and Mineflayer bridge process must be composed from
the platform process/service seams. No MC module may silently launch a server,
accept a stale port, or treat a running tmux pane as readiness.

## Migration gates

A migrated MC slice is not complete when files merely exist. It must have:

- a registered topology node and matching canonical catalog entry;
- API/runtime/provider/composition ownership with no old `mc_runtime` import;
- source and import-graph checks proving generic method code remains MC-free;
- focused contract, identity, timeout, recovery and checkpoint tests;
- Python compile and full platform regression;
- explicit absence/deletion evidence for the migrated old owner;
- a server-side smoke qualification before any scientific claim.

Until the final gates pass, the platform may claim only MC adapter contract
coverage, never a live Minecraft experiment or paper result.

## v034 reuse matrix

The old tree is treated as a reference implementation, not as an importable
package. The migration decision is made per responsibility, because one old
file often mixes environment semantics with project orchestration or scientific
gating.

| v034 source | Reuse decision | New owner | Required treatment |
|---|---|---|---|
| `mc_runtime/protocol.py` | Reuse the data model and validation rules | `environment/minecraft/api` | Recreate the event envelope under the current namespace. Preserve event kind, timestamp, source and bridge sequence. Remove all v034 imports and define the current protocol version explicitly. |
| `mc_runtime/bridge.py` | Reuse the transport behavior, not the module | `environment/minecraft/providers` | Reimplement the timeout-bounded JSONL client behind `MinecraftBridgePort`. Keep concurrent stdout/stderr draining, stderr tail capture, EOF/timeout distinction and process-group cleanup. Route diagnostics through injected current-platform seams. |
| `mc_runtime/agent_connection.py` | Reuse connection state machine | `environment/minecraft/providers` | Split startup/handshake, command correlation, event forwarding and shutdown. Inject command executable/bridge path; add action identity/request digest correlation. Do not retain v034 metrics, logger or `reliability` imports. |
| `mc_runtime/state.py` | Reuse most of the MC state reduction logic | `environment/minecraft/runtime` | Adapt `VerifiedMinecraftState` to the new event contract. Make snapshot/digest semantics explicit, bound entity retention, and keep it as environment read-model state rather than memory or task state. |
| `mc_runtime/preflight.py` | Reuse probe algorithms and version parsing | `environment/minecraft/instance/readiness` | Return typed readiness observations with phase, cause code, command, exit status and captured output. Compose Node/Java/package/TCP probes; never infer readiness from a process, port or tmux pane alone. |
| `mc_runtime/local_server.py` pure parts | Reuse specification and deterministic file logic | `environment/minecraft/api` plus `environment/minecraft/composition` | Preserve server configuration validation, SHA-256 artifact identity, stable `server.properties` rendering and TCP probe. Adapt them to platform artifact/resource/runtime contracts. EULA acceptance must be an explicit run policy. |
| `mc_runtime/local_server.py` process parts | Do not copy implementation | `runtime/service` composed by MC composition | The generic service/process system owns launch, capture, identity, readiness, stop, restart and recovery. MC supplies a service launch contract and an MC-specific readiness adapter. |
| `mc_runtime/server_download.py` | Reuse official metadata/checksum algorithm | artifact/resource system, composed by MC | Move acquisition to the platform artifact owner. Retain official manifest lookup, SHA-1 verification and atomic partial-download replacement. MC should only declare the required server artifact. |
| `mc_runtime/provenance.py` | Reuse generic hashing ideas only | artifact/provenance system | Do not duplicate the global source-tree or runtime fingerprint authority. Extract only MC-specific artifact facts if the platform lacks them; otherwise bind to the existing digest API. |
| `mc_runtime/mineflayer_bridge/package.json` | Reuse dependency versions as a pinned input | MC provider asset | Add a lockfile and a platform-owned bridge asset manifest. Keep Mineflayer/pathfinder/Node versions explicit and verify them at readiness time. |
| `mc_runtime/mineflayer_bridge/bridge.js` | Reuse as an external adapter baseline | `environment/minecraft/providers` asset | Preserve grounded actions and snapshots, but add request/action identity, protocol version and structured error fields. Keep stdout JSONL-only. Remove task/memory/evolution fields from the provider contract; those belong to the project composition root. |
| `mc_runtime/admission.py` | Do not move as a whole | project/evidence composition | The event-to-evidence mapping is useful for the paper but it imports the old evidence owner and task semantics. Split raw event normalization into MC runtime and evidence admission into the project/evidence adapter. |
| `mc_runtime/query.py` | Do not move | memory system | It is only a compatibility facade over the old memory runtime. The MC environment must not own memory querying. |
| `mc_runtime/planner.py` | Do not move | project method / participant agent | Tool schema validation is reusable as a method-level contract, but LLM client, prompting, retrieval context and planner decisions must remain outside the environment provider. |
| `mc_runtime/semantic_executor.py` | Do not move | model/agent or project method system | It is an LLM-backed memory semantic executor, not an environment concern. |
| `mc_runtime/task_runner.py` | Do not move | experiment/project composition | It couples benchmark tasks, memory session, planner, connection and success criteria. Replace it with a project workload adapter that consumes the generic participant/environment interfaces. |
| `mc_runtime/fixed_smoke.py` and `smoke_executor.py` | Reuse test intent, not runtime ownership | experiment validation | Rewrite smoke cases against the current environment participant and effect workflow. Keep them as validation artifacts, not production MC runtime modules. |
| `mc_runtime/evidence_bundle.py` | Do not move as MC runtime | evidence/artifact system | Bundle integrity and provenance are valuable, but T2B schema and scientific gate semantics belong to experiment/evidence governance. Bind to platform artifact/provenance APIs instead of copying the old bundle authority. |
| `mc_runtime/gate_state.py` | Do not move as MC runtime | experiment governance | T3 unlock is a paper workflow gate, not Minecraft environment behavior. Migrate only after the experiment governance owner is established. |
| `mc_runtime/t2b_integrity.py` | Do not move as MC runtime | project/evidence validation | It audits memory grounding and therefore crosses into memory/evidence semantics. Keep the audit concept in the project validation layer. |
| `mc_runtime/planner.py::validate_tool_args` | Reuse invariants, rewrite module | `environment/minecraft/api/actions.py` | Normalize bounded action payloads before the provider seam. Keep LLM planning and rationale outside the environment. |
| `operations/minecraft_service.py` | Do not copy | composition root | It is the old broad service locator: server process, Mineflayer connection, task runner, metrics and PID files are fused. Use it only as a migration inventory and delete it after its responsibilities are rehomed. |
| `operations/server_recovery.py` | Do not copy into MC | runtime/server and operations governance | Recovery planning is valuable, but it belongs to the platform server/runtime governance system and must be rebuilt on current leases, deployment identity and diagnostic runs. |

### What can be reused immediately

The first migration slice should therefore extract four things from v034:

1. the strict JSONL event envelope and command/ack protocol;
2. the timeout-bounded bridge connection state machine with complete stream capture;
3. the verified Minecraft state reduction and deterministic snapshot;
4. the Node/Java/Mineflayer/pathfinder/TCP readiness probes.

These four form one coherent environment provider path. They do not introduce a
second memory, planner, evidence store or server supervisor. The remaining v034
files are either project-level adapters or historical gate implementations and
must be migrated only under their corresponding platform owners.

### Reuse boundary

“Reuse” here means preserving a tested behavior or data invariant while
rewriting the module against current interfaces. It does not mean importing
`memory-evolving/v034_work` on `sys.path`, keeping `mc_runtime` as a compatibility
package, or copying the old service object. After each slice, an import-graph
check must show no current production module importing the old tree; only audit
documents may mention it until deletion evidence is recorded.

## First extraction status

The following current-platform files now contain rewritten extractions of the
first four reusable responsibilities:

- `research_platform/environment/minecraft/api/contracts.py`: strict bridge
  envelope and observation identity;
- `research_platform/environment/minecraft/runtime/state.py`: bounded,
  deterministic Minecraft state projection;
- `research_platform/environment/minecraft/providers/readiness.py`: actionable
  Node, Java, package, pathfinder and TCP probes;
- `research_platform/environment/minecraft/providers/jsonl_bridge.py`:
  timeout-bounded JSONL transport with stdout/stderr draining, command
  correlation, action proof cache and process cleanup.

This is an adapter-contract slice, not a live Minecraft qualification. The
provider has an injectable process factory for deterministic tests; the Java
server lifecycle is still intentionally absent and must be composed through
the platform service/runtime system before a server run is allowed. The old
`mc_runtime` package remains untouched as a reference until the complete
production call chain has been migrated and its deletion gate passes.

The bridge asset declares the v034-verified Mineflayer and pathfinder versions
(`4.37.1` and `2.4.5`) and requires Node `>=22`. A Node 22/npm 10 lockfile is
now present at
`environment/minecraft/providers/assets/mineflayer_bridge/package-lock.json`,
with lockfile version 3, official npm tarball URLs and integrity hashes. The
lockfile is a dependency identity artifact; it does not mean dependencies have
been installed or that the bridge has connected to a server.

The official npm audit reports six moderate transitive findings through the
offline-capable Mineflayer authentication/protocol dependency chain. The only
automatic fix offered by the registry is a semver-major Mineflayer `1.4.0`
proposal, which is not a valid upgrade path from the pinned `4.37.1` provider.
No forced audit fix was applied. Server qualification must explicitly use
`auth=offline`, keep the pinned dependency identity, and record this audit
result as deployment risk until a compatible upstream fix or reviewed provider
replacement exists.

## Server lifecycle and diagnostic seam status

The second extraction slice now adds:

- `MinecraftServerSpec` and `MinecraftServerPreparedFiles` in the MC API;
- `providers/server_files.py` for deterministic `server.properties`, SHA-256
  artifact identity, atomic configuration writes and explicit EULA policy;
- `composition/server_service.py` for translating an MC server specification
  into the platform `ServiceLaunchContract`, using the injected
  `ExactServiceRuntimePort`, and for MC-specific TCP readiness;
- `MinecraftDiagnosticsPort`, consumed by the bridge/session/server composition
  without importing a logging or failure storage backend.

The server controller does not own `Popen`, tmux, systemd, process identity,
capture, restart or recovery. Those remain the platform service authority. A
Paper project or platform composition root can adapt its own structured logger,
failure ledger and metrics recorder to `MinecraftDiagnosticsPort`; all MC
events carry a phase and correlation reference, while the final sink/query
authority remains outside MC.

The controller is therefore service-port qualified but not yet server-run
qualified: the target service composition still needs a concrete Linux service
provider, installation from the pinned lockfile, and a server-side readiness
smoke before any experiment execution.

## Round 107 status: session state and action contract closure

The MC session path now performs two additional responsibilities that were
missing from the earlier adapter-only slice:

1. `api/actions.py` validates and normalizes every external MC action before
   calling the bridge. It rejects unknown fields, malformed coordinates,
   non-finite numbers, invalid ranges and missing semantic identifiers with a
   stable action-contract code.
2. `runtime/session.py` owns one bounded `MinecraftStateProjection` per
   session. All bridge events returned by `observe` and `act` are ingested
   before the `Observation` is returned. The observation contains the compact
   state and its digest; the session diagnostics expose the digest and state
   sequence without exposing an unbounded history.

The composition leaf also exposes
`compose_minecraft_participant_endpoint()`, which joins the MC implementation
and session runtime through the platform's generic
`LocalParticipantRuntimeEndpoint`. No MC-specific second lifecycle endpoint or
service locator was added.

Focused verification for this slice: 12 MC tests passed, 32 MC + SEM projection
tests passed, and the broader MC/architecture subset passed 82 tests. Python
compilation passed, and the production import scan found no `mc_runtime`,
`memory_runtime`, `memory_ir` or `v034_work` imports. This remains
contract/provider evidence only; no Minecraft server, Node bridge, model or
scientific experiment was run.

## Diagnostic composition status

The MC runtime does not import a concrete logger, metric registry, failure
catalog, ledger, or persistence backend. Its only diagnostic dependency is
`MinecraftDiagnosticsPort`. The composition layer now provides
`StructuredMinecraftDiagnostics`, which translates that seam into:

- the platform `StructuredLogger` for structured events and exception records;
- the platform `ContextMetricSink` for context-bound metrics;
- an injected failure materializer and `FailureLedgerPort` for durable failure
  envelopes.

The failure materializer is deliberately injected. MC provider codes such as
`BRIDGE_STDOUT_EOF` are transport facts, while failure taxonomy, recovery and
scientific-risk semantics remain owned by the platform/project composition.
When an observability sink fails, the adapter retains a bounded diagnostic-error
tail; it does not hide the primary environment error or silently claim that the
diagnostic write succeeded.

## Round 108 status: process-signal ownership and v034 reuse audit

The current JSONL provider no longer calls `os.killpg` directly. The old
process-group cleanup behavior is represented by an injected
`ProcessTerminator` seam, while the provider retains a local terminate/kill
fallback for test doubles and hosts that do not supply a group-aware policy.
Platform service composition remains the owner of the production process-group
termination policy. This closes the source-authority violation without copying
the old supervisor into the MC environment.

The old `mc_runtime` audit was rechecked file by file. The reusable behavior is
now classified as follows:

- Already rewritten under current ownership: wire envelope, JSONL transport,
  action/request correlation, bounded state projection, readiness probes,
  server-file preparation and the Mineflayer bridge asset baseline.
- Still required but not yet moved: official vanilla-server acquisition with
  Mojang manifest SHA-1 verification; it belongs under artifact acquisition,
  not the MC runtime.
- Required at the Paper project boundary: Mineflayer-event-to-evidence
  admission, grounding audit and the T2/T3 evidence bundle; these are workload
  and experiment governance, not environment behavior.
- Required as a project workload adapter: the old task runner's decision-cycle
  and success-predicate semantics. Its benchmark, memory and planner coupling
  must be rewritten against the generic participant/environment ABI.
- Not reusable as MC code: the old query facade, semantic memory executor,
  LLM planner implementation, broad service locator, and paper-specific gate
  state.

The old tree remains a read-only migration reference until the current Paper
workload call chain, artifact acquisition, service provider and evidence
qualification are live. No old compatibility import or `sys.path` injection is
allowed.

## Round 109 status: artifact, evidence and workload ownership

The next v034 responsibilities have now been rehomed:

- official server acquisition is an artifact/content operation with a
  Minecraft-only official-manifest adapter;
- MC event admission is a Paper composition adapter with explicit `J_mem` /
  `J_audit` routing;
- task execution is a Paper workload adapter over injected environment,
  method, evidence, planner and diagnostic ports.

The MC environment system is therefore present at the API/runtime/provider/
composition level and has a current project workload path. It is still not a
live qualification: the Linux service implementation, dependency installation,
server readiness smoke and baseline experiment remain outstanding.

## Round 110 status: generic service composition

The reusable local service composition authority has now moved from
`platform/composition` into `runtime/service/composition`:

- `build_service_supervisor` is owned by the runtime/service composition node;
- `LocalServiceRuntimeComposer` assembles explicit state, start-intent,
  capture, environment, process and readiness seams;
- the old pass-through `platform/composition/service_supervisor.py` was deleted
  after all imports were migrated;
- MC binds its TCP readiness probe through
  `compose_minecraft_server_service_runtime` and contributes no process
  supervisor.

The target-host service tests remain pending: two existing tests require POSIX
`fcntl` and directory `fsync` and cannot qualify on this Windows controller.
This is recorded as an environment qualification limit, not handled by a
degraded Windows implementation. No live server or scientific run has been
claimed.
