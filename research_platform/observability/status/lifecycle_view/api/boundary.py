# vNext Boundary: observability/status/lifecycle_view

SYSTEM = "observability"
NODE = "observability/status/lifecycle_view"
OWNS = "read-only lifecycle status views"
MUST_NOT_OWN = "lifecycle state authority"
AUTHORITY = "lifecycle_projection"
