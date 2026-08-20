# vNext Boundary: reliability/policy

SYSTEM = "reliability"
NODE = "reliability/policy"
OWNS = "reliability invariants, no-fallback rules and escalation policies"
MUST_NOT_OWN = "runtime implementation"
AUTHORITY = "reliability_policy"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
