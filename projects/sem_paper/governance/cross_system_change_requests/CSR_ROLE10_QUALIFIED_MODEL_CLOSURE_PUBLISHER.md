# CrossSystemChangeRequest — Qualified Model Deployment Closure Publisher

- request_id: `CSR-ROLE10-20260829-QUALIFIED-MODEL-CLOSURE-PUBLISHER`
- requester role/system: `ROLE 10 — SEM Composition / Experiment Integration`
- target owner/system: `ROLE 06B — Model / Deployment / Qualification / Serving`
- status: `ASSIGN_TO_TARGET_OWNER_REQUIRED`

## Concrete problem and failing call path

SEM baseline production is already fail-closed on a platform-qualified model binding. `scripts/sem_paper_minecraft_application.py` loads a platform-published `qualified-model-deployment-closure.v1`, reconstructs it with `load_qualified_model_deployment_closure()`, and calls `PersistedQualifiedModelEndpointBinding(...).binding_for(role="planner", prompt_generation="sem-paper-planner-generation-v1")`.

The current platform source has the typed closure reader and runtime receipt store, but no production publisher that constructs and durably publishes the `QualifiedDeploymentManifest` / `QualificationCertificate` / route / runtime qualification receipt / complete closure. Production constructors for those objects exist only in tests. ROLE 10 therefore cannot legitimately close `LIVE_EXECUTION_EVIDENCE` or start claim-eligible baseline runs.

Server1 live observation on 2026-08-29 confirms that `sem-qwen38-qualification-tp2` is serving `sem-qwen38-27b` successfully at `127.0.0.1:30080`, but HTTP health is deliberately not accepted as qualification evidence. `/data1/research-platform/state/model-serving` contains no published qualified closure.

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
5. Linux/GPU live test on authoritative Server1 using frozen Qwen3.8-27B revision and exact container digest; a real planner canary must pass before publication.
6. ROLE 10 integration test consumes only the published closure and records the resulting `QualifiedModelEndpointBinding` digest into the run manifest.

## Current independent evidence already completed by ROLE 10

Minecraft T2B is no longer the blocker. Exact SEM SHA `35dddf3e7e8dc309505ca18de31f67ea88a8ffec` passed T2B on Server1 with Java 21, Node 22 and pinned Mineflayer dependencies. Gate digest: `dcf2ced67974742b153149e0726fbeb2f1e2e53aa579f24e3fc7a0577f6ca19c`; verified evidence bundle SHA-256: `dabfa7d71941bb45322483c45a3e1dc7ce6b5ac8f25aa5c0a9dfcca5a036cc06`.
