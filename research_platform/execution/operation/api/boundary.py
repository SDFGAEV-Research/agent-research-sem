# vNext Boundary: execution/operation

SYSTEM = "execution"
NODE = "execution/operation"
OWNS = "operation identity, lifecycle and result envelopes"
MUST_NOT_OWN = "failure taxonomy and recovery authority"
AUTHORITY = "operation_state"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
