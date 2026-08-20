from __future__ import annotations

from dataclasses import dataclass

from research_platform.reliability.effect.api import EffectIntent
from research_platform.environment.runtime.api import ActionRequest, ActionResult
from research_platform.platform.kernel import OperationResult


@dataclass(frozen=True, slots=True)
class SafeActionExecution:
    result: ActionResult
    operation_results: tuple[OperationResult[object], ...]
    replayed_from_intent: bool = False


@dataclass(frozen=True, slots=True)
class ActionSafetyPermit:
    decision_cycle_id: str
    environment_component_digest: str
    journal_durability: str | None
    request_digest: str
    intent_id: str | None


@dataclass(frozen=True, slots=True)
class PreparedSafeAction:
    """Exact action authorization frozen before crossing the side-effect boundary."""

    request: ActionRequest
    intent: EffectIntent | None
    permit: ActionSafetyPermit
    operation_results: tuple[OperationResult[object], ...] = ()


__all__ = ["ActionSafetyPermit", "PreparedSafeAction", "SafeActionExecution"]
