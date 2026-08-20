from __future__ import annotations

from research_platform.runtime.service.runtime.start_intent_ports import ServiceStartIntentStorePort
from research_platform.runtime.service.runtime.start_journal import ServiceStartJournal
from research_platform.runtime.service.runtime.state_ports import ServiceStateStorePort
from research_platform.runtime.service.runtime.supervision_contracts import ServiceProcessAdapter
from research_platform.runtime.service.runtime.supervisor import ExactServiceSupervisor


def build_service_supervisor(
    state: ServiceStateStorePort,
    intents: ServiceStartIntentStorePort,
    adapter: ServiceProcessAdapter,
) -> ExactServiceSupervisor:
    """Compose one exact service supervisor from explicit state, intent and process seams."""

    return ExactServiceSupervisor(
        state,
        adapter,
        start_journal=ServiceStartJournal(intents),
    )


__all__ = ["build_service_supervisor"]
