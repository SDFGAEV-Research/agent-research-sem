# vNext Boundary: execution/command

SYSTEM = "execution"
NODE = "execution/command"
OWNS = "typed execution commands and command routing"
MUST_NOT_OWN = "human UI and provider-specific control"
AUTHORITY = "command_intent"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.
