# vNext Boundary: runtime/process/supervision

SYSTEM = "runtime"
NODE = "runtime/process/supervision"
OWNS = "process health/reconcile loops"
MUST_NOT_OWN = "durable runtime history storage"
AUTHORITY = "process_supervision"
