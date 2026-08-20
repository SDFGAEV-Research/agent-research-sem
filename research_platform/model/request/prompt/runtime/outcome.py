from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptOutcomeLink:
    request_id: str
    prompt_digest: str
    task_id: str
    decision_cycle_id: str
    action_id: str | None
    verified_action_success: bool | None
    task_success: bool | None
    utility: float | None
    contract_repairs: int


@dataclass(frozen=True, slots=True)
class PromptOutcomeSummary:
    prompt_digest: str
    observations: int
    verified_action_success_rate: float | None
    task_success_rate: float | None
    mean_utility: float | None
    effect_claim_authorized: bool = False


def summarize_outcomes(prompt_digest: str, links: tuple[PromptOutcomeLink, ...]) -> PromptOutcomeSummary:
    rows=[x for x in links if x.prompt_digest==prompt_digest]
    action=[x.verified_action_success for x in rows if x.verified_action_success is not None]
    task=[x.task_success for x in rows if x.task_success is not None]
    util=[x.utility for x in rows if x.utility is not None]
    return PromptOutcomeSummary(prompt_digest,len(rows),sum(action)/len(action) if action else None,sum(task)/len(task) if task else None,sum(util)/len(util) if util else None,False)
