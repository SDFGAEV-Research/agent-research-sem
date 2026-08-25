# vNext Boundary: scientific/prompt

SYSTEM = "scientific"
NODE = "scientific/prompt"
OWNS = "prompt identities, generation, promotion and policy"
MUST_NOT_OWN = "model serving and process control"
AUTHORITY = "prompt_authority"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="scientific",
    node="scientific/prompt",
    package_prefix='research_platform.scientific.prompt',
    authority_id="prompt_authority",
    owns="prompt identities, generation, promotion and policy",
    must_not_own="model serving and process control",
    api_module='research_platform.scientific.prompt.api',
    runtime_module='research_platform.scientific.prompt.runtime',
    provider_module='research_platform.scientific.prompt.providers',
    composition_module='research_platform.scientific.prompt.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
