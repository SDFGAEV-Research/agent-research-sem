from __future__ import annotations

from tests_support import FakeParticipantResolver, frozen_binding

from dataclasses import dataclass

from research_platform.participant.agent.api import AgentIdentity, AgentTurnRequest, AgentTurnResult
from research_platform.participant.capability.api import (
    CapabilityDescriptor,
    CapabilityProviderIdentity,
    CapabilityRequest,
    CapabilityResult,
)
from research_platform.platform.kernel import EffectClass, ExecutionContext


class EchoCapabilitySession:
    @property
    def capabilities(self):
        return (CapabilityDescriptor("echo", "1", "echo.req.v1", "echo.res.v1", EffectClass.PURE, True),)

    def invoke(self, request: CapabilityRequest):
        return CapabilityResult(request.capability_id, request.payload)

    def checkpoint(self): return b"{}"
    def restore(self, payload): return None
    def close(self): return None


class EchoProvider:
    identity = CapabilityProviderIdentity("echo-provider", "1", "1", "1", "cfg")
    def open_session(self, *, session_id: str, services: object): return EchoCapabilitySession()


class GenericAgent:
    identity = AgentIdentity("generic", "1", "1", "1", "cfg")
    def open_session(self, *, session_id: str, services: object): return object()


def test_agent_and_capability_registries_are_independent():
    agents = FakeParticipantResolver()
    providers = FakeParticipantResolver()
    agents.register("agent", "generic", GenericAgent)
    providers.register("capability_provider", "echo-provider", EchoProvider)
    assert agents.resolve(frozen_binding("agent", "agent", "generic")).endpoint.identity.agent_id == "generic"
    assert providers.resolve(frozen_binding("capability_provider", "capability_provider", "echo-provider")).endpoint.identity.provider_id == "echo-provider"


def test_capability_contract_is_environment_agnostic():
    ctx = ExecutionContext("run", "trace", "span")
    request = CapabilityRequest("echo", {"x": 1}, ctx, "slot-1")
    result = EchoCapabilitySession().invoke(request)
    assert result.payload == {"x": 1}
    assert EchoCapabilitySession().capabilities[0].effect_class is EffectClass.PURE


def test_agent_turn_contract_carries_no_concrete_substrate_type():
    ctx = ExecutionContext("run", "trace", "span")
    request = AgentTurnRequest("do something", ctx, {"input": 1})
    result = AgentTurnResult({"done": True}, "agent-g1")
    assert request.task == "do something"
    assert result.agent_generation == "agent-g1"
