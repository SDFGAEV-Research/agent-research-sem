# Current Development Version Notes — 2026-08-19

## 2026-08-21 Deluxe D3 diagnostic plane

- Rebuilt the current-project neutral diagnostic plane in
  `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py`.
- Added typed query/task observations, explicit incident facts, immutable
  diagnostic snapshots, ontology-free slices, bounded structural probes,
  evidence-linked hypotheses and an observation-only slow clock.
- Kept diagnostics read-only with respect to `J_mem`, candidate acceptance,
  verification, adoption and experiment comparison; no legacy runtime import
  is present.
- Verification: 3 focused tests passed, Python compilation passed, and the
  targeted legacy-import scan passed. This does not claim Deluxe completion or
  any live Minecraft/server experiment.

## 2026-08-21 paired evaluation and MC branch composition

- Added the current-contract `PairedBranchEvaluator` for control/candidate
  receipts and explicit metric deltas.
- Added `MinecraftPairedBranchRunner`, which enforces one prepared source-world
  cut, isolated branch materialization, injected workload execution and
  mandatory cleanup.
- Hardened platform comparability proof to reject reused branch identities.
- Verification: 22 focused tests and compilation passed. The concrete
  service/participant/Planner/SEM/workload executor and live server ladder are
  still not implemented or run.

## 2026-08-21 MC workload ABI adapter

- Added `MinecraftWorkloadEnvironmentAdapter` to translate the generic MC
  environment session into the Paper workload contract.
- Missing or malformed authoritative state now fails explicitly; no empty
  state is fabricated.
- Verification: 9 workload/branch/adapter tests and compilation passed. The
  concrete server-to-workload executor and live ladder remain pending.

## 2026-08-21 branch workload executor

- Added `MinecraftWorkloadBranchExecutor` for task-manifest execution through
  injected environment, SEM, evidence, Planner and diagnostics bindings.
- Added explicit aggregate branch metrics and close-failure propagation.
- Verification: 6 executor/adapter/branch tests and compilation passed. Real
  service, participant, Deluxe and model bindings remain pending.

## 2026-08-21 current SEM architecture presets and typed builder

- Added current-project `SemPaperArchitecturePreset.C/X` builders under the
  SEM architecture namespace; old v034 seed YAML remains reference evidence,
  not a runtime import.
- Added `ArchitectureDrivenTypedNodeBuilder` and an explicit injected semantic
  transform seam. It routes only declared J_mem event types and architecture
  upstream records, with no flat or empty fallback.
- Added the current-project live Deluxe factory composition over a selected
  preset and exact materialization contracts.
- Fixed Deluxe capability projection to deduplicate repeated field output
  types while preserving the full typed schema.
- Verification: 19 architecture/materialization/projection tests, 30 focused
  Deluxe/MC/evolution tests, compilation, diff check and legacy-import scan
  passed. No live model, server or Minecraft experiment was run.

The current development worktree remains package version `0.41.0` but is **ahead of the last verified release**. Release evidence remains frozen at the prior release; this file describes development-state changes only.

## Final architecture migration foundation

The direct final-architecture migration is now an active workstream governed
by `FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md` and
`FINAL_ARCHITECTURE_MIGRATION_MATRIX.md`.

- The 180-node system registry now materializes `owns`, `must_not_own`, and
  the standard `api/runtime/providers/composition` shape from the canonical
  catalog instead of silently dropping those fields at runtime.
- The canonical catalog is now packaged under
  `research_platform/governance/system_registry/catalog.json`; the `docs/`
  copy is checked as an exact mirror, so installed/server runs do not depend
  on the repository working directory.
- Release quality evidence is now a release API port injected by the platform
  composition root. The reverse dependency from governance release runtime to
  platform composition was removed, and the old governance composition entry
  was physically deleted.
- Workflow dispatch authority checks are now path-separator independent on
  Windows; the previous false failures were caused by comparing backslash
  paths with slash-separated authority records.
- Current structural verification: architecture gate PASS, package cycles 0,
  workflow invariant findings 0, CodeGraph circular-dependency check 0, and
  the four architecture analyzer unit tests PASS.

The full regression suite has not been rerun after these migration slices, so
the historical 709-test result below is not being promoted to current proof.
The local worktree has no Git repository; these changes therefore cannot yet
be committed or tagged.

## Harness-pattern integration

Added without adopting Cordis or an everything-is-a-plugin runtime:

- `model_request_api/runtime`: content-addressed, reconstructable model-visible requests bound to full immutable model identity and prompt generation.
- `scope_api/runtime`: hierarchical, reversible, quiescent registration lifetime management.
- `capability_runtime`: monotonic guards + approval + post-policy wrapped around the existing effect-safe execution engine.
- `projection_api/runtime`: source/version/watermark-bound incremental tails with fail-closed rebuild requirements.
- `record_api` + `fact_api`: Durable Fact / Live Interception / Side-Plane Observation semantics and fail-closed unknown required facts.
- architecture seam graphs: generated capability/operation/event producer-consumer views.

## Current verification

- 709 tests collected.
- 709 passed + 4 subtests in the latest complete development regression.
- Architecture gate PASS.
- Silent-Failure audit PASS.
- No-Degradation audit PASS.
- Architecture report SHA-256: `a5a7148a7d1d88b17105e85aef5a6bc6db9a4f48111316f1ff52fe0059f9ad70`.

## Policy unchanged

No compatibility layer is retained merely to preserve pre-run APIs. No lower-quality fallback is introduced. Runtime/backend changes must not silently change scientific identity, model identity, effect semantics, prompt identity or release reproducibility.

## 2026-08-21 host OS and target-path routing / Windows durability slice

- Promoted host OS identity and conventions to the `runtime/host` API/provider
  route (`OperatingSystemRoute`), and promoted cross-controller target-path
  semantics to `scope/path`. Session, service, tmux, artifact, server and
  Minecraft contracts now use one absolute-target-path authority.
- Local service composition now routes the process backend by host OS and
  refuses to silently use Linux `/proc` semantics on unsupported hosts.
- Windows interprocess locking now uses a path-derived named Mutex; the marker
  file remains observable but is not held open, preventing abandoned leases
  from pinning temporary trees while preserving one lock domain.
- Model-request ledgers and prompt publication reuse the platform lock
  authority. Raw/capture byte writers explicitly use binary mode on Windows;
  telemetry retries close failed writer sessions while retaining pending rows.
- Release regression process cleanup now has a Windows process-tree route;
  remote POSIX tmux paths are preserved instead of being rewritten by the
  controller's local `Path` flavor.
- Verification: 74 focused architecture/durability/forensics/prompt/path
  tests passed; 17 focused capture/telemetry/release/path tests passed after
  the binary and OS-route fixes. The full suite is not yet promoted: remaining
  failures are isolated to Linux `/proc`/signal assumptions, Windows symlink
  privilege, cross-host server-launcher fixtures, and direct test-owned SQLite
  connections that are not closed on Windows.

For historical Round 02 notes, use the repository history or older round documents; this file now serves as the current development summary.

## 2026-08-21 managed server identity and SSH connection route

Server connection is now a runtime/server identity concern rather than an
ad-hoc shell command in a project or script:

- `runtime/server/identity/api` owns the non-secret server profile, command
  result and health report contracts.
- `runtime/server/identity/providers/ssh.py` is the OpenSSH provider. It
  receives the host OS route and owns only argv construction plus remote
  command/result semantics; it never places a password in argv or invokes a
  local shell.
- `EnvironmentSSHServerConnectionFactory` reads one logical server profile
  from `RP_SERVER_<ID>_HOST`, `_PORT`, `_USER`, optional `_KEY_PATH`,
  `_KNOWN_HOSTS`, `_SSH_CONFIG` and `_SSH`. The repository contains no server address,
  account, password or private key.
- `scripts/server_health.py` is the operational entry point. It returns a
  machine-readable health report and non-zero status on an unreachable host.
  Automated operation requires an SSH key or agent; `--interactive` can be
  used when OpenSSH must prompt on a terminal.

The provider is explicitly composed with `runtime/host`'s OS route and is
covered by the source-authority architecture gate. The server route is
designed for multiple logical servers; changing the target means selecting a
different environment profile, not editing Python.

## 2026-08-21 recursive governance gate system

Governance gates now have their own registered `governance/gate` subsystem.
`GatePort`, `GateRequest`, `GateFinding` and `GateReport` form the only public
contract. `CompositeGate` recursively aggregates explicitly injected child
gates, preserves child reports as provenance and fails closed when a child
cannot produce a report. The parent does not discover a global rule registry.

The existing architecture analyzer is exposed through this contract by the
governance composition root. Future quality, security, release, server and
project gates can be supplied by each parent system through the same port and
can define their own child hierarchy without importing gate implementations
from unrelated systems. The old analyzer remains the architecture provider;
this slice changes ownership and composition, not the analyzer's scientific or
runtime semantics.
