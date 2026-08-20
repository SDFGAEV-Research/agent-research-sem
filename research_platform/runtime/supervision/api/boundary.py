# vNext Boundary: runtime/supervision

SYSTEM = "runtime"
NODE = "runtime/supervision"
OWNS = "supervision loops, health checks and restart/reconcile orchestration"
MUST_NOT_OWN = "diagnostic storage and failure taxonomy"
AUTHORITY = "supervision_state"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
