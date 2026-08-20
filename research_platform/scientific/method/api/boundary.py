# vNext Boundary: scientific/method

SYSTEM = "scientific"
NODE = "scientific/method"
OWNS = "method identity, configuration and lifecycle"
MUST_NOT_OWN = "runtime session internals"
AUTHORITY = "method_identity"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
