# Round 99 – Paper method ownership and project composition migration

## Scope

This round migrates the concrete Paper-1 self-evolving-memory method into its
project-owned namespace and makes the platform/project seam explicit. The
self-evolving memory is the paper's scientific method, not a generic platform
implementation.

## Architecture changes

- Moved the 64-file method implementation from the retired top-level
  `methods/self_evolving_memory` root to
  `projects/sem_paper/method/self_evolving_memory`.
- Physically removed the empty historical `methods/` package root; no
  production/test import or packaging entry points target it.
- Kept platform ownership at stable interfaces such as
  `MethodCompositionPorts`, method endpoint/runtime ports,
  `MethodObservationOutboxPort`, and `LogSinkPort`.
- Added `projects/sem_paper/composition/project.py` as the Paper-1 composition
  root. It binds fixed and self-evolving treatments and the Paper-1 logging
  policy from injected ports without opening a session or starting an external
  process.
- Added an executable project API firewall check for concrete platform-layer
  imports and physical retirement of the historical method root.
- Corrected the no-degradation audit's exclusion paths after the quality system
  migration; the audit now excludes its actual
  `research_platform/governance/quality` implementation files.

## Evidence

- Architecture gate: PASS.
- Silent-failure audit: PASS.
- No-degradation audit: PASS.
- Python compileall: PASS.
- Focused unittest regression: 23 passed.
- Direct Paper-1 project-composition/firewall checks: 5 passed.
- CodeGraph one-shot circular dependency check: 0 cycles.
- Current development snapshot: 2281 files, 2180 Python files, 223 test
  modules; architecture report SHA-256
  `dd7576b9456a4e0bf8bd6976098e0be3b3a33711c3f39c998493ca43a4dbf2a9`.

## Explicit non-claims

- No Minecraft execution, training, benchmark, or scientific experiment was
  run.
- The complete post-migration regression has not yet been rerun.
- The generic platform host has not yet been proven to call the Paper-1 project
  composition root through the full experiment/run production chain.
- `RELEASE_MANIFEST.json` and `RELEASE_EVIDENCE.json` remain frozen historical
  release evidence; this round only regenerates development snapshot evidence.
