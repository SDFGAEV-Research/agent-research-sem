# vNext Boundary: runtime/history

SYSTEM = "runtime"
NODE = "runtime/history"
OWNS = "runtime state/history snapshots and integrity"
MUST_NOT_OWN = "current live process truth"
AUTHORITY = "runtime_history"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
