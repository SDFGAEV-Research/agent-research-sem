# vNext Boundary: operator/command/intent

SYSTEM = "operator"
NODE = "operator/command/intent"
OWNS = "human command intents and authorization context"
MUST_NOT_OWN = "command execution side effects"
AUTHORITY = "operator_command_intent"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="operator",
    node="operator/command/intent",
    package_prefix='research_platform.operator.command.intent',
    authority_id="operator_command_intent",
    owns="human command intents and authorization context",
    must_not_own="command execution side effects",
    api_module='research_platform.operator.command.intent.api',
    runtime_module='research_platform.operator.command.intent.runtime',
    provider_module='research_platform.operator.command.intent.providers',
    composition_module='research_platform.operator.command.intent.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
