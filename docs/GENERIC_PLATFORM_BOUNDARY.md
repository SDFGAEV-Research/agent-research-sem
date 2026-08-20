# Generic Platform Boundary

## Replaceable units

Scientific/project-specific implementations live behind stable contracts:

```text
methods/<project_method>/
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
