# vNext Boundary: reliability/reconciliation

SYSTEM = "reliability"
NODE = "reliability/reconciliation"
OWNS = "uncertain effects, projection drift and state reconciliation"
MUST_NOT_OWN = "new business state creation"
AUTHORITY = "reconciliation_authority"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
