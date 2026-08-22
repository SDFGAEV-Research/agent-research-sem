# Round 129 — Qwen3.8-27B candidate acquisition

Date: 2026-08-22

## Decision

Qwen3.8-27B is an official Qwen open-weight release, not a rumor. It is the
latest practical Qwen candidate for this host class: the 2.4T Qwen3.8 model
is not a feasible asset for the current RTX 3090 server, while the 27B model
is a dense native vision-language model with a 262,144-token native context.

The paper's first model-backed path remains Qwen3.6-35B-A3B so that the
already qualified project/runtime plan is not invalidated by an unqualified
engine change. Qwen3.8 is acquired as an independent candidate and will be
promoted only after the same model identity, parser, memory, readiness,
restart and Paper-1 smoke contracts pass on the actual host.

## Server action

- Existing Qwen3.6-35B-A3B fetch was left running and untouched.
- A separate persistent session, `sem-paper-qwen38-model-fetch`, was created
  through the server session system.
- Candidate source: `Qwen/Qwen3.8-27B`, revision `main`, BF16 weights.
- Candidate destination: `/data/research-platform/model-pools/nvme/qwen38-27b`.
- Candidate remains unregistered until the complete artifact closure is
  independently verified.

## Qualification boundary

The current server has RTX 3090 GPUs and the active Qwen3.6 environment has
SGLang 0.5.10. The current official SGLang Qwen3.8-27B recipe is pinned to a
newer development revision and lists newer GPU classes for validation. The
Qwen3.8 candidate therefore cannot silently replace the Qwen3.6 path or reuse
its environment. A separate Qwen3.8 runtime must first prove boot, parser
semantics, memory stability, endpoint readiness and exact restart behavior.
