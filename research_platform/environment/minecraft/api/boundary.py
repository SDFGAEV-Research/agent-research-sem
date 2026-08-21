# vNext Boundary: environment/minecraft

SYSTEM = "environment"
NODE = "environment/minecraft"
OWNS = "Minecraft environment semantics, world-cut contracts and replaceable bridge adapters"
MUST_NOT_OWN = (
    "generic environment catalog, process/server supervision, model serving, "
    "paper method semantics or telemetry storage"
)
AUTHORITY = "minecraft_environment"
