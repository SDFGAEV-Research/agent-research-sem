# Round 108 — v034 `mc_runtime` reuse audit and process-signal seam

## Scope

This round audits `memory-evolving/v034_work/mc_runtime` against the current
recursive platform topology. It does not copy the old package, run Minecraft,
install a Node bridge, or run a scientific experiment.

## Reuse decisions

| Old responsibility | Decision | Current/future owner |
|---|---|---|
| `protocol.py` envelope | preserve invariant, rewrite types | `environment/minecraft/api` |
| `bridge.py` JSONL transport | preserve stream draining, timeout and proof behavior | `environment/minecraft/providers` |
| `agent_connection.py` | preserve handshake/command lifecycle, remove old dependencies | MC provider |
| `state.py` | preserve reduction rules, add bounded retention/digest | `environment/minecraft/runtime` |
| `preflight.py` | preserve version/TCP probes, return typed readiness evidence | MC readiness provider |
| `local_server.py` file logic | preserve property rendering, hashing and explicit EULA policy | MC API/provider |
| `local_server.py` process logic | do not copy; express launch contract | generic service runtime + MC readiness adapter |
| `server_download.py` | preserve official manifest and SHA-1 verification algorithm | artifact acquisition provider |
| `provenance.py` | preserve only MC-specific facts | artifact/release provenance authority |
| `bridge.js` / package pins | preserve grounded commands and pinned versions, add current protocol identity | MC bridge asset |
| `admission.py` | split; do not import old evidence owner | Paper evidence composition |
| `planner.py`, `semantic_executor.py`, `query.py` | do not move into MC | project method/model/memory systems |
| `task_runner.py` | rewrite as a Paper workload adapter | project/participant composition |
| `evidence_bundle.py`, `gate_state.py`, `t2b_integrity.py` | preserve validation concepts only | experiment/evidence governance |

The practical rule is: reuse behavior and invariants, never old ownership.

## Architecture correction

`JsonlMinecraftBridge` previously contained direct `os.killpg` calls. That made
the environment provider a second process-signal authority. The provider now
accepts an injected `ProcessTerminator(process, force)` seam and uses its own
portable process methods only as a fallback. A Linux service composition can
therefore provide group-aware termination without making MC import service
runtime implementation modules.

## Verification

- MC tests: **12 passed**.
- MC + SEM projection tests: **32 passed**.
- MC/architecture seam subset: **82 passed**.
- Python compilation: passed.
- `git diff --check`: passed.
- Production import scan: no imports of `mc_runtime`, `memory_runtime`,
  `memory_ir` or `v034_work`.

These are contract and architecture results only. Live server readiness,
Mineflayer dependency installation, model serving and paper experiments remain
unqualified.

## Next migration slice

The next high-value slice is not a copy of the old folder. It is an explicit
artifact-acquisition contract for the official server jar, followed by a
Paper-owned evidence adapter for MC observations. Only after those are wired
through the current generic service/participant/evidence interfaces can the
old `mc_runtime` owner be deleted.
