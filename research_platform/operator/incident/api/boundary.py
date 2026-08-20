# vNext Boundary: operator/incident

SYSTEM = "operator"
NODE = "operator/incident"
OWNS = "incident triage and incident work surfaces"
MUST_NOT_OWN = "incident authority"
AUTHORITY = "operator_incident_view"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
