# Round 42 — Binary-wheel qualification without artifact downloads

Date: 2026-08-23

## Purpose

Extend the automatic model-deployment qualification system so an index's
newest version is not accepted merely because it is listed. The target Python
ABI, interpreter-supported wheel tags and platform tags must participate in the
candidate decision without turning a read-only probe into a package install or
large artifact download.

## Implemented

- Added typed package-artifact facts for filename, version, wheel kind, SHA-256
  link hash, Python/ABI/platform tags and `Requires-Python`.
- The qualification probe now reads PEP 503 simple-index links through the
  target interpreter and chooses the newest version exposing a compatible
  binary wheel. It does not use `pip install --dry-run` and does not download
  wheels.
- The resolver now consumes `selected_version` from artifact compatibility
  evidence. A package with no compatible binary wheel is rejected with an
  explicit cause; it is never silently downgraded or switched.
- Durable qualification evidence moved to
  `model-deployment-qualification-evidence.v3`; v2 snapshots are not silently
  interpreted as v3 records.

## Server evidence

The formal `research-platform-manage deployment qualify` command was run on
the Ubuntu validation host with the Qwen3.6-35B-A3B artifact and tensor
parallel width 4. It recorded:

- facts digest
  `66f1bb904303d12bb69d17beda7f7144cdbd9fa21ced3e75f04066b268080823`;
- plan digest
  `216ad4d756cd35df0141e6844df291a2ca4c59e9e56173d204c825f4154eafbe`;
- record digest
  `83ac16117f106ff80e1a7e41f356925283e15f46a463750be6c89bfc24f2dd45`;
- SGLang `0.5.18` and `sglang-kernel 0.4.6.post1+cu130` exposed compatible
  binary wheels for the target Python, but SGLang was still rejected because
  its observed native architectures `sm90,sm100` do not cover host `sm86`;
- vLLM `0.27.1` exposed one compatible binary wheel and remained the selected
  candidate.

Server regression passed **38 focused tests**, `ARCHITECTURE_GATE_PASS`, and
`NO_DEGRADATION_AUDIT_PASS`. The target Qwen environment was not changed, no
vLLM service was started, and no SEM scientific result was produced.

## Root-cause correction

A preliminary dependency-resolution probe used `pip install --dry-run
--report -`. Independent inspection showed that pip was downloading a large
CUDA wheel into a temporary directory while resolving dependencies. The exact
dry-run process was terminated, the target environment was verified to have no
vLLM installation, and the server operation was reconciled as
`effect_not_applied`. The platform now uses simple-index metadata for this
stage. Full dependency-closure evidence remains the next bounded slice.

## Remaining boundary

The system now closes host/GPU/fabric/storage/model facts and binary-wheel
compatibility. It still needs a non-downloading, marker-aware transitive
dependency-closure resolver, live serving readiness proof, and migration of
residual host-inventory ownership into the final resource topology.
