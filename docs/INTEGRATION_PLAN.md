# Integration Plan Against Frozen Release Evidence

## Current development status

Passes A–G are no longer merely planned boundaries: the development tree has implemented the contract/runtime separation, forensic/telemetry planes, Prompt/Service/Participant API boundaries, generated capability/operation/event graphs, reconstructable model requests, scope-owned registrations, capability policy pipeline, and projection runtime. The worktree is currently in the final-architecture migration of the Paper-1 method; only focused migration checks have been rerun after the move, and a complete post-migration regression is still pending.

The remaining major work is the production project/method host wiring, then **Pass H: target-host live deployment qualification**, plus continued systematic decoupling and measured performance/algorithm optimization. No live scientific run has been performed, and the retired top-level method boundary is not kept through a compatibility path.

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
Move Paper-1 implementation under `projects/sem_paper/method/self_evolving_memory`; platform and environment must only know `ResearchMethod/MethodSession`. No compatibility adapter is retained after the cutover.

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

## 2026-08-20 migration overlay

The historical development-regression sentence near the top of this document
predates the final-architecture SEM move and is not current evidence. After
the move, the verified slice is the 23-test focused migration regression plus
five direct project-composition firewall checks and Python syntax compilation;
a complete post-migration regression is pending.
The current production path is now project-owned:

```text
platform API/ports
        -> projects/sem_paper/composition
        -> projects/sem_paper/method/self_evolving_memory
```

The paper method may implement its own logging, serving, state, and evolution
adapters behind injected platform interfaces. The platform does not own or
import those scientific implementations. No live scientific run has been
performed.
