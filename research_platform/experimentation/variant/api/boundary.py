# vNext Boundary: experimentation/variant

SYSTEM = "experimentation"
NODE = "experimentation/variant"
OWNS = "experiment variants, assignments and comparison semantics"
MUST_NOT_OWN = "model deployment internals"
AUTHORITY = "variant_state"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
