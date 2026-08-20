# vNext Boundary: observability/tracing/storage

SYSTEM = "observability"
NODE = "observability/tracing/storage"
OWNS = "trace/span storage backends"
MUST_NOT_OWN = "trace identity semantics"
AUTHORITY = "trace_storage"
