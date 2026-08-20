# vNext Boundary: resource/catalog

SYSTEM = "resource"
NODE = "resource/catalog"
OWNS = "resource identities/types and catalog metadata"
MUST_NOT_OWN = "live capacity"
AUTHORITY = "resource_catalog"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
