# CrossSystemChangeRequest — Qualified Model Deployment Closure Publisher

- request_id: `CSR-ROLE10-20260829-QUALIFIED-MODEL-CLOSURE-PUBLISHER`
- requester role/system: `ROLE 10 — SEM Composition / Experiment Integration`
- target owner/system: `ROLE 06B — Model / Deployment / Qualification / Serving`
- status: `ASSIGN_TO_TARGET_OWNER_REQUIRED`

## Concrete problem and failing call path

SEM baseline production is already fail-closed on a platform-qualified model binding. `scripts/sem_paper_minecraft_application.py` loads a platform-published `qualified-model-deployment-closure.v1`, reconstructs it with `load_qualified_model_deployment_closure()`, and calls `PersistedQualifiedModelEndpointBinding(...).binding_for(role="planner", prompt_generation="sem-paper-planner-generation-v1")`.

The current platform source has the typed closure reader and runtime receipt store, but no production publisher that constructs and durably publishes the `QualifiedDeploymentManifest` / `QualificationCertificate` / route / runtime qualification receipt / complete closure. Production constructors for those objects exist only in tests. ROLE 10 therefore cannot legitimately close `LIVE_EXECUTION_EVIDENCE` or start claim-eligible baseline runs.

Server1 live observation on 2026-08-29 confirms that `sem-qwen38-qualification-tp2` is serving `sem-qwen38-27b` successfully at `127.0.0.1:30080`, but HTTP health is deliberately not accepted as qualification evidence. `/data1/research-platform/state/model-serving` contains no published qualified closure.

### Server1 qualification inputs observed by ROLE 10

These are live inputs for ROLE 06B qualification, not a downstream substitute for qualification:

- container id: `1a2519404f2116dc7cd524fe8b0391042b2474f145c13dc2b6adaee43b762efd`;
- immutable image digest: `vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967`;
- vLLM `0.27.1`, Torch `2.13.0+cu130`, NCCL package `2.30.7`;
- serving profile: `sem-qwen38-27b`, tensor parallel `2`, `bfloat16`, max model length `262144`, endpoint `127.0.0.1:30080`;
- model `config.json` SHA-256 `191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab`;
- tokenizer config SHA-256 `b11349aafa7cdc6a320767cf7ceb29ed82f7eda5d65e8e0819e76f0ce947bf27`.

A planner canary also exposed a qualification-critical request contract. With the serving default reasoning mode and `max_tokens=32`, the request returned only hidden reasoning/blank visible content with `finish_reason=length`. The same canary with `chat_template_kwargs={"enable_thinking": false}` returned exactly `{"status":"ok"}` with `finish_reason=stop`. ROLE 10 therefore froze non-thinking mode in production planner commit `d797550ea1b5751be125bf2d53ffac522d8c7134`. ROLE 06B qualification must canary the same effective request semantics; a generic `/health` or `/v1/models` success is insufficient.

## Current public contract

- `research_platform.model.serving.endpoint.providers.qualified_closure_file.load_qualified_model_deployment_closure`
- `research_platform.model.serving.endpoint.providers.qualified_binding.PersistedQualifiedModelEndpointBinding`
- `research_platform.model.serving.api.QualifiedDeploymentManifest`
- `research_platform.model.serving.api.QualificationCertificate`
- `research_platform.model.serving.api.RuntimeQualificationReceipt`
- generic deployment qualification CLI stages: `deployment qualify`, `apply-qualification`, `runtime-qualify`

The consumer contract explicitly states that qualification/deployment systems publish the closure and downstream projects only consume it.

## Required capability / semantic gap

ROLE 06B must provide one platform-owned production authority that turns exact measured deployment facts into an immutable, durable `qualified-model-deployment-closure.v1` and associated runtime qualification evidence. The publisher must bind, rather than infer:

- immutable model identity/revision and model artifact digests;
- exact serving runtime/container image digest and engine build identity;
- CUDA/NCCL/Torch/runtime identities;
- tensor-parallel degree and exact GPU UUID placement;
- host identity digest;
- deployment id and deployment generation;
- endpoint route generation and live readiness/canary evidence;
- measured resource envelope;
- qualified role `planner`;
- runtime qualification receipt and evidence refs;
- immutable closure digest / publication identity.

A mutable image tag, operator URL, model name, successful `/health`, or manually authored JSON must never substitute for the authority above.

## Authority impact

Model qualification/deployment/serving remains the sole producer authority. ROLE 10 remains a read-only consumer of the published closure and binds it into SEM run/scientific provenance. No duplicate downstream model authority is requested.

## Persistence impact

Publication must be durable, publish-once/idempotent for identical content, reject conflicting overwrite, checksum its referenced evidence, and preserve the exact deployment/runtime generation used by the closure. Relative runtime-evidence paths must remain relocatable with the closure bundle or be explicitly materialized as an immutable evidence package.

## Failure / recovery / effect impact

The publisher must fail closed on artifact drift, container/runtime drift, GPU placement drift, route-generation drift, stale heartbeat/readiness, missing canary evidence, missing role qualification, partial publication, or restart to a new deployment generation. Recovery must never reuse an old receipt for a newly started process/container generation.

## Expected consumers

- ROLE 10 SEM Minecraft baseline/preflight composition
- generic downstream projects requiring `QualifiedModelEndpointBinding`
- operator/release qualification gates
- model-serving recovery/admission paths

## Breaking-change impact

`YES` if required. There is no valid production writer to preserve. Prefer one authoritative typed publication path over compatibility shims or a second closure schema.

## Proposed acceptance tests

1. Unit round-trip: publisher → persisted closure → existing loader → `binding_for("planner", "sem-paper-planner-generation-v1")` succeeds and all digests agree.
2. Tamper tests: model artifacts, runtime/container identity, host identity, GPU UUIDs, certificate digest, route generation, runtime receipt digest, and role each fail closed independently.
3. Publication tests: identical replay is idempotent; conflicting replay is rejected; interrupted/partial publication never exposes a valid closure.
4. Lifecycle test: container/process restart changes generation and invalidates the previous live receipt until requalification.
5. Linux/GPU live test on authoritative Server1 using frozen Qwen3.8-27B revision and exact container digest; the canary must use the SEM planner request contract, including `chat_template_kwargs={"enable_thinking": false}`, and reject blank/length-truncated visible output.
6. ROLE 10 integration test consumes only the published closure and records the resulting `QualifiedModelEndpointBinding` digest into the run manifest.

## Read-only integration review of in-progress ROLE 06B publisher

ROLE 10 reviewed the target worktree read-only on 2026-08-29 at base HEAD `26443d6` while the publisher/codec changes were still uncommitted. The direction is correct: strict v2 codec, closure digest, deployment/route alignment, interprocess publication lock, runtime receipt readback, role coverage, and publish-once closure semantics are present. The following items still need to close before handoff:

1. The focused target suite currently reports `9 passed, 1 failed`. `test_identical_replay_is_idempotent_and_conflict_is_rejected` fails because `DirectoryRuntimeQualificationEvidenceStore.publish()` compares a JSON-loaded payload containing lists against the in-memory payload containing tuples, so an identical replay is misclassified as conflicting evidence. Canonicalize both sides before equality/digest comparison.
2. Closure publication accepts a directly constructed `RuntimeQualificationReceipt` and checks only `created_at > 0`; neither publication nor `PersistedQualifiedModelEndpointBinding` enforces receipt freshness. A stale but structurally valid receipt can therefore be rebound later. Freshness/expiry must be an explicit persisted policy/identity and fail closed at publication and/or binding time.
3. `ServiceHeartbeat` carries `pid`, `process_start_marker`, `argv_digest`, readiness and timestamp, but `RuntimeQualificationReceipt` does not persist the process-instance identity. The durable closure therefore cannot prove that a later binding still refers to the process/container instance that passed the canary. Bind a process/deployment generation digest derived from the live heartbeat/runtime generation and invalidate it on restart.
4. `evidence_refs` are currently only required to be non-empty strings. The closure publisher must resolve or otherwise verify immutable/content-addressed canary/performance evidence and bind those evidence digests into the durable authority; opaque strings alone do not satisfy the requested evidence checksum invariant.
5. The in-progress codec intentionally moves to `qualified-model-deployment-closure.v2`. ROLE 10 does not require v1 compatibility, but after ROLE 06B lands this breaking contract, downstream audit/consumer tests must migrate atomically to v2 before claim-eligible execution.

These are integration acceptance findings only. ROLE 10 must not patch the target-owned model-serving files.
## Second read-only integration review

A second read-only review was performed after ROLE 06B committed `8caf794 feat(model): publish immutable qualified closures` and `6552de5 fix(model): stabilize qualification publication lock keys`, with additional target-owned fixes still uncommitted. The focused closure/runtime-qualification/generation/transport suite now reports `24 passed`.

The earlier replay, freshness, and process-generation findings are materially addressed in the in-progress target tree: runtime receipts persist `process_pid`, `process_start_marker`, `argv_digest`, `heartbeat_timestamp`, and `valid_until`; stale receipts are rejected at publication and binding; digest-bound heartbeat evidence is reconstructed; process restart changes receipt identity; and runtime receipt storage uses a strict v3 codec.

One qualification-critical gap remains: digest-bound `canary:sha256:*` and `performance:sha256:*` references are accepted as optional extras, but the receipt/publication contract does not require a planner canary reference or performance evidence to be present. A heartbeat-only receipt can therefore still satisfy the closure publisher. Before handoff, the platform authority must require and verify the evidence classes needed by the qualified role, including the real planner canary whose request semantics match SEM (`chat_template_kwargs={"enable_thinking": false}`), rather than treating those refs as optional metadata.

The lifecycle/process-generation fixes landed in ROLE 06B commit `9722795261fc4c52857d3281370c399bfa425f74`. A platform-owned runtime-canary authority is now being developed in the target worktree but is not yet committed. ROLE 10 has independently removed its own hard-coded v1 schema gate so future closure schema acceptance is delegated to the platform loader/codec rather than duplicated downstream.
## Current independent evidence already completed by ROLE 10

Minecraft T2B is no longer the blocker. ROLE 10 now rejects non-terminal model completions (`finish_reason=length/content_filter/tool_calls`) before planner JSON/action acceptance. Exact runtime-sensitive SEM SHA `e6d38fb6bd71bfae0ff40ad4d4d11be203bba085` passed T2B again on Server1 with Java 21, Node 22 and pinned Mineflayer dependencies. Gate digest: `99a5109d7ae603499a7947bead4d1af152e382db8cd149ea3f2cff0732f2e100`; gate-result SHA-256: `6c7618b012bb70dbc9230653d8a5c4ede4b3330c09ea0dea61d86591111aa538`; verified evidence bundle SHA-256: `26c83cf50b9b5fe1ada5ce44869299856ee7de94b91f167f03b0cf1e57e8c202`. Older T2B artifacts remain preserved as history but are rejected by the source-current gate.
