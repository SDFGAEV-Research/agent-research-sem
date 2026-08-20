# Round 110 — generic service composition and Minecraft binding

## Scope

This round moves the reusable local service composition authority out of the
platform composition area into `runtime/service/composition`. The old
`platform/composition/service_supervisor.py` module was a pass-through
composition owner and has been deleted after all production and test imports
were migrated.

## Service ownership change

`runtime/service/composition/supervisor.py` now owns construction of an exact
service supervisor from explicit state, start-intent and process seams.

`runtime/service/composition/local_runtime.py` adds
`LocalServiceRuntimeComposer`. It binds:

- exact service state and start-intent storage;
- deterministic stdout/stderr capture paths;
- a complete materialized environment whose digest must equal the frozen
  launch contract;
- the injected readiness probe;
- the platform Linux process backend by default;
- the existing crash-aware service supervisor.

The composer does not know whether the executable is Minecraft, a model server
or a future project runtime. It does not add a second process authority.

## Minecraft binding

`environment/minecraft/composition/server_service.py` now exposes
`compose_minecraft_server_service_runtime`. Minecraft contributes only
`MinecraftTcpReadinessProbe`; launch, process identity, capture, state,
stop and recovery stay in `runtime/service`.

This closes the v034 `local_server.py` process-ownership migration path without
copying its process implementation into MC. The function is composition-only:
the caller still injects the service roots, complete environment and optional
process backend.

## Verification

- MC/environment, service-composition, project firewall and architecture tests:
  68 passed;
- two existing service persistence tests remain non-runnable on this Windows
  controller because they intentionally require POSIX `fcntl` locking and
  POSIX directory `fsync`; no Windows downgrade was introduced;
- Python compilation of changed service/MC modules passed;
- architecture source/import checks remain clean for the migrated path;
- the deleted `platform/composition/service_supervisor.py` has no current
  production or test import;
- no Minecraft server, Node dependency installation, model serving or
  scientific experiment was run.

The POSIX service tests must be rerun on the target Ubuntu host before service
qualification is claimed. This round therefore proves composition and static
ownership, not live-server readiness.
