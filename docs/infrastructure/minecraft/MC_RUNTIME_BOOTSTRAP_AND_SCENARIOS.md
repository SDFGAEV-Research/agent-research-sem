# Minecraft runtime bootstrap and source scenarios

## Purpose

The Minecraft environment separates four independently replaceable concerns:

1. immutable server artifact acquisition;
2. exact Java service lifecycle and readiness;
3. source-world scenario provisioning;
4. Mineflayer participant actions and evidence.

Paper-1 selects these interfaces at its composition root. The platform owns
their reusable contracts and providers; no Paper memory or evolution logic is
present in the MC infrastructure layer.

## Official server artifact route

`compose_official_minecraft_server_artifacts()` binds Mojang's official version
metadata to the generic streaming artifact acquirer. Acquisition enforces:

- official HTTPS metadata and content hosts;
- manifest-published SHA-1 and byte size;
- temporary-file download followed by atomic publication;
- verified reuse or fail-closed rejection of an existing mismatch;
- an artifact receipt containing SHA-256, SHA-1, size, source and producer
  operation identity.

The experiment runner does not download implicitly. `--acquire-server-jar`
must be present, otherwise a missing JAR is an actionable configuration error.
Minecraft EULA acceptance remains a distinct explicit flag.

## Typed source-world scenario

`MinecraftScenarioSpec` is an ordered immutable set of
`MinecraftScenarioStep` values. Each step declares a mutation command and a
required response assertion, optionally obtained through a separate
verification command. `RconMinecraftScenarioProvisioner` applies the steps
only after source-server TCP and RCON readiness.

For every step it records:

- the canonical step digest;
- mutation command evidence;
- mutation response SHA-256;
- verification command evidence;
- verification response SHA-256.

An absent response fragment, RCON error or incomplete receipt aborts source
startup. The host stops the source process when scenario provisioning fails,
so a partially prepared world cannot leak into a world cut. The scenario
digest is included in the environment and source-generation identities.

## Deterministic scripted smoke

The default `scripted-smoke` composition uses:

- `projects/sem_paper/experiments/manifests/scripted_smoke_scenario.json`;
- `projects/sem_paper/experiments/manifests/scripted_smoke.json`.

The scenario freezes time, weather, random mob spawning and spawn radius,
creates a bounded stone work area, places known oak logs and creates a
persistent no-AI husk target. The paired control and candidate branches are
materialized from the same verified source cut.

The task chain exercises real provider effects in dependency order:

| Task | Capability | Required evidence |
|---|---|---|
| Collect logs | `collect_block` | Broken blocks and positive inventory delta |
| Craft planks | `craft_item` | At least four grounded planks |
| Craft table | `craft_item` | One grounded crafting table |
| Place table | `place_block` | Verified world block at the declared position |
| Fight husk | `attack_nearest` | Mineflayer hurt/death signal |

Script rows are normalized through the authoritative MC action validator while
loading the task manifest. Invalid tools, unknown fields and unbounded values
fail before any live service starts.

## Operator flow

```bash
cd research_platform/environment/minecraft/providers/assets/mineflayer_bridge
npm ci
cd ../../../../../..

python scripts/run_sem_minecraft_experiment.py \
  --mode scripted-smoke \
  --acquire-server-jar \
  --accept-minecraft-eula \
  --generate-ephemeral-rcon-secret
```

The run publishes `server_artifact.json`, `run_manifest.json`,
`source_scenario_receipt.json`, service captures, world-cut manifests, action
evidence, workload checkpoints and `result.json`. A completed scripted smoke is
infrastructure evidence only; it is not a scientific SEM result and keeps the
scientific-claim gate false.
