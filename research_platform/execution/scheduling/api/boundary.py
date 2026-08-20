# vNext Boundary: execution/scheduling

SYSTEM = "execution"
NODE = "execution/scheduling"
OWNS = "scheduling decisions and admission requests"
MUST_NOT_OWN = "live resource state"
AUTHORITY = "schedule_intent"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
