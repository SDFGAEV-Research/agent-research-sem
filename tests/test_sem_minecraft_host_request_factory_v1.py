from __future__ import annotations

import pytest

from projects.sem_paper.composition import (
    SemPaperMinecraftBranchRequestFactory,
    SemPaperMinecraftHostInputs,
)
from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from research_platform.environment.minecraft.api import (
    MinecraftAgentSpec,
    MinecraftBridgeSpec,
    MinecraftEndpointSpec,
    MinecraftEnvironmentSpec,
    MinecraftRconEndpoint,
    MinecraftServerSpec,
    MinecraftWorldBranch,
)


def _branch() -> MinecraftWorldBranch:
    return MinecraftWorldBranch(
        branch_id="candidate-a",
        cut_id="cut-1",
        workdir="/srv/minecraft/branches/candidate-a",
        level_name="candidate-a-world",
        manifest_digest="a" * 64,
        cleanup_ref="cleanup:candidate-a",
    )


def _inputs(*, rcon: bool = True) -> SemPaperMinecraftHostInputs:
    return SemPaperMinecraftHostInputs(
        environment_template=MinecraftEnvironmentSpec(
            endpoint=MinecraftEndpointSpec("127.0.0.1", 25565),
            bridge=MinecraftBridgeSpec(("node", "bridge.js"), "/srv/minecraft/bridge"),
            agent=MinecraftAgentSpec(username="paper_bot", version="1.20.1"),
        ),
        server_template=MinecraftServerSpec(
            jar_path="/srv/minecraft/server/server.jar",
            workdir="/srv/minecraft/template",
            java_executable="/usr/bin/java",
            rcon_endpoint=MinecraftRconEndpoint(port=25575) if rcon else None,
        ),
        server_candidate_ports=(25566, 25567),
        rcon_candidate_ports=(25576, 25577) if rcon else (),
    )


def test_host_request_factory_builds_deterministic_server_and_rcon_allocations() -> None:
    request = SemPaperMinecraftBranchRequestFactory(_inputs()).build(
        role=BranchRole.CANDIDATE,
        candidate=object(),
        branch=_branch(),
    )

    assert request.endpoint_allocation.allocation_id == "sem-paper:candidate:candidate-a:server-endpoint"
    assert request.endpoint_allocation.candidate_ports == (25566, 25567)
    assert request.endpoint_allocation.holder_scope.scope_id == "candidate-a"
    assert request.rcon_endpoint_allocation is not None
    assert request.rcon_endpoint_allocation.candidate_ports == (25576, 25577)
    assert request.session_id.endswith(":environment-session")


def test_host_request_factory_rejects_rcon_configuration_without_candidates() -> None:
    with pytest.raises(ValueError, match="RCON.*candidates"):
        SemPaperMinecraftHostInputs(
            environment_template=_inputs().environment_template,
            server_template=_inputs().server_template,
            server_candidate_ports=(25566,),
        )


def test_host_request_factory_does_not_turn_control_candidate_into_a_runtime_request() -> None:
    factory = SemPaperMinecraftBranchRequestFactory(_inputs(rcon=False))
    with pytest.raises(ValueError, match="control"):
        factory.build(role=BranchRole.CONTROL, candidate=object(), branch=_branch())
