# Generic Platform Boundary

## Replaceable units

Scientific/project-specific implementations live behind stable contracts:

```text
projects/<project>/method/<project_method>/
environments/<environment>/
agent implementations
capability providers
service/process backends
storage/projection backends
```

Everything else should remain reusable infrastructure or a narrow API/runtime implementation.

## Runtime composition

```text
composition
├── StudyRuntimeComponents
├── ParticipantResolutionPort
├── ParticipantSessionLifecyclePort
├── ParticipantCheckpointOperationsPort
├── OperationDispatchPort
├── ExactServiceRuntimePort
├── model/prompt/release verification ports
├── model-request/scoped-registration/projection runtimes
└── workflow/capability/effect runtime bindings
```

`StudyRuntime` does not construct participant/workflow implementations. Concrete joining happens in `composition`.

## Implementation is not runtime

A method/agent/environment/capability implementation declares functional/scientific identity. Session runtime and endpoint identity are separate. A frozen participant binding joins implementation identity, runtime identity and configuration identity.

## Platform must not know

- `MemoryNodeSpec` or SEM CREATE/RETIRE/SPLIT/MERGE details;
- Minecraft item/entity/block types or Mineflayer commands;
- method-specific acceptance metrics;
- concrete Service OS/Model OS/Prompt OS storage layout from outside their owning system;
- concrete telemetry/forensic persistence backend from scientific/runtime code.

## Method must not know

- Minecraft transport implementation;
- tmux/systemd/process supervision;
- GPU topology/placement implementation;
- SGLang/vLLM process management;
- deployment credentials or release packaging;
- telemetry/forensics backend implementations.

## Environment must not know

- method architecture generation;
- treatment arm/candidate adoption state;
- prompt qualification internals;
- `J_mem/J_audit` semantics beyond generic evidence contracts.

## Capability policy must not know

- how effect WAL/persistence is implemented;
- how external-effect certainty is reconciled;
- how telemetry is persisted.

It can guard/approve/post-process, but it cannot bypass the effect-safe executor.

## Composition-root rule

Only composition roots may depend on unrelated concrete implementations to bind ports together. Domain/runtime packages depend on API/ports across system boundaries.

## Paper-method ownership and injected system interfaces

A concrete paper method is a scientific implementation, not a generic platform
subsystem. Its scientific state machine, method-specific evidence semantics,
treatment behavior, serving policy, and evolution policy remain owned by the
paper project:

```text
research_platform/<system>/api/       # stable contract exposed to the project
projects/<project>/composition/       # project composition root
projects/<project>/method/<method>/   # paper-owned scientific implementation
```

The platform gives a paper project interfaces and ports. It does not give the
project a platform-owned implementation to inherit or extend. The project may
implement its own adapters and policies behind those ports, provided that the
adapter does not become a second platform authority.

For Paper-1, the concrete self-evolving memory implementation is therefore
owned by `projects/sem_paper/method/self_evolving_memory`. The generic
Participant/Method system exposes `MethodCompositionPorts`, method endpoint and
runtime contracts, and observation-outbox ports. The project composition root
binds those ports to the Paper-1 implementation. The platform must not import
the Paper-1 implementation as a generic method.

The same rule applies to logging. The record leaf exposes
`LogWriterPort`/`LoggingSystemPort`; `projects/sem_paper/composition/logging.py`
binds the project-owned `SemPaperLoggingSystem` policy adapter, which enriches
records with paper identity without knowing the logging backend or storage
runtime. A later paper may provide a different policy through the same port.

The platform may centralize this binding in a frozen typed composition graph,
but not in a runtime service locator. Runtime code receives the narrowest
logging port directly. See `docs/architecture/COMPOSITION_GRAPH_AND_EVENT_SPINE_DESIGN.md`.

The following are forbidden even when they would be convenient:

- a project importing a platform `runtime`, `providers`, or unrelated
  `composition` implementation;
- the platform importing a concrete paper method to satisfy a generic default;
- moving paper scientific truth into a generic manager, registry, or service
  locator;
- treating a project-local method adapter as reusable platform authority.
