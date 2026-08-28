# Server Fleet Path Inventory — 2026-08-28

This document is the operational path authority for the managed GPU fleet. It records where code, immutable source snapshots, Docker assets, models, mutable runtime state, SEM evidence and logs physically live on each server.

It contains **no passwords, private keys, tokens or API secrets**. Connection secrets remain outside Git. The committed profile only carries non-secret server identity; the ignored local profile carries controller-local bindings.

## Fleet summary

| Server ID | SSH identity | Primary role | Stable project root | Docker root |
| --- | --- | --- | --- | --- |
| `node-118-190-202-247` | `gpuadmin@118.190.202.247:30056` | Minecraft/SEM execution; Qwen3.8 qualification | `/data1/research-platform` | `/var/lib/docker` |
| `node-121-48-164-241` | `ubuntu@121.48.164.241:32155` | image builder; model-serving expansion | `/data/hdd1/research-platform` | `/data/hdd3/docker` |
| `sem-ubuntu` | `ubuntu@103.40.13.126:60320` | legacy SEM node | legacy `/data/research-platform` | must be re-qualified |

`sem-ubuntu` is currently unreachable from the controller. Its paths below are historical attestation, not current reachability proof.

## Server 1 — `node-118-190-202-247`

Host fact: `gpusystem`, operator `gpuadmin`, home `/home/gpuadmin`. `/data1` is an XFS HDD filesystem, 5.5 TiB total with about 4.8 TiB free at the latest probe.

The stable project root is `/data1/research-platform`. Project-owned mutable and archival data must remain under this HDD root. The host Docker daemon itself still stores layers under `/var/lib/docker`; do not migrate that global daemon without a separate host-impact review.
### Server 1 code and source snapshots

- Stable source area: `/data1/research-platform/source`.
- General extracted source root: `/data1/research-platform/source/agent-research-platform-system`.
- Exact smoke snapshots currently retained include:
  - `/data1/research-platform/source/agent-research-platform-system-e2336b8c83db`
  - `/data1/research-platform/source/agent-research-platform-system-5f6e92d24b16`
  - `/data1/research-platform/source/agent-research-platform-system-6e6319ba57e0`
  - `/data1/research-platform/source/agent-research-platform-system-71fe1fab3b4e`
  - `/data1/research-platform/source/agent-research-platform-system-ac70f3c463b3`
  - `/data1/research-platform/source/agent-research-platform-system-b3632bcb5013`
- Matching Git-archive inputs are stored beside those directories as `research-platform-<commit>.tar.gz`.
- These extracted snapshots are **not Git checkouts**: they intentionally have no `.git` directory. The commit suffix is their source identity.
- Current latest live Minecraft smoke source is `b3632bcb5013`; later Windows worktree changes are not yet deployed scientific source.

### Server 1 Docker assets

- Docker/image archive directory: `/data1/research-platform/images`.
- Canonical platform archive: `/data1/research-platform/images/research-platform-11dcefb919d6.tar.gz`.
- Platform archive SHA-256: `471d7649f16ecab02e4aef5f9ef292f0e34a9ce57d8905862c3bc36fe94b6f42`.
- vLLM archive: `/data1/research-platform/images/vllm-openai-v0.27.1.tar.gz`.
- vLLM archive SHA-256: `8ebfc50f862caf061da84ac503d76ab6f543e56d19cac35e8b64015c65dfd319`.
- Loaded reusable application image: `research-platform:11dcefb919d6`.
- Loaded model-serving image: `vllm/vllm-openai:v0.27.1`.
### Server 1 models and SEM runtime

- Qwen3.8 model root: `/data1/research-platform/models/qwen38-27b`.
- Frozen model revision: `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- Latest asset verification: about 52 GiB, 18 safetensors shards, zero `.incomplete` files.
- Hugging Face cache: `/data1/research-platform/cache/huggingface`.
- Acquisition receipt: `/data1/research-platform/state/model-acquisition/qwen38-27b.json`.
- Model-serving state: `/data1/research-platform/state/model-serving`.
- Current qualification container: `sem-qwen38-qualification-tp2`.
- Container model mount: host `/data1/research-platform/models/qwen38-27b` → container `/model:ro`.
- Qualification container currently binds GPU `0,1`, TP=2, BF16, max model length 262144, and container-local endpoint `127.0.0.1:30080`.

- Mutable runtime root: `/data1/research-platform/runtime`.
- Minecraft runtime/artifact root: `/data1/research-platform/runtime/minecraft`.
- Platform mutable state: `/data1/research-platform/runtime/platform-state`.
- SEM run evidence root: `/data1/research-platform/runtime/platform-state/sem-runs`.
- Live/smoke run directories are named by exact run ID, for example `sem-scripted-smoke-b3632bcb5013-itemdrop1`.
- Operator-facing run staging: `/data1/research-platform/runs`.
- Logs: `/data1/research-platform/logs`.
- Durable acquisition/transfer/serving state: `/data1/research-platform/state`.

Do not interpret an old smoke directory or exited smoke container as current scientific evidence. Full Core-6 evidence will receive a new frozen run identity and must not reuse a debug run directory.
## Server 2 — `node-121-48-164-241`

Host fact: `ubuntu-desktop-2204`, operator `ubuntu`, home `/home/ubuntu`. The server has three 15 TiB HDD filesystems: `/data/hdd1`, `/data/hdd2`, `/data/hdd3`. The project control root is on `/data/hdd1`; the Docker daemon itself is also HDD-backed under `/data/hdd3/docker`.

### Server 2 code and build assets

- Stable project root: `/data/hdd1/research-platform`.
- Stable source area: `/data/hdd1/research-platform/source`.
- General extracted source root: `/data/hdd1/research-platform/source/agent-research-platform-system`.
- Retained immutable source snapshots include:
  - `/data/hdd1/research-platform/source/agent-research-platform-system-858906ff9c67`
  - `/data/hdd1/research-platform/source/agent-research-platform-system-11dcefb919d6`
- Matching source archives: `/data/hdd1/research-platform/source/research-platform-<commit>.tar.gz`.
- The snapshot directories are extracted Git archives rather than mutable Git checkouts; the commit suffix is the authoritative source identity.
- Builder image/archive root: `/data/hdd1/research-platform/images`.
- Canonical platform archive SHA-256 matches Server 1: `471d7649f16ecab02e4aef5f9ef292f0e34a9ce57d8905862c3bc36fe94b6f42`.
- vLLM `0.27.1` archive SHA-256 also matches Server 1: `8ebfc50f862caf061da84ac503d76ab6f543e56d19cac35e8b64015c65dfd319`.

Server 2 remains the preferred image-builder node because its Docker root is already HDD-backed. Other nodes should consume verified archives rather than rebuilding the same environment independently.
### Server 2 models and runtime

- Qwen3.6 Hugging Face cache root: `/data/hdd1/huggingface/models--Qwen--Qwen3.6-35B-A3B`.
- Frozen Qwen3.6 revision: `995ad96eacd98c81ed38be0c5b274b04031597b0`.
- Exact Qwen3.6 snapshot: `/data/hdd1/huggingface/models--Qwen--Qwen3.6-35B-A3B/snapshots/995ad96eacd98c81ed38be0c5b274b04031597b0`.
- Latest Qwen3.6 asset verification: about 67 GiB with all expected weight shards present.
- `/data/hdd1/research-platform/models/qwen38-27b` currently exists only as an empty placeholder; Qwen3.8 weights have **not** yet been copied to Server 2.
- Project runtime root: `/data/hdd1/research-platform/runtime`.
- Minecraft runtime root: `/data/hdd1/research-platform/runtime/minecraft`.
- Platform mutable state: `/data/hdd1/research-platform/runtime/platform-state`.
- Project log root: `/data/hdd1/research-platform/logs`.
- Project model root reserved for normalized served-model assets: `/data/hdd1/research-platform/models`.

The intended future Qwen3.8 expansion placement is role-aware multi-GPU serving on Server 2. This is a target topology, not a current scientific deployment: weights must first be transferred and the resulting endpoints must pass platform qualification.

## Server 3 — `sem-ubuntu`

Current SSH endpoint: `ubuntu@103.40.13.126:60320`. It is currently unreachable from the controller, so no current mutation or path claim is allowed.

Historical attestation records the platform root as `/data/research-platform`, managed Python as `/data/research-platform/envs/sem-paper/bin/python`, managed Node as `/data/research-platform/toolchains/node-v22.22.2-linux-x64/bin/node`, and Java 21 at `/data/ubuntu/cef-hicc-multiserver-D/runtime/jre-21.0.8/bin/java`.

The exact active repository checkout/code path on `sem-ubuntu` is **not currently re-verified**. Do not assume that `/data/research-platform` itself is the active checkout. Restore connectivity, run server qualification/doctor, and attest `REPOSITORY_ROOT` before any deployment or experiment mutation.
## Path and identity rules

1. HDD project roots are stable operational authorities; per-commit source snapshot directories are immutable execution inputs.
2. A source snapshot suffix such as `b3632bcb5013` is a Git commit identity, not an indication that the extracted directory contains `.git` metadata.
3. Scientific runs must freeze source commit, Docker archive/image identity, model revision, prompt/role bindings and evidence root before claim-eligible execution starts.
4. Docker image/archive equality is proven by SHA-256 of the portable archive; do not infer equality from local legacy-builder image IDs alone.
5. Model folders are not interchangeable merely because their names match. Record repository ID, frozen revision, shard completeness and qualification evidence.
6. Debug/smoke evidence under `sem-runs` remains historical evidence and must never be overwritten by a later run.
7. Global host Docker roots are host infrastructure. Project data placement may be HDD-first without migrating an existing global daemon.
8. `sem-ubuntu` remains fail-closed until reachability and repository/runtime paths are re-attested.

## Controller-side references

- Committed non-secret enrollment template: `configs/server_profiles/three-servers.example.env`.
- Ignored operational profile: `configs/server_profiles/three-servers.local.env`.
- Server control-plane contract: [`SERVER_CONNECTIONS.md`](SERVER_CONNECTIONS.md).
- Current operational/scientific state: [`../../status/CURRENT_EXECUTION_STATUS_20260828.md`](../../status/CURRENT_EXECUTION_STATUS_20260828.md).

Whenever a server path, role, model placement, image identity, Docker root, runtime evidence root or source-snapshot convention changes, update this inventory in the **same change set** as the implementation/deployment change.
