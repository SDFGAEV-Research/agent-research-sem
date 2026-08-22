# Round 117 — Reusable Minecraft experiment host

Date: 2026-08-21

## Objective

Move experiment concerns that recur across Minecraft papers behind platform
interfaces while keeping SEM method, task and planner semantics project-owned.
The immediate goal remains a reproducible Ubuntu control-path smoke, not a
scientific result.

## Implemented boundary

`research_platform/environment/minecraft/composition/experiment_host.py`
introduces the MC-owned host composition:

```text
source Minecraft service
  -> source lifecycle identity
  -> RCON save/quiescence barrier
  -> verified filesystem world cut
  -> endpoint-bound branch runtime factory
  -> deterministic branch service/session cleanup
```

The public host surface is `MinecraftExperimentHostPort`. It exposes only
world-cut, branch-runtime, source-start, source-process-identity and
source-stop operations. It does not expose a service locator or paper method.
The source process identity is retained from the start receipt and is used as
an exact fallback when a reconciliation observation temporarily has no process
identity.

The SEM entrypoint now supplies project-specific task/request templates and
consumes the generic host. It no longer creates the save barrier, world-cut
provider or branch runtime itself.

## Verification

- Focused MC/SEM/server/world-cut regression: **28 passed**.
- Python compilation of the new host, entrypoint and host test: **PASS**.
- Entrypoint `--help` and task-manifest loading: **PASS**.
- Local preflight: **expected FAIL** with
  `mineflayer:PACKAGE_NOT_RESOLVABLE` and
  `mineflayer_pathfinder:PACKAGE_NOT_RESOLVABLE`; Node and Java probes passed.
- No Minecraft server, model endpoint or remote host was started in this
  round.

## Remaining execution blockers

1. Install the bridge's locked Node dependencies on Ubuntu.
2. Provide the exact server artifact and environment profile on Ubuntu.
3. Run the preflight and one control-path smoke on the server.
4. Implement and bind the SEM candidate materializer before any paired
   scientific claim.

The existing generic `experimentation/run` and `experimentation/experiment`
systems remain the authorities for run identity, lifecycle, manifests,
checkpoints and scientific workflow. This round adds only the missing MC
specialization; it does not create a second generic run manager.
