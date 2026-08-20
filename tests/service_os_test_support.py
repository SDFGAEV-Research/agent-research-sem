from __future__ import annotations

from research_platform.platform.composition.service_supervisor import build_service_supervisor
from research_platform.runtime.service.runtime.start_intent_store import DirectoryServiceStartIntentStore


def make_service_supervisor(state, adapter):
    """Test-only deterministic directory wiring; production code must inject both stores explicitly."""
    from pathlib import Path
    state_path = Path(state.reference())
    intent_root = state_path.with_name(state_path.name + ".start-intents")
    return build_service_supervisor(state, DirectoryServiceStartIntentStore(intent_root), adapter)
