# vNext Boundary: platform/configuration

SYSTEM = "platform"
NODE = "platform/configuration"
OWNS = "platform configuration sources and frozen configuration snapshots"
MUST_NOT_OWN = "domain configuration semantics"
AUTHORITY = "platform_configuration"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
