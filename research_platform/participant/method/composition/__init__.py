"""Default Participant/Method system wiring.

Concrete methods/projects should receive ``MethodCompositionPorts`` through their own
composition boundary rather than importing these defaults.
"""

from research_platform.participant.method.api import MethodCompositionPorts
from research_platform.participant.method.runtime import (
    DefaultMethodEndpointFactory,
    DefaultMethodObservationOutboxFactory,
)


def build_default_method_composition_ports() -> MethodCompositionPorts:
    return MethodCompositionPorts(
        endpoint_factory=DefaultMethodEndpointFactory(),
        observation_outbox_factory=DefaultMethodObservationOutboxFactory(),
    )


__all__ = ["build_default_method_composition_ports"]
