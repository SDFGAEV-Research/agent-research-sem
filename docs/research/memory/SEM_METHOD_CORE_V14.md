# Self-Evolving Memory Method Core — Round 14

## Evidence cut

`J_mem` now exposes a pinned `MemoryEvidenceSnapshot(sequence, rows, digest)`. Clean materialization consumes exactly one snapshot and records both source sequence and snapshot digest. `J_audit` and `J_eval` remain separate stores and have no type path into the materializer.

## Structural compilation

Meta's external grammar remains `NO_EDIT / CREATE / RETIRE / SPLIT / MERGE`. The trusted compiler expands SPLIT/MERGE into bounded CREATE/RETIRE primitive plans. `OperationalVerifier` checks operational legality only and exposes no score/accept decision.

## Paired evaluation

The generic platform defines `BranchReceipt` and a mechanical `ComparabilityProof`. Same checkpoint, workload, environment generation and task manifest are required; branch-to-lifetime writes and private-evaluation-to-method flows invalidate the proof. SEM consumes this proof but does not own environment forks.

## Adoption transaction

Adoption is the only architecture activation authority:

1. verify candidate still targets current generation;
2. allocate a prepared generation;
3. clean-build the **entire target** from pinned J_mem;
4. atomically CAS architecture head + evolution ledger;
5. mark the generation committed only after the atomic state transaction succeeds;
6. abandon the prepared generation on any transaction failure.

A candidate evaluation branch is never promoted as runtime state.
