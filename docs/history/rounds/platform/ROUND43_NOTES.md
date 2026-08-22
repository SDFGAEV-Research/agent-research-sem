# Round 43 — Automatic deployment environment closure and server-first status

Date: 2026-08-23

## Objective

Turn model deployment preparation into a platform capability that derives the
required runtime and package evidence from the actual target environment. The
operator should not manually correlate Ubuntu, kernel, libc, NVIDIA driver,
CUDA, GPU architecture, Python ABI, package indexes, native wheels and model
artifacts. This round extends the existing `model/qualification` system; it
does not add a second package manager, model registry or serving authority.

The direction is deliberately fail-closed. An unavailable compatibility fact
is an explicit incomplete qualification, not permission to install a weaker
backend, silently use a different index, or lower the requested deployment
quality.

## Implemented source changes

The qualification evidence model now has a recursive dependency layer:

```text
target interpreter
  -> PEP 503 simple-index page
  -> compatible binary wheel + PEP 658 metadata
  -> Requires-Dist requirements with environment markers
  -> compatible dependency wheel + metadata
  -> ...
  -> complete / incomplete dependency-closure evidence
```

The durable objects are:

- `PackageArtifactFacts`: wheel identity, version, link hash, metadata hash,
  Python/ABI/platform tags, `Requires-Python` and parsed direct requirements;
- `PackageDependencyNodeFacts`: one resolved package version and its artifact
  evidence, all under the same index/target-Python observation;
- `PackageIndexFacts`: root candidate, artifact facts, dependency nodes and an
  explicit `dependency_closure_complete` / `dependency_closure_error` result.

The target-Python probe reads PEP 658 `.whl.metadata` only. It does not fetch
wheel payloads and does not use `pip install --dry-run` as a read-only
resolver. It evaluates environment markers for the observed interpreter,
rejects direct URL requirements, checks version specifiers, detects conflicting
versions, bounds the observed graph at 512 nodes, and reports all observation
failures. The resolver accepts a backend only when its dependency closure is
complete. The closure is evidence, not an installation side effect.

This changes the qualification meaning from:

```text
"a compatible root wheel was visible"
```

to:

```text
"a compatible root wheel and a complete, target-interpreter dependency
closure were observed"
```

The server operation ledger also gained an offline reconciliation path. A
failed remote operation can be resolved from the controller-local ledger and
the recorded profile digest even when the current SSH identity is unavailable.
Reconciliation does not contact or mutate the remote host; this removes the
credential-repair deadlock in which fixing an SSH key was blocked by the
unreconciled operation that the key failure had prevented from being inspected.

## Evidence and current limits

The previous server validation remains valid for the v3 wheel-evidence slice:
38 focused tests, architecture gate, and no-degradation audit passed. A
subsequent v4-focused server run passed 39 tests before the final diagnostic
branch fix below. That run verified the new code path structurally, but it is
not treated as final v4 qualification evidence until the corrected source is
uploaded and rerun.

The real v4 qualification reached recursive dependency evidence on the Ubuntu
RTX 3090 host. It recorded:

- facts digest:
  `18935b4368ffd15d59edd8e16e5ab15ad0cf891e12af84d54f85505d3179421c`;
- plan digest:
  `111225c4081a9a929da00e5082fdb8827edcc3c6181ff61f57f7acc04c3c990e`;
- SGLang's closure reported no compatible binary wheel for `cuda-tile`;
- the SGLang-kernel metadata request reported an HTTP error;
- the vLLM path exposed a probe-diagnostic defect rather than a valid
  compatibility decision.

The vLLM isolated retry then exposed the exact source defect: the target
simple-index subprocess returned a non-zero result, but the diagnostic branch
had discarded the stderr variable and raised `NameError` while formatting the
error. The local source now binds and preserves that stderr. The failed
operation was reconciled as `effect_not_applied`; the target environment was
not installed into, no model process was started, and no scientific result was
produced.

The corrected source has not yet been uploaded because the local profile
currently points to an unavailable SSH key. This is an infrastructure access
blocker, not a qualification result. The platform intentionally does not
reintroduce hidden password prompts or downgrade to an unaudited transport.

## Required next sequence

1. Restore a valid key/agent identity for the declared `sem-ubuntu` profile.
2. Upload the corrected probe, server-ledger script and regression test through
   the persistent repository uploader.
3. Run the focused server suite, architecture gate and no-degradation audit.
4. Run isolated vLLM recursive qualification and inspect its complete error or
   acceptance evidence.
5. Rerun both backend candidates, then update the authoritative digests only
   from the corrected server record.
6. Materialize nothing until the closure is complete and the user explicitly
   authorizes the mutating deployment step. A successful plan is still not a
   serving or scientific qualification certificate.

## Non-claims

This round did not install vLLM/SGLang, start a serving process, run Minecraft,
run the SEM paper experiment, or alter the memory method. It only strengthens
the reusable AI-infrastructure qualification and its evidence governance.
