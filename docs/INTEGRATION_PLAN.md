# Integration Plan Against Frozen Release Evidence

## Current development status

Passes A–G are no longer merely planned boundaries: the current development tree has implemented the contract/runtime separation, forensic/telemetry planes, Prompt/Service/Participant API boundaries, generated capability/operation/event graphs, reconstructable model requests, scope-owned registrations, capability policy pipeline, and projection runtime. The current development regression is **709 passed + 4 subtests** with all three static gates PASS.

The remaining major work is **Pass H: target-host live deployment qualification**, plus continued systematic decoupling and measured performance/algorithm optimization. No live scientific run has been performed, so obsolete compatibility paths remain intentionally unnecessary.

The current regression count and release identity are not maintained manually in this document. `RELEASE_MANIFEST.json` is the byte-level source/document inventory and `RELEASE_EVIDENCE.json` binds that manifest to the full regression result, architecture report, silent-failure gate, and no-degradation gate. An official release ZIP must independently verify every package member against those two frozen artifacts.

Legacy `PACKAGE_CONTENTS.sha256` and `PACKAGE_METADATA.json` snapshots are intentionally removed so there is no second package manifest that can drift from the release manifest. The supported freeze path is `generate_release_evidence.py` → `verify_release_evidence.py` → `release_package.py` → `verify_release_package.py`. This refactor replaces rather than wraps obsolete compatibility layers.

## Pass A — Kernel identities
Move the canonical ExecutionContext/ComponentIdentity/Operation/Effect contracts into the platform kernel and migrate all LLM, environment, checkpoint and method boundaries.

## Pass B — Forensics OS
Merge the existing RunEvidenceStore/FailureDiagnosisService/evoctl why/locate/last-writer capabilities behind one causal evidence model. Raw ledgers remain append-only; indexes remain rebuildable.

## Pass C — Telemetry OS
Merge existing event/metric schemas into a central registry. Keep high-volume IDs out of metric labels and preserve them in events/traces. Add model/GPU/host/method/prompt families before the first live run.

## Pass D — Model Serving OS
Replace scattered deployment/recovery/model-run state with one model-run state machine, immutable ModelStack identity, host inventory, strict placement, exact restart/resume and canary qualification.

## Pass E — Prompt OS
Move all four prompt roles into atomic prompt generations. Runtime request construction must bind the exact bundle digest. Remove remaining prompt literals from method/runtime source.

## Pass F — Method ABI
Move Paper-1 implementation under `methods/self_evolving_memory`; platform and environment must only know `ResearchMethod/MethodSession`. No compatibility adapter is retained after the cutover.

## Pass G — Architecture/dataflow audit v2
CI validates import graph, component graph, capability graph, state authority, side-effect authority and scientific dataflow.

## Pass H — live deployment qualification
Only after target-host read-only inventory is captured:

1. pin exact model revisions and serving engine/container;
2. generate placement;
3. qualify startup and role canaries;
4. run throughput/latency characterization;
5. validate hard-kill/reboot/network-loss recovery;
6. validate exact checkpoint/study resume;
7. then start live Minecraft scientific qualification.
