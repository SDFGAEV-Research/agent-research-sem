# vNext Boundary: observability/tracing/context

SYSTEM = "observability"
NODE = "observability/tracing/context"
OWNS = "trace/span context creation and attachment"
MUST_NOT_OWN = "business operation state"
AUTHORITY = "trace_context"
