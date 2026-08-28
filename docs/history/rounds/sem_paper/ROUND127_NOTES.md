# Round 127 — recovery invariant audit locality repair

## Failure found by server architecture regression

The AI-infrastructure migration regression reached the source-invariant suite
and exposed one failure unrelated to model serving:
`test_recovery_lease_store_cannot_own_execution_fencing` constructed only the
recovery-provider subtree, but `audit_runtime_recovery_invariants` returned
early when the execution-manager subtree was absent. The auditor therefore
missed a forbidden `RecoveryLeaseStore.execution` method.

## Root cause and repair

The guard incorrectly treated the execution-manager directory as a prerequisite
for every recovery invariant. The store, one-click runtime and execution-fence
checks are independent observations. The early return was removed; each check
now remains conditional only on its own source file while the store audit runs
whenever the store exists.

This strengthens the governance system and does not weaken or skip a check.

## Verification gate

The changed source-invariant test and the full architecture subset must be
rerun on the Ubuntu server before this round is considered verified.
