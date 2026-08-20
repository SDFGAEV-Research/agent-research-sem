# vNext Boundary: portfolio/workspace

SYSTEM = "portfolio"
NODE = "portfolio/workspace"
OWNS = "workspace metadata and lifecycle"
MUST_NOT_OWN = "generic scope tree authority"
AUTHORITY = "workspace_metadata"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
