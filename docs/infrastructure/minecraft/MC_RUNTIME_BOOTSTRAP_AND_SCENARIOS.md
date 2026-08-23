# Minecraft runtime bootstrap and source scenarios

## Purpose

The Minecraft environment separates five independently replaceable concerns:

1. immutable server artifact acquisition;
2. verified Java toolchain acquisition and materialization;
3. exact Java service lifecycle and readiness;
4. source-world scenario provisioning;
5. Mineflayer participant actions and evidence.

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

## Verified Java runtime route

`compose_eclipse_adoptium_java_runtime()` binds three platform-owned seams:

- the official Adoptium v3 latest-assets metadata adapter;
- the generic atomic artifact acquirer using the published SHA-256 and size;
- the bounded `SafeTarArchiveMaterializer`.

The tar provider rejects absolute or parent-traversing paths, duplicate
members, devices/FIFOs, multiple roots, unsafe links, missing required files,
member-count overflow and expanded-size overflow. It publishes a complete tree
only by a same-filesystem rename. The Java adapter then requires an executable
regular `bin/java`, verifies the exact requested major with `java -version`,
and durably records archive, tree, executable and version-output digests.

The experiment runner acquires nothing implicitly. `--acquire-java-runtime`
selects this route; otherwise the operator must provide a resolvable Java 21+
binary. A complete cached archive/tree/receipt triple is revalidated without a
metadata request. Partial cache state or any subsequent drift fails closed.
The verified receipt digest and executable digest are included in the source
generation and experiment-environment identities.

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
  --acquire-java-runtime \
  --acquire-server-jar \
  --accept-minecraft-eula \
  --generate-ephemeral-rcon-secret
```

The run publishes `java_runtime_artifact.json`, `server_artifact.json`,
`run_manifest.json`, `source_scenario_receipt.json`, service captures,
world-cut manifests, action evidence, workload checkpoints and `result.json`.
A completed scripted smoke is infrastructure evidence only; it is not a
scientific SEM result and keeps the scientific-claim gate false.
