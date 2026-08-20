# vNext Boundary: observability/projection

SYSTEM = "observability"
NODE = "observability/projection"
OWNS = "observation projections/indexes and read models"
MUST_NOT_OWN = "source-of-truth mutation"
AUTHORITY = "observation_projection"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
