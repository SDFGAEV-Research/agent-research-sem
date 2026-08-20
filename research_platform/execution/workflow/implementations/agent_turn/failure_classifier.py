from __future__ import annotations

from research_platform.reliability.failure.api import ClassifiedOperationFailure
from research_platform.platform.kernel import OperationRequest


class AgentTurnFailureClassifier:
    """Extension point for Agent/Capability taxonomy; currently delegates unknowns to core fallback."""

    def classify(self, request: OperationRequest[object], exc: BaseException) -> ClassifiedOperationFailure | None:
        del request, exc
        return None


__all__ = ["AgentTurnFailureClassifier"]
