# Round 107 — MC session state and action-contract closure

## Scope

This round continues the migration of `memory-evolving/v034_work/mc_runtime`
into the current recursive platform architecture. It does not import the old
package and does not run Minecraft or a scientific experiment.

## Changes

- Added `research_platform.environment.minecraft.api.actions`.
  `validate_minecraft_action()` is the current MC action input seam. It
  preserves the useful v034 bounds while removing planner, LLM and task-runner
  dependencies.
- Added `max_entities` to `MinecraftEnvironmentSpec`, making the state-read
  model bound part of the immutable environment identity.
- Bound one `MinecraftStateProjection` to every
  `MinecraftEnvironmentSession`. `observe()` and `act()` ingest all returned
  events before constructing the observation.
- Added compact state and `state_digest` to MC observations. Event payloads now
  retain sequence, timestamp, source and request identity.
- Invalid action contracts produce current `MinecraftEnvironmentFailure` with
  a stable contract code and never cross into the bridge provider.
- Added `compose_minecraft_participant_endpoint()`, reusing the generic
  `LocalParticipantRuntimeEndpoint` rather than introducing another MC
  lifecycle endpoint.
- Generated `providers/assets/mineflayer_bridge/package-lock.json` with Node
  22/npm lockfile v3, pinned versions and official npm integrity URLs. No
  `node_modules` was installed.

## Root-cause correction

The previous MC slice proved that the bridge could transport events and that a
state projection existed, but it did not prove that the environment session
actually owned and returned the projection. Consequently a project adapter
would have needed to depend on provider-specific event folding. The session is
now the single owner of this environment read model; projects consume the
generic `Observation` payload and remain independent of Mineflayer.

## Verification

- MC environment tests: **12 passed**.
- MC + SEM architecture/projection tests: **32 passed**.
- Python compilation of MC package and MC tests: passed.
- `git diff --check`: passed.
- Production import scan: no imports of `mc_runtime`, `memory_runtime`,
  `memory_ir` or `v034_work`.

The workspace default interpreter is Python 3.10 while the project declares
Python >=3.11. The focused verification for this round was rerun with the
repository's Python 3.12 environment; the broader Windows suite still has
known POSIX-only `fcntl`/directory-fsync and SQLite cleanup assumptions. This
is an environment limitation, not a code downgrade; Linux qualification
remains pending.

## Remaining MC qualification gates

1. Install from and verify the provider lockfile / integrity manifest for the
   pinned Node, Mineflayer and pathfinder versions.
2. Bind a concrete Linux service/process provider to the already-composed
   `MinecraftServerServiceController`.
3. Run server-side readiness and bridge smoke on the target host, preserving
   complete stdout/stderr and failure evidence.
4. Wire the MC observation stream into the Paper-1 workload/evidence adapter;
   do not move task or memory ownership into the MC package.
5. Only after the current call chain is live and deletion evidence exists may
   the old `v034_work/mc_runtime` owner be physically removed.

The official npm audit currently reports six moderate transitive findings in
Mineflayer's auth/protocol chain. The offered automatic fix is an incompatible
semver-major Mineflayer `1.4.0` proposal, so no forced fix or dependency
weakening was applied. The finding is recorded as a deployment qualification
risk and must be resolved by a compatible upstream/provider change.
