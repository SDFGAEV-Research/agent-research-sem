from __future__ import annotations

from research_platform.data.fact.api import DurableFact, FactCriticality, UnknownRequiredFact


class FactDecoderRegistry:
    def __init__(self, decoders=()) -> None:
        self._decoders = {(x.fact_type, x.schema_version): x for x in decoders}

    def decode(self, fact: DurableFact):
        decoder = self._decoders.get((fact.fact_type, fact.schema_version))
        if decoder is None:
            if fact.criticality is FactCriticality.IGNORABLE:
                return None
            raise UnknownRequiredFact(
                f"unknown required fact: {fact.fact_type}@{fact.schema_version}"
            )
        return decoder.decode(fact)


__all__ = ["FactDecoderRegistry"]
