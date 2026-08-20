from __future__ import annotations

from dataclasses import dataclass

from research_platform.participant.capability.api import CapabilityResult
from research_platform.platform.kernel import OperationResult


class UnsafeEffectfulCapability(RuntimeError):
    pass


class UnresolvedCapabilityEffect(RuntimeError):
    pass


class CapabilityEffectIdentityConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CapabilityEffectExecution:
    result: CapabilityResult
    operation_results: tuple[OperationResult[object], ...]
    replayed_from_intent: bool = False


__all__ = [
    "CapabilityEffectExecution",
    "CapabilityEffectIdentityConflict",
    "UnresolvedCapabilityEffect",
    "UnsafeEffectfulCapability",
]
