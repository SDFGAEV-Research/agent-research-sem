# vNext Boundary: model/catalog/revision

SYSTEM = "model"
NODE = "model/catalog/revision"
OWNS = "versioned model revision identity"
MUST_NOT_OWN = "mutable serving state"
AUTHORITY = "model_revision"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="model",
    node="model/catalog/revision",
    package_prefix='research_platform.model.catalog.revision',
    authority_id="model_revision",
    owns="versioned model revision identity",
    must_not_own="mutable serving state",
    api_module='research_platform.model.catalog.revision.api',
    runtime_module='research_platform.model.catalog.revision.runtime',
    provider_module='research_platform.model.catalog.revision.providers',
    composition_module='research_platform.model.catalog.revision.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
