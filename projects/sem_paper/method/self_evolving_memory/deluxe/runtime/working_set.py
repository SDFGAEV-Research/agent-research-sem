from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ..api import (
    CapabilityCard,
    WorkingSet,
    WorkingSetEntry,
    WorkingSetPolicyConfig,
)
from .capabilities import CapabilityRegistry


@dataclass(slots=True)
class ArchitectureOpenWorkingSetPolicy:
    """Select from capabilities derived from the current architecture."""

    registry: CapabilityRegistry
    config: WorkingSetPolicyConfig = field(default_factory=WorkingSetPolicyConfig)
    provider_utility: dict[str, float] = field(default_factory=dict)
    provider_reliability: dict[str, float] = field(default_factory=dict)
    provider_cost: dict[str, float] = field(default_factory=dict)

    def select(
        self,
        ranked_capabilities: Sequence[tuple[float, CapabilityCard]],
        *,
        budget_nodes: int,
        exploration_slots: int = 0,
    ) -> WorkingSet:
        if budget_nodes <= 0 or exploration_slots < 0 or exploration_slots > budget_nodes:
            raise ValueError("Deluxe working-set selection budget is invalid")
        scored: list[tuple[float, CapabilityCard]] = []
        cfg = self.config
        for relevance, card in ranked_capabilities:
            utility = self.provider_utility.get(card.provider_node_id, 0.0)
            reliability = self.provider_reliability.get(card.provider_node_id, 0.5)
            cost = self.provider_cost.get(card.provider_node_id, 0.0)
            score = (
                cfg.relevance_weight * relevance
                + cfg.utility_weight * utility
                + cfg.reliability_weight * reliability
                - cfg.cost_weight * cost
            )
            scored.append((score, card))
        scored.sort(key=lambda row: (-row[0], row[1].capability_id))
        exploit_count = max(1, budget_nodes - exploration_slots)
        chosen = [
            WorkingSetEntry(card.capability_id, card.provider_node_id, score, False)
            for score, card in scored[:exploit_count]
        ]
        if exploration_slots:
            chosen_ids = {entry.capability_id for entry in chosen}
            unexplored = [
                (score, card)
                for score, card in scored
                if card.capability_id not in chosen_ids
                and self.registry.lifecycle[card.capability_id].selected_queries == 0
            ]
            chosen.extend(
                WorkingSetEntry(card.capability_id, card.provider_node_id, score + cfg.exploration_bonus, True)
                for score, card in unexplored[:exploration_slots]
            )
        return WorkingSet(tuple(chosen[:budget_nodes]), budget_nodes)

    def observe(self, node_id: str, *, utility: float, success: bool, cost: float, alpha: float = 0.2) -> None:
        if not node_id.strip() or cost < 0.0 or not 0.0 < alpha <= 1.0:
            raise ValueError("Deluxe working-set observation is invalid")
        self.provider_utility[node_id] = (1.0 - alpha) * self.provider_utility.get(node_id, utility) + alpha * utility
        self.provider_reliability[node_id] = (
            (1.0 - alpha) * self.provider_reliability.get(node_id, 1.0 if success else 0.0)
            + alpha * (1.0 if success else 0.0)
        )
        self.provider_cost[node_id] = (1.0 - alpha) * self.provider_cost.get(node_id, cost) + alpha * cost

    def snapshot(self) -> Mapping[str, object]:
        return {
            "provider_utility": dict(sorted(self.provider_utility.items())),
            "provider_reliability": dict(sorted(self.provider_reliability.items())),
            "provider_cost": dict(sorted(self.provider_cost.items())),
        }


__all__ = ["ArchitectureOpenWorkingSetPolicy"]
