# Lifecycle OS v18

Every long-lived subsystem has an explicit lifecycle instead of relying on constructor/destructor ordering.

States: `NEW -> STARTING -> READY -> STOPPING -> STOPPED`, with `FAILED` explicit.

`LifecycleManager` validates all component IDs/dependencies and computes a deterministic topological startup order **before any start side effect**. A missing dependency or cycle therefore cannot leave a partially started platform. If a component fails to start, already-started components are stopped in exact reverse order. Rollback failures are preserved separately from the original start failure.

Health is distinct from lifecycle. A component may remain in `READY` but be classified `STALLED` when its heartbeat or progress heartbeat expires. Health records include generation, PID + process-start identity, heartbeat/progress time, last failure and a compact resource snapshot. This supports precise differentiation among:

- process dead;
- process alive but heartbeat dead;
- heartbeat alive but scientific/work progress stalled;
- component explicitly failed;
- component intentionally stopped.

No health classification silently selects another model, method, precision, context size or prompt.
