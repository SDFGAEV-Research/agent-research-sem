from __future__ import annotations

from dataclasses import dataclass

from research_platform.governance.architecture.api.capability_composition import (
    BindingPlan,
    CapabilityOffer,
)

from .ports import LoggingSystemPort


@dataclass(frozen=True, slots=True)
class LoggingSystemBinding:
    """Public logging port paired with immutable composition provenance."""

    logging: LoggingSystemPort
    plan: BindingPlan
    offer: CapabilityOffer


__all__ = ["LoggingSystemBinding"]
