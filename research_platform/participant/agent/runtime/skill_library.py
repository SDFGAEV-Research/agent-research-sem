from __future__ import annotations

from dataclasses import replace
import re
from typing import Mapping

from research_platform.platform.kernel import ExecutionContext

from ..api.cognition import (
    AgentActionSequence,
    AgentGoal,
    AgentObservation,
    AgentSkillRecord,
    AgentStepReceipt,
    JsonObject,
)
from ..api.cognition_ports import AgentSkillLibraryPort


def _tokens(value: str) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9_:-]+", value.lower()) if len(item) > 1}


class InMemorySkillLibrary(AgentSkillLibraryPort):
    """Structured recipe retrieval; it stores actions, never executable code."""

    def __init__(self, records: tuple[AgentSkillRecord, ...] = (), *, max_records: int = 512) -> None:
        if max_records < 1:
            raise ValueError("skill library max_records must be positive")
        self._records = list(records)
        self._max_records = max_records

    def register(self, record: AgentSkillRecord) -> None:
        self._records = [existing for existing in self._records if existing.skill_id != record.skill_id]
        self._records.append(record)
        self._records = self._records[-self._max_records :]

    def search(self, goal: AgentGoal, observation: AgentObservation, *, limit: int, context: ExecutionContext) -> tuple[AgentSkillRecord, ...]:
        del context
        if limit < 1:
            raise ValueError("skill search limit must be positive")
        query = _tokens(goal.objective + " " + " ".join(str(key) for key in observation.state))
        scored: list[tuple[float, AgentSkillRecord]] = []
        for record in self._records:
            overlap = len(query & _tokens(record.summary + " " + " ".join(record.tags)))
            reliability = (record.success_count + 1) / (record.success_count + record.failure_count + 2)
            if overlap or record.skill_id in query:
                scored.append((overlap * 10 + reliability, record))
        scored.sort(key=lambda item: (-item[0], item[1].skill_id, item[1].version))
        return tuple(record for _, record in scored[:limit])

    def record(self, sequence: AgentActionSequence, receipts: tuple[AgentStepReceipt, ...], *, success: bool, context: ExecutionContext) -> None:
        del context
        if not receipts:
            return
        existing = next((record for record in self._records if record.skill_id == sequence.skill_id), None)
        recipe = tuple((step.action_type, dict(step.payload)) for step in sequence.steps)
        if existing is None:
            self.register(AgentSkillRecord(
                skill_id=sequence.skill_id, version="1", summary=f"learned sequence for {sequence.skill_id}",
                tags=("learned",), source_refs=("agent-cognition",), recipe=recipe,
                success_count=1 if success else 0, failure_count=0 if success else 1,
            ))
            return
        self.register(replace(
            existing,
            recipe=recipe,
            success_count=existing.success_count + (1 if success else 0),
            failure_count=existing.failure_count + (0 if success else 1),
        ))

    def snapshot(self) -> tuple[AgentSkillRecord, ...]:
        return tuple(self._records)

    def checkpoint_payload(self) -> JsonObject:
        return {
            "schema_version": "agent-skill-library.v1",
            "records": [
                {
                    "skill_id": record.skill_id, "version": record.version, "summary": record.summary,
                    "tags": list(record.tags), "source_refs": list(record.source_refs),
                    "recipe": [{"action_type": action_type, "payload": dict(payload)} for action_type, payload in record.recipe],
                    "success_count": record.success_count, "failure_count": record.failure_count,
                }
                for record in self._records
            ],
        }

    def restore(self, payload: Mapping[str, JsonObject | list[JsonObject] | str]) -> None:
        if payload.get("schema_version") != "agent-skill-library.v1" or not isinstance(payload.get("records"), list):
            raise ValueError("invalid agent skill library checkpoint")
        records: list[AgentSkillRecord] = []
        for row in payload["records"]:
            if not isinstance(row, Mapping) or not isinstance(row.get("recipe", []), list):
                raise ValueError("invalid skill library record")
            records.append(AgentSkillRecord(
                skill_id=str(row["skill_id"]), version=str(row["version"]), summary=str(row["summary"]),
                tags=tuple(str(value) for value in row.get("tags", [])),
                source_refs=tuple(str(value) for value in row.get("source_refs", [])),
                recipe=tuple((str(item["action_type"]), dict(item["payload"])) for item in row["recipe"] if isinstance(item, Mapping)),
                success_count=int(row.get("success_count", 0)), failure_count=int(row.get("failure_count", 0)),
            ))
        self._records = records[-self._max_records :]


__all__ = ["InMemorySkillLibrary"]
