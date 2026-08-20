# Research Platform — Current Development Worktree

> **Current development truth:** see `docs/CURRENT_DEVELOPMENT_BASELINE.md`. The current worktree is in the final-architecture migration: the Paper-1 self-evolving-memory implementation is project-owned under `projects/sem_paper/method/self_evolving_memory`, and the current verified slice is limited to focused migration checks. A complete post-migration regression has not yet been rerun.
>
> **Current release truth (last verified release):** `RELEASE_MANIFEST.json` + `RELEASE_EVIDENCE.json` remain the authority for the last frozen release (`f18faec8c497...`, 675/675 tests). Ordinary development snapshots do **not** rewrite release evidence.
>
> **Official freeze workflow:** `python scripts/generate_release_evidence.py` → `python scripts/verify_release_evidence.py` → `python scripts/release_package.py` → `python scripts/verify_release_package.py <zip>`. An ad-hoc source ZIP is never a verified release.

## Current focus

The platform is now contract-driven and composition-root assembled. The current development cycle absorbed selected DeepSeek Harness runtime patterns without adopting Cordis or an "everything is a plugin" model:

- reconstructable model-visible requests (`model_request_api/runtime`);
- scope-owned reversible registrations with quiescent disposal (`scope_api/runtime`);
- monotonic-guard capability invocation policy around the existing effect-safe engine (`capability_runtime`);
- watermark/version-bound incremental projections (`projection_api/runtime`);
- generated capability / operation / event seam graphs in the architecture report;
- explicit Durable-Fact / Live-Interception / Side-Plane-Observation record planes.

See `docs/HARNESS_PATTERN_ADOPTION.md`, `docs/PLATFORM_ARCHITECTURE.md`, `docs/CURRENT_ARCHITECTURE_EVOLUTION_20260820.md`, and `docs/CURRENT_DEVELOPMENT_BASELINE.md` for the current design.

## Historical refactor record

## Round 56 — Durable Service Crash Handoff

- Added durable two-phase service crash coordination.
- Crash evidence is frozen first; no recovery is executed inside crash capture.
- Added idempotent forensic `append_failure_once()` against authoritative hash ledger.
- Added replayable crash handoff journal with phases:
  `PREPARED -> FAILURE_DURABLE -> STATE_COMMITTED -> COMPLETE`.
- Added idempotent service-state commit carrying the exact forensic `failure_id`.
- Fault-injection coverage includes:
  - crash after forensic append but before journal advance;
  - crash after service state commit but before journal advance;
  - immutable contract drift before replay.
- Full regression: **204 passed**.
- Gates: Architecture / Silent-Failure / No-Degradation **PASS**.


## Round 74
Cumulative platform refactor snapshot. Full regression and architecture/silent-failure/no-degradation gates passed for this round.


## Round 75
Prompt compile pipeline split into validation, strict budgeting, rendering, and schema binding. Full regression/gates PASS.


## Round 77
Cumulative validated refactor. Full regression and Architecture / Silent-Failure / No-Degradation gates PASS.


## Round 79
Cumulative validated refactor. Full regression and Architecture / Silent-Failure / No-Degradation gates PASS.


## Round 80
Metric emitter source coverage audit + real extended Prompt trace emission. Full regression/gates PASS.


## Round 81
Real runtime/one-click metric emission through low-level observability API. Full regression/gates PASS.


## Round 82
Durable exact recovery emits real attempt/duration/step metrics across failure and reconcile resume. Full regression/gates PASS.


## Round 83 — Failure Catalog Authority

- FailureCatalog now rejects semantic drift for the same `(domain, code)` across stages.
- Model-service crash taxonomy is registered centrally instead of carrying free-form recovery/risk semantics.
- Added source audit for literal failure taxonomy usage.
- Service crash projection resolves recovery/risk from the catalog.
- Full regression: **242 passed**.
- Architecture / Silent-Failure / No-Degradation: **PASS**.


## Round 84 — Operator Failure Catalog

- Added read-only `failure-catalog` operator command.
- Stable failure specs are filterable by domain/code without opening runtime state.
- Operator view exposes stage, recovery action and scientific/debugging risk semantics.
- Full regression and architecture/silent-failure/no-degradation audits passed.


## Round 85 — Taxonomy-Enriched Failure Diagnosis

- `why` and debug snapshots now expose registered FailureCatalog semantics.
- Diagnosis adds the exact catalog lookup command to next actions.
- Unregistered failures remain explicit (`registered=false`) and are never silently reinterpreted.
- Full regression and all safety/architecture audits passed.


## Round 86 — Spec-Driven Failure Construction

- Added `build_failure_from_spec()` as the production failure construction boundary.
- FailureRecorder and model service crash projection no longer repeat taxonomy/recovery/risk strings.
- Source audit rejects production free-form `build_failure(...)` calls outside the envelope primitive.
- Full regression and all architecture/silent-failure/no-degradation audits passed.


## Round 87 — Versioned Failure Taxonomy Binding

- Spec-driven FailureEnvelopes now carry the exact `FailureSpec.digest()`.
- Failure diagnosis compares historical envelope semantics with the current catalog.
- `semantic_drift` is explicit instead of silently interpreting old failures using new taxonomy semantics.
- Full regression and all audits passed.


## Round 88 — Version-Aware Incident Fingerprints

- Failure identity now incorporates the bound taxonomy spec digest.
- Incident OS tracks exact fingerprint (taxonomy-version aware) and family fingerprint (cross-version root-cause family).
- Exact and family recurrence counts/examples are kept separately.
- Full regression and all audits passed.


## Round 89 — Self-Describing Crash Bundles

- Crash bundle schema v2 embeds taxonomy binding/drift and exact/family incident fingerprints.
- Offline bundles no longer require the live forensic DB to understand failure semantics.
- Crash bundle serialization is strict; no `default=str` coercion.
- Full regression and all audits passed.


## Round 90 — Offline Crash Bundle Verification

- Added `crash-bundle-verify` for DB-independent bundle verification.
- Verifies transport digest, embedded failure identity, taxonomy snapshot digest, and exact/family fingerprints independently.
- Semantic tampering remains detectable even if an attacker/tool recomputes the outer bundle digest.
- Full regression and all audits passed.


## Round 91 — Failure Catalog as Debugging Knowledge Base

- Every default failure spec now carries owner, description, diagnostic focus and operator checks.
- Added catalog knowledge completeness audit.
- `why` and crash bundles surface the same operator knowledge.
- Full regression and all audits passed.


## Round 92 — Deterministic Triage Plans

- Added evidence-first `triage-plan` operator command.
- Triage order is deterministic and catalog-driven; recovery is never auto-executed.
- Missing external inputs are surfaced explicitly instead of inventing or skipping checks.
- Full regression and all audits passed.


## Round 93 — Authoritative Incident Projection Sync

- Incident recurrence is now projected from every verified failure-ledger row, not only manually opened incidents.
- Projection sync is incremental and checkpointed by source rows/tail hash.
- Prefix mismatch triggers a full disposable-index rebuild instead of mixing recurrence histories.
- Duplicate failure IDs are idempotently ignored in recurrence counts.
- Full regression and all audits passed.


## Round 94 — Incident Projection Physical Decomposition

- Split incident contracts, SQLite storage, projection mutation, ledger synchronization and façade.
- Preserved full-ledger recurrence accuracy and incremental freshness semantics.
- Full regression and all audits passed.


## Round 95 — Full Model Deployment Closure

- Model stack digest now binds model artifacts and executable runtime build identity, not only logical model metadata.
- ModelRunState freezes the qualified deployment digest.
- RecoveryPlanner rejects deployment stack/certificate/placement drift even when logical model identity is unchanged.
- Durable recovery plan digest includes the frozen deployment digest.
- Full regression and all audits passed.


## Round 96 — Stable Host Identity vs Live Capacity Snapshot

- Split stable host/runtime qualification identity from transient resource/occupancy snapshot.
- Qualification certificates bind hardware/runtime compatibility identity.
- Capacity planning revalidates live VRAM/RAM/ports/storage without invalidating qualification for unrelated transient drift.
- Capacity failure still fails closed; no stack/prompt/context degradation exists.
- Full regression and all audits passed.


## Round 97 — Runtime Host Inventory Evidence

- Runtime VERIFY_HOST_INVENTORY now captures and validates a real TargetHostInventory.
- Frozen host identity is checked by the platform, not delegated to an opaque external proof.
- Full live inventory snapshot receipts are atomically persisted and referenced by runtime evidence.
- Full regression and all audits passed.


## Round 98 — Historical Verified Runtime Baseline

- Revalidated the Round 97 runtime-host-inventory architecture as the new clean baseline.
- Full regression at the Round 98 freeze: **266 passed**. Current release verification is authoritative only through `RELEASE_EVIDENCE.json`.
- Architecture / Silent-Failure / No-Degradation: **PASS**.
- This round intentionally introduces no scientific/runtime behavior change.


## Runtime asset management

Day-to-day server resources are managed separately from scientific release qualification.
Use `research-platform-manage` with an explicit directory-layout config to manage workspaces,
Python environments (venv/conda/mamba), local model assets, and multi-model deployment desired state.
See `docs/RUNTIME_ASSET_MANAGEMENT.md` and `configs/runtime_management.example.json`.
