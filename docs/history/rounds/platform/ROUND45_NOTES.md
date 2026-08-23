# Round 45 — Deterministic constraint reconciliation and real backend qualification

Date: 2026-08-23

## Root causes resolved

The first fast recursive probe exposed a real resolver defect rather than a
host incompatibility. It selected the newest version for each dependency as
soon as that dependency was first encountered. Later requirements could then
impose a tighter bound and produce a false conflict, even when a common
version existed. The vLLM graph demonstrated this with `numpy`: the valid
solution is `numpy==2.3.5`, while the greedy first choice was too new for a
later `mistral-common` constraint.

The target-Python resolver now performs deterministic fixed-point constraint
reconciliation:

```text
selected nodes
  -> collect all active Requires-Dist constraints
  -> combine specifiers per normalized package
  -> select a version satisfying the combined constraint
  -> fetch its metadata and repeat if the node changed
  -> stable closure or explicit unsatisfiable evidence
```

Old-version constraints are recomputed from the current selected graph when a
node changes, so stale requirements are not retained as hidden constraints.
If no binary wheel satisfies the combined requirements, the closure remains
incomplete and the backend is rejected with the combined constraint evidence.

The initial implementation was also too slow because independent package
pages and metadata documents were fetched serially. Independent resolution
requests now run through a bounded 16-worker target-interpreter pool, while
results are merged in deterministic dependency order. This changes only
transport scheduling; it does not skip nodes, remove metadata checks, increase
the graph boundary, or turn timeouts into acceptance.

## Server verification

The corrected source was uploaded through the persistent server uploader and
validated on the Ubuntu RTX 3090 host:

- focused qualification, installer, evidence, runtime, public API and
  composition-boundary suite: **42 passed**;
- `ARCHITECTURE_GATE_PASS`;
- `NO_DEGRADATION_AUDIT_PASS`;
- isolated vLLM qualification completed in about 61 seconds and accepted
  `vllm==0.27.1` with a **162-node** dependency closure and **161** transitive
  packages in the frozen install plan;
- isolated vLLM facts digest:
  `bd1129ea2f7640e7361712adb649a4840d03ea288f48d6ed820fe6f8506f1fb5`;
- isolated vLLM plan digest:
  `f95e55080a57266d51d0b433a952075e4639d95a1f79a1e11db921b8bda14e48`;
- isolated vLLM record digest:
  `3a5756c88e6a765d8ddb54374416919735e44bd7c97806098c3d9c1a5f766919`;
- the reconciled numpy choice was `numpy==2.3.5`;
- the full SGLang/vLLM qualification completed in about 104 seconds with
  facts digest
  `23a10803981db312760d617e5e0bd88650457464eec90e8a7432b38e008d6e2c`,
  plan digest
  `504f51ea3a48f87b8d05cb03c6b55fe3d7c623003ef2da0ea19a2938c4d56c57`, and
  record digest
  `ea8a9403996d56a21bb35781f544b3fa3343bead81aebab354cef14eefb84de6`;
- the full plan selected vLLM and rejected SGLang because `cuda-tile==1.6.0rc5`
  had no compatible binary wheel, SGLang-kernel metadata returned an HTTP
  error, and the observed kernel architectures `sm100,sm90` did not cover
  host `sm86`.

All qualification commands were read-only. No package was installed, no model
service was started, and no Minecraft or SEM experiment was run. “Accepted”
here means accepted for the next explicitly governed materialization step; it
is not yet an import, serving-readiness or scientific certificate.

## Next controlled step

Commit and push the solver changes, preserve the server's controlled dirty
development state through the platform repository workflow, synchronize the
exact pushed revision, then rerun the same gates from a clean checkout. Only
after that reproducibility check may the user-authorized small materialization
step be considered.
