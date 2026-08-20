# vNext Boundary: runtime/control

SYSTEM = "runtime"
NODE = "runtime/control"
OWNS = "runtime control commands, transitions and recovery handoff"
MUST_NOT_OWN = "failure taxonomy and recovery evidence"
AUTHORITY = "runtime_control"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
