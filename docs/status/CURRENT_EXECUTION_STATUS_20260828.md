# Current Execution Status — 2026-08-28

This is the current operational status projection for the development tree and the managed GPU fleet. It reports verified facts; it does not replace source contracts, release manifests, or scientific evidence receipts.

## Status authority and claim boundary

- Current committed source baseline: `b3632bc` (`fix(minecraft): capture block drops from upstream events`).
- The working tree also contains unrelated in-progress `server_doctor` changes; they are not part of the Minecraft commits summarized here.
- Full Core-6 Minecraft SEM has **not** started as a claim-eligible scientific run.
- Current live Minecraft work is still `scripted-smoke` and remains `scientific_claim=false`.
- A historical operational success, a currently running service, a qualified deployment, and a claim-eligible scientific run are four different states and must not be conflated.

## Three-server fleet

| Server ID | Current role | Verified storage / accelerator facts | Current state |
| --- | --- | --- | --- |
| `node-118-190-202-247` | Minecraft/SEM execution + Qwen3.8 qualification | `/data1` HDD 5.5T, ~4.8T free; 4× RTX 5000 Ada 32 GB | online; Docker usable |
| `node-121-48-164-241` | image builder + model-serving expansion | `/data/hdd1` HDD 15T, ~11T free; 8× RTX 4090 ~49 GB | online; Docker usable |
| `sem-ubuntu` | legacy SEM server/profile | historical 3090-class SEM host | SSH endpoint currently unreachable from controller |

Credentials remain outside Git. The committed three-server catalog contains only non-secret connection identity; runtime/toolchain paths must be attested before `composition_ready` can be claimed.

## HDD-first Docker runtime

The reusable application environment is the Linux Docker image. Project checkout, model/image archives, Minecraft worlds, run evidence and mutable platform state are stored on HDD roots rather than recreated per server.

- Server 1 root: `/data1/research-platform`.
- Server 2 root: `/data/hdd1/research-platform`.
- The validated deployment pattern is build once on the builder, archive + SHA-256, then `docker load` on execution nodes without rebuilding.
- Current live debugging uses a validated dependency image plus an exact read-only source archive overlay; a new immutable final image will be built only after the live smoke path is green.
## Model state

### Qwen3.8-27B — primary SEM model track

- Official asset: `Qwen/Qwen3.8-27B`.
- Frozen revision: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- Server 1 acquisition state: `complete`, about 52 GB, zero `.incomplete` files.
- vLLM `0.27.1` has previously loaded the model successfully with TP=2, BF16 and the full 262,144-token context on two RTX 5000 Ada GPUs.
- The verified TP admissibility constraint is structural: TP=3 is invalid because model head dimensions are not jointly divisible by 3. Candidate TP sizes are 1/2/4/8 subject to capacity qualification.
- At the latest status probe the qualification container was still running and its TP workers occupied GPUs 0/1, but host endpoint `127.0.0.1:8018` was not listening. This is runtime drift requiring readiness reconciliation; it is **not** a current qualified-ready claim.
- Qwen3.8 is the intended primary SEM model. It is not yet a published qualified scientific deployment closure.

The intended role bundle is `planner / semantic / meta / diagnostic`. Each role must retain its own frozen prompt generation, request trace and authority boundary even when roles share one model revision. The current production Minecraft composition is not yet fully wired to all four roles.

### Qwen3.6-35B-A3B — retained independent candidate

Server 2 contains the complete Qwen3.6 asset at about 67 GB with zero incomplete shards. It remains a separately qualified candidate/reference path and is not an automatic fallback for Qwen3.8 scientific runs.

The vLLM `0.27.1` image archive transfer to server 2 was only about 5.8 GB at the latest probe and must not be treated as a complete transferable image until its expected archive size and SHA-256 are verified.

## Current Minecraft live execution

The official Minecraft 1.21.8 server artifact, Java 21 runtime, RCON scenario creation, world save/cut, branch runtime, Mineflayer bridge, evidence ingestion, cognition loop and checkpoint publication have all been exercised in real live runs.

The latest run is `sem-scripted-smoke-b3632bcb5013-itemdrop1` and failed closed. Its gather action broke two `oak_log` blocks but verified only one collected item: `COLLECTION_INCOMPLETE`, `collected_count=1`, with `ITEM_DROP_NOT_OBSERVED`. The final result also exposed a separate cleanup task-identity collision in graceful bridge shutdown. Neither failure is being relabeled as success.
## Live fixes already verified

The current live-hardening sequence includes:

- `6e6319b`: preserve environment evidence payload through `AgentObservation`.
- `e2336b8`: bound Mineflayer action execution and cancellation.
- `5f6e92d`: restore the canonical world-cut encoder import.
- `71fe1fa`: require real dropped-item pickup evidence.
- `f4b1d51`: unify checkpoint task-manifest identity with the SEM workload authority.
- `ac70f3c`: align Mineflayer entity handling with upstream `GoalFollow`, `playerCollect`, `displayName` and dropped-item contracts.
- `b3632bc`: capture block drops from `itemDrop` registered before `dig`.

The checkpoint/resume digest mismatch is no longer reproduced: live Fixed-C/Fixed-X branches have published workload checkpoints under the unified manifest identity.

## Minecraft upstream-source policy

Minecraft behavior must be changed only after inspecting the exact upstream source used by the lockfile. The current audited versions include:

- Mineflayer 4.37.1, tag source commit `03eba44…`;
- mineflayer-pathfinder 2.4.5, tag source commit `ca35a00…`;
- prismarine-entity 2.6.0, tag source commit `4f2678f…`;
- mineflayer-collectblock 1.6.0/1.7.0 behavior for `itemDrop` capture and `GoalFollow` pickup;
- mineflayer-pvp 1.3.2 tag commit `0b4006de…`.

The pinned mineflayer-pvp 1.3.2 source still subscribes to deprecated `physicTick`; current upstream main uses `physicsTick` but has not published a new package version. Do not silently vendor or upgrade it without an explicit compatibility decision.

The current collectblock upstream still correlates a drop to a block using a 0.5-block-center radius. The live 1.21.8 run showed that this rule did not reliably observe the expected drop. No larger radius will be invented without upstream/protocol evidence.
## Current verification evidence

Recent focused verification includes:

- Minecraft/SEM Python regression: `91 passed` for the upstream-contract + checkpoint slice.
- Upstream-grounded Node bridge regression: `13/13 passed`, then `14/14 passed` after pre-dig `itemDrop` capture.
- Additional item-drop Python regression: `36 passed`.
- Earlier evidence-ABI regression: `15/15 passed`.
- Earlier bounded-action regression: `41 Python passed + 10 Node passed`.

These focused suites validate the changed seams. They are not a substitute for the final full repository regression required before the scientific run freeze.

## Governance scans — current worktree

Current reports are maintained inside the documentation system:

- `docs/status/algorithm/ALGORITHM_REPORT.md`: 7,483 symbols, 631 optimization candidates.
- `docs/status/concurrency/CONCURRENCY_REPORT.md`: 410 hotspots, 1 finding, zero P0/P1 debt.
- `docs/status/performance/PERFORMANCE_REPORT.md`: 104 hotspots, 125 findings, zero P0/P1 blockers.

Root `ALGORITHM_SCAN.md`, `CONCURRENCY_SCAN.md` and `PERF_SCAN.md` remain only because frozen release manifests reference those paths. They are compatibility/release projections, not the current documentation authority.

## Remaining gates before full Core-6

1. Close the current live Minecraft pickup and graceful-close task-identity blockers with upstream-grounded fixes.
2. Run scripted smoke through gather, craft, place and combat with no ungrounded completion claims or cleanup failures.
3. Reconcile Qwen3.8 serving readiness and publish the platform-qualified deployment/runtime closure.
4. Wire the four Qwen3.8 role bindings while preserving prompt/evidence authority separation.
5. Materialize a real SelfEvolve proposal authority and scientifically-ready evolution bindings.
6. Run the final repository, architecture, degradation, model-role, Minecraft and evidence gates.
7. Build one immutable Docker image from the frozen commit and launch Core-6: 6 arms × 12 repetitions.

Until all seven gates close, full SEM is **not running as a scientific experiment**.

## Optimization lane

Optimization may proceed beside validation, but a frozen scientific run must never be hot-patched. High-priority work includes GPU topology/TP legality, replica and role placement, KV-cache/batching telemetry, experiment-level GPU/CPU/IO scheduling, TaskGroup identity/cancellation, Minecraft lifecycle reuse, HDD/SQLite WAL behavior, and Docker build ownership/copy costs.
