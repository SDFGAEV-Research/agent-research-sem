# vNext Boundary: platform/lifecycle

SYSTEM = "platform"
NODE = "platform/lifecycle"
OWNS = "platform startup/shutdown/readiness semantics"
MUST_NOT_OWN = "service/process lifecycle"
AUTHORITY = "platform_lifecycle"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
