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

For historical Round 02 notes, use the repository history or older round documents; this file now serves as the current development summary.
