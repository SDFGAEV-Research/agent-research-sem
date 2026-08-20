from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..api import BudgetPolicyConfig, QueryBudget


@dataclass(slots=True)
class FineGrainedBudgetPolicy:
    """Port of the legacy Deluxe allocation policy over current read contracts."""

    config: BudgetPolicyConfig = field(default_factory=BudgetPolicyConfig)
    node_cost_ema: dict[str, float] = field(default_factory=dict)
    capability_cost_ema: dict[str, float] = field(default_factory=dict)

    def allocate(
        self,
        *,
        requested_nodes: int,
        requested_records: int,
        node_count: int,
        unresolved_rate: float = 0.0,
        cost_pressure: float = 0.0,
    ) -> QueryBudget:
        if node_count < 0 or unresolved_rate < 0.0 or cost_pressure < 0.0:
            raise ValueError("Deluxe budget allocation inputs cannot be negative")
        cfg = self.config
        nodes = max(cfg.min_nodes, min(cfg.max_nodes, requested_nodes or cfg.default_nodes, max(1, node_count)))
        records = max(cfg.min_records, min(cfg.max_records, requested_records or cfg.default_records))
        explore = min(
            nodes - 1,
            max(0, int(round(nodes * cfg.exploration_fraction * min(1.0, unresolved_rate * 2.0)))),
        )
        if cost_pressure > 0.5 and nodes > cfg.min_nodes:
            nodes = max(cfg.min_nodes, nodes - 1)
            explore = min(explore, nodes - 1)
        token_budget = max(256, int(cfg.default_tokens * (1.0 - 0.35 * min(1.0, cost_pressure))))
        return QueryBudget(nodes, records, token_budget, explore)

    def node_record_cap(self, node_id: str, *, probation: bool = False) -> int:
        if not node_id.strip():
            raise ValueError("Deluxe node id must be non-empty")
        cap = self.config.per_node_record_cap
        return max(1, int(round(cap * self.config.probation_budget_scale))) if probation else cap

    def observe_node_cost(self, node_id: str, cost: float, *, alpha: float = 0.2) -> None:
        self._observe(self.node_cost_ema, node_id, cost, alpha)

    def observe_capability_cost(self, capability_id: str, cost: float, *, alpha: float = 0.2) -> None:
        self._observe(self.capability_cost_ema, capability_id, cost, alpha)

    @staticmethod
    def _observe(target: dict[str, float], key: str, value: float, alpha: float) -> None:
        if not key.strip() or value < 0.0 or not 0.0 < alpha <= 1.0:
            raise ValueError("Deluxe cost observation is invalid")
        previous = target.get(key, value)
        target[key] = (1.0 - alpha) * previous + alpha * value

    def snapshot(self) -> Mapping[str, object]:
        return {
            "node_cost_ema": dict(sorted(self.node_cost_ema.items())),
            "capability_cost_ema": dict(sorted(self.capability_cost_ema.items())),
        }


__all__ = ["FineGrainedBudgetPolicy"]
