# vNext Boundary: artifact/retention

SYSTEM = "artifact"
NODE = "artifact/retention"
OWNS = "retention, pinning and garbage-collection policy"
MUST_NOT_OWN = "business state semantics"
AUTHORITY = "artifact_retention"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
