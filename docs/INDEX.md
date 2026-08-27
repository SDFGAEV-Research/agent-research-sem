# Documentation Index

This directory is the single documentation root for the platform. Documents
are grouped by ownership and lifecycle; a document must live in the subtree of
the system that owns its contract.

## Authority order

1. `research_platform/governance/system_registry/catalog.json` is the unique
   system-topology authority.
2. `docs/architecture/VNEXT_SYSTEM_CATALOG.json` is the checked documentation
   mirror of that topology.
3. Current architecture and governance documents describe the contracts and
   invariants enforced by the source tree.
4. Project documents describe Paper-1 composition and scientific execution.
5. `history/` and `status/` are evidence and snapshots; they do not override a
   current contract.

Conflicting historical notes are not a second authority. Update the current
owner document and add a new dated history note when a decision changes.

## Hierarchy

### Platform and architecture

- [`architecture/`](architecture/README.md) — final recursive architecture,
  topology, composition graph, data flow, migration contract and boundary
  design.
- [`governance/`](governance/README.md) — architectural gates, forensic
  evidence, debugging policy and no-degradation invariants.

### Reusable infrastructure

- [`infrastructure/`](infrastructure/README.md) — reusable platform systems,
  split into AI/model assets, runtime control, server management,
  observability and Minecraft environment infrastructure.

### Research and project ownership

- [`research/memory/`](research/memory/README.md) — the self-evolving-memory
  method specification and research-level memory decomposition.
- [`projects/sem_paper/`](projects/sem_paper/README.md) — current Paper-1
  implementation, Minecraft production composition and scientific audit
  documents.

### Evidence and status

- [`history/`](history/README.md) — immutable round-by-round development
  record, grouped by platform, memory and Paper-1 ownership.
- [`status/`](status/README.md) — current development baseline and version
  history. These files report state; they do not define runtime ownership.

## Current execution status

The live operational projection for the active SEM/server/model work is
[`status/CURRENT_EXECUTION_STATUS_20260828.md`](status/CURRENT_EXECUTION_STATUS_20260828.md).
It reports runtime facts and open gates; it does not override source contracts or frozen release evidence.

Documentation changes are governed by
[`governance/DOCUMENTATION_CHANGE_POLICY.md`](governance/DOCUMENTATION_CHANGE_POLICY.md).
Implementation, tests and owning documentation are expected to move together.

## Documentation rules

- Keep one canonical document per contract. Do not copy a contract into a
  project or a historical round.
- Put reusable capability documentation under `infrastructure/`, not under a
  paper project.
- Put scientific method and experiment decisions under `research/` or the
  owning project, not in platform architecture documents.
- New round notes go under the matching `history/rounds/<owner>/` directory and
  must link back to the current owner document.
- Root `README.md` is the repository entry point; root `CONTEXT.md` is the
  vocabulary entry point. They are navigation documents, not alternative
  architecture registries.
