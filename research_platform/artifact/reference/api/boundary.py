# vNext Boundary: artifact/reference

SYSTEM = "artifact"
NODE = "artifact/reference"
OWNS = "references, aliases and cross-system artifact pointers"
MUST_NOT_OWN = "content mutation"
AUTHORITY = "artifact_reference"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
