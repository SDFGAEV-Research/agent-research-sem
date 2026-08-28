# Self-Evolving Memory Research System

[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Upstream](https://img.shields.io/badge/Agent%20Research%20Platform-v0.43.1-blue)](https://github.com/SDFGAEV/agent-research-platform-system)
[![Project](https://img.shields.io/badge/research-SEM-6f42c1)](docs/projects/sem_paper/README.md)

This repository is the downstream research repository for **Self-Evolving Memory (SEM)**. It preserves the complete Git ancestry of the reusable [Agent Research Platform](https://github.com/SDFGAEV/agent-research-platform-system) and layers SEM-specific methods, experiment composition, model/deployment choices, task manifests, scientific tests, and evidence on top.

The platform release base is **v0.43.1** at `f9c1740dddd2cde6f0e13c0042637b8bb0eb4938`; the current upstream tracking head is `8941ce502e485d3c108be83c708461426ca6c7bb`, which adds the post-tag concurrency test-stability fix. Platform source remains upstream-owned: the downstream tree does not fork or override files under `research_platform/`.

## Repository relationship

```text
SDFGAEV/agent-research-platform-system
  upstream/master ? 8941ce5
  release v0.43.1 ? f9c1740
          ?
          ?
SDFGAEV-Research/agent-research-sem
  main
          ?
   ???????????????????????
   ?      ?              ?
 SEM   experiments   model/deployment/
 method  + tasks       evidence policy
```

The dependency direction is one-way: `projects.sem_paper` may consume public `research_platform` contracts; `research_platform` must never import SEM project code.

## Ownership boundary

| Surface | Owner |
| --- | --- |
| `research_platform/` | Upstream Agent Research Platform |
| `research_platform/environment/minecraft/` | Upstream reusable Minecraft provider |
| `projects/sem_paper/` | SEM scientific method and experiment composition |
| `configs/models/*` project profiles | SEM model/deployment selection |
| `configs/server_profiles/*` project profiles | SEM deployment inventory templates |
| `scripts/sem_paper_*`, `scripts/run_sem_*`, `scripts/t2*` | SEM execution and evidence tooling |
| `docs/projects/sem_paper/` | SEM scientific/runbook authority |
| `docs/infrastructure/server/SERVER_FLEET_PATH_INVENTORY.md` | SEM operational fleet path authority |
| `tests/test_sem_*` and SEM-specific application tests | Downstream scientific/integration verification |

Reusable fixes belong upstream first. SEM-specific scientific semantics stay downstream. This avoids carrying private platform patches that would make upstream synchronization ambiguous.

## Project entry points

- `projects/sem_paper/method/self_evolving_memory/` — SEM method implementation and evolution system.
- `projects/sem_paper/composition/` — study, model, Minecraft, non-Minecraft, evidence, and scientific-closure composition.
- `projects/sem_paper/experiments/manifests/` — frozen task/study manifests.
- `docs/projects/sem_paper/` — implementation audits, runbooks, milestones, and scientific evidence contracts.
- `docs/status/CURRENT_EXECUTION_STATUS_20260828.md` — current operational/scientific truth.
- `configs/models/qwen38_27b_vllm.yaml` — current primary-model serving profile.

## Current scientific state

Qwen3.8-27B is the current primary model track. Model-serving health and earlier Minecraft live-smoke evidence exist, but **full Core-6 has not started as a claim-eligible scientific run**. Operational success, deployment qualification, smoke evidence, and scientific evidence remain separate states.

## Development setup

```bash
git clone git@github.com:SDFGAEV-Research/agent-research-sem.git
cd agent-research-sem

python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest -q
```

The downstream wheel installs both `research_platform*` and `projects*`. SEM experiment manifests are shipped as project package data, so an installed checkout retains the frozen scientific inputs required by the project composition.

## Upstream synchronization

The canonical remote layout is:

```text
origin    -> SEM repository
upstream  -> git@github.com:SDFGAEV/agent-research-platform-system.git
```

Synchronize platform changes explicitly:

```bash
git fetch upstream --tags
git merge upstream/master
python -m pytest -q
```

After every upstream merge, verify that `git diff upstream/master..HEAD -- research_platform` is empty unless a reusable platform fix is intentionally being prepared for upstream first.

## Evidence and release authority

Root `RELEASE_*` files inherited from an upstream merge describe the exact upstream platform tree that produced them; they are **not** SEM scientific-release authority once downstream files are present. SEM claim eligibility is governed by the project manifests, deployment identities, run evidence, and scientific-closure checks under the downstream project surfaces.

Server credentials, private keys, tokens, and controller-local bindings are never committed. Non-secret server identities and operational paths may be documented downstream because they are part of this project's reproducibility/deployment record; they must not leak back into the generic upstream repository.

## Preservation history

The repository split was performed without discarding the pre-split history. Recovery bundles/tags preserve the earlier mixed worktree and the first downstream baselines. Those archives are historical recovery evidence, not active development repositories. Historical changes are intentionally kept out of this README; use the history/status documents and Git tags for reconstruction. The current development truth for SEM is maintained in the downstream baseline and current execution-status documents linked below. The inherited platform development baseline remains at `docs/status/CURRENT_DEVELOPMENT_BASELINE.md`.

## Key documentation

- [SEM project documentation](docs/projects/sem_paper/README.md)
- [Downstream baseline](docs/projects/sem_paper/DOWNSTREAM_BASELINE_20260828.md)
- [Current execution status](docs/status/CURRENT_EXECUTION_STATUS_20260828.md)
- [Server fleet path inventory](docs/infrastructure/server/SERVER_FLEET_PATH_INVENTORY.md)
- [Upstream repository contract](docs/architecture/DOWNSTREAM_PROJECT_REPOSITORY_CONTRACT.md)

The guiding rule is simple: **general infrastructure evolves upstream; scientific meaning evolves here.**