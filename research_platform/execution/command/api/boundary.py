# vNext Boundary: execution/command

SYSTEM = "execution"
NODE = "execution/command"
OWNS = "typed execution commands and command routing"
MUST_NOT_OWN = "human UI and provider-specific control"
AUTHORITY = "command_intent"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="execution",
    node="execution/command",
    package_prefix='research_platform.execution.command',
    authority_id="command_intent",
    owns="typed execution commands and command routing",
    must_not_own="human UI and provider-specific control",
    api_module='research_platform.execution.command.api',
    runtime_module='research_platform.execution.command.runtime',
    provider_module='research_platform.execution.command.providers',
    composition_module='research_platform.execution.command.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
