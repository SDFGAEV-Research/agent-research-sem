# vNext Boundary: execution/admission

SYSTEM = "execution"
NODE = "execution/admission"
OWNS = "execution admission constraints and decisions"
MUST_NOT_OWN = "model/environment truth"
AUTHORITY = "admission_decision"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
