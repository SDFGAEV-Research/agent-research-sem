# vNext Boundary: environment/resolution

SYSTEM = "environment"
NODE = "environment/resolution"
OWNS = "resolve logical environment requirements to concrete instance plan"
MUST_NOT_OWN = "process lifecycle"
AUTHORITY = "environment_resolution"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
