# Round 109 — artifact acquisition, Paper evidence admission and MC workload

## Scope

This round completes the next three responsibilities identified in the v034
`mc_runtime` audit. The old package remains untouched and is not imported.
No Minecraft server, Node bridge, model or scientific experiment was run.

## Artifact acquisition

`research_platform.artifact.content.api` now defines a generic,
digest-required acquisition contract. `artifact/content/providers/download.py`
implements streaming HTTP acquisition, SHA-1/SHA-256/size verification,
atomic publication, verified existing-file reuse and explicit replacement
policy. The provider returns a normal `ArtifactRecord`-compatible result; the
artifact catalog remains the registration authority.

`environment/minecraft/providers/server_artifact.py` is only the Minecraft
manifest adapter. It resolves the official Mojang version manifest, accepts
only official HTTPS hosts, validates the server SHA-1, and delegates bytes and
atomic publication to artifact/content. This is the direct structural
replacement for v034 `server_download.py`.

The environment/minecraft topology declaration now explicitly requires the
artifact system. The dependency is recorded in the canonical topology rather
than hidden in an import.

## Paper evidence admission

`projects/sem_paper/composition/minecraft_evidence.py` rewrites v034
`admission.py` against the current interfaces:

- self snapshots and entity observations become normalized `J_mem` payloads;
- verified action results become `J_mem` payloads;
- unverified action results, health/death/bridge/error events become injected
  `J_audit` rows;
- IDs are deterministic from the bridge event identity and payload;
- malformed observations fail with stable admission codes;
- the adapter owns no SEM storage, retrieval, or architecture state.

## Paper workload adapter

`projects/sem_paper/composition/minecraft_workload.py` replaces the old
task-runner coupling with injected ports for environment observation/action,
method recall/completion, evidence admission, planner decisions and
diagnostics. It preserves the v034 task fields, scripted planner behavior,
success predicates, action/decision-cycle records and terminal task completion.
LLM planning remains a replaceable implementation of `MinecraftPlannerPort`;
the workload does not import an LLM client or Mineflayer connection.

## Verification

- artifact + MC + SEM focused tests: passed;
- evidence/workload/artifact plus MC/SEM regression set: **97 passed**;
- the architecture subset within that run: **65 passed**;
- project API firewall, source invariants, seam graphs and architecture planes:
  passed;
- Python compilation and `git diff --check`: passed;
- production legacy import scan: no `mc_runtime`, `memory_runtime`,
  `memory_ir` or `v034_work` imports.

These results prove contract and composition behavior only. The Linux service
provider, Node dependency installation, real server readiness, baseline
reproduction and scientific run remain pending.

## Remaining v034 responsibilities

Evidence bundle/gate logic still belongs to experiment governance, and the
old source/runtime provenance must bind to the platform release/artifact
authorities. They will be migrated only after their current owners are audited;
they will not be copied into MC or Paper workload code.
