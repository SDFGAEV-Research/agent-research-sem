# Current Development Baseline

**Baseline date:** 2026-08-28
**Platform version:** 0.43.0
**Repository role:** reusable upstream platform

This document is the current development truth for the generic Agent Research Platform repository. Concrete research methods, benchmark tasks, environment implementations, model selections, machine inventories, experiment matrices, and scientific results are downstream-owned.

## Repository boundary

The reusable package boundary is `research_platform/`. Packaging publishes only `research_platform*`; the upstream must import, test, build, release, and run its generic doctor without any `projects/` tree or project-owned environment/provider package.

The enforceable split contract is [`../architecture/DOWNSTREAM_PROJECT_REPOSITORY_CONTRACT.md`](../architecture/DOWNSTREAM_PROJECT_REPOSITORY_CONTRACT.md) and `scripts/platform_repository_boundary.py`.

## Platform ownership

The upstream owns generic contracts and runtime systems for experiment identity, participants, agents, methods, environments, models, prompts, services, processes, servers, artifacts, storage, recovery, observability, governance, testing, and release control.

Concrete downstream behavior binds through public contracts and may add scientific methods, benchmark adapters, environment providers, model profiles, deployment inventory, application CLIs, and result/evidence interpretation without becoming an upstream dependency.

## Current source validation

The frozen source-validation pass on 2026-08-28 completed with **1000 passed, 6 skipped, 0 failed, 0 errors, and 4 subtests passed**.
Algorithm governance accepted **5261 symbols / 305 candidates**. Concurrency governance accepted **267 hotspots / 1 finding / 0 blocker debt**. Performance governance accepted **67 hotspots / 79 findings / 0 blocker debt**. Architecture and test-system source gates pass.

The three source inventories explicitly exclude `.server-state`, so local controller state, audit clones, transfer staging, and forensic scratch files cannot contaminate platform governance evidence.

SQLite WAL lock contention is handled by the generic deadline-retry primitive in `platform.kernel`; `scope` declares this dependency explicitly rather than relying on a hidden cross-system exemption.

Structured deadline propagation is stress-qualified: the child-first inherited-group deadline race passed 50/50 independent repetitions, and the complete concurrency runtime module passed 37/37.

## Packaging and deployment

The generic Docker image installs the platform package and operator tooling only. Project-specific runtimes are layered by downstream images or Compose overlays.

The 0.43.0 generic image was built from the verified release tree and passed its container doctor on an online Linux Docker host. The image reports Python 3.12.14 and `research-platform==0.43.0`, has a writable platform state directory, contains no `/opt/research-platform/projects` tree, and does not carry Java or Node as implicit project runtimes.

Version 0.43.0 establishes the repository-extraction boundary. A release is authoritative only when the release subsystem regenerates `RELEASE_MANIFEST.json`, `RELEASE_EVIDENCE.json`, and `RELEASE_AUTHORITY.json` from the exact source tree and the final repository-boundary/package verification gates pass.

## Release qualification contract

A qualifying release must prove all of the following without weakening a gate: no downstream-owned source in the upstream manifest; complete test taxonomy; full regression; architecture/algorithm/concurrency/performance gates; wheel/sdist membership; generic container doctor; and self-verifying release authority/evidence.

Historical release files remain evidence for their historical tree only. They are never reused as current development truth after the source tree changes.

## Downstream continuity

Repository extraction does not discard project history. Downstream repositories retain their own source, configuration, tests, documentation, deployment inventory, evidence, and Git history and consume the platform through the documented one-way dependency boundary.
