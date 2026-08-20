# vNext Boundary: governance/schema

SYSTEM = "governance"
NODE = "governance/schema"
OWNS = "schema/version declarations for contracts and records"
MUST_NOT_OWN = "domain state mutation"
AUTHORITY = "schema_authority"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
