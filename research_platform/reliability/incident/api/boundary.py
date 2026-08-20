# vNext Boundary: reliability/incident

SYSTEM = "reliability"
NODE = "reliability/incident"
OWNS = "incident grouping, lifecycle and incident identity"
MUST_NOT_OWN = "raw failure taxonomy"
AUTHORITY = "incident_authority"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
