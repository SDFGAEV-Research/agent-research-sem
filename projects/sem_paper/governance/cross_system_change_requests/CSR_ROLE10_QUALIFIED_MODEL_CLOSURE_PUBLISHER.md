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

## Current independent evidence already completed by ROLE 10

Minecraft T2B is no longer the blocker. The earlier `35dddf3e7e8dc309505ca18de31f67ea88a8ffec` gate is intentionally superseded because the planner request contract changed. Exact runtime-sensitive SEM SHA `d797550ea1b5751be125bf2d53ffac522d8c7134` then passed T2B again on Server1 with Java 21, Node 22 and pinned Mineflayer dependencies. Gate digest: `cdfd5edbd95f256eb7fac3bee2eaf16293fab45a192fea0d17846e1e38502597`; gate-result SHA-256: `7e59ee9f3da2dcf2a2d4b041c1f118908a1b5b611b40aacdec2b0b526712e4a5`; verified evidence bundle SHA-256: `4815d8bcd8dbc1210fad1dac9296ffcb2e9f69ce729f5b9bee1a9bb633a1e4e8`.
