# vNext Boundary: platform/identity

SYSTEM = "platform"
NODE = "platform/identity"
OWNS = "platform identity and immutable platform metadata"
MUST_NOT_OWN = "workspace/project/run identity"
AUTHORITY = "platform_identity"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
