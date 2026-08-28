"""Compile Mindcraft task JSON into the platform's typed Minecraft fixture manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.platform.kernel import canonical_digest
from research_platform.environment.minecraft.runtime import MinecraftTaskSpec


def _rows(value: object) -> list[dict[str, object]]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict) and isinstance(value.get("tasks"), list):
        rows = value["tasks"]
    else:
        raise ValueError("input must be a task list or an object with a tasks list")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("every task row must be an object")
    return rows  # type: ignore[return-value]


def _construction_cells(raw: object) -> list[dict[str, object]]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if not isinstance(raw, dict) or not isinstance(raw.get("levels"), list):
        return []
    cells: list[dict[str, object]] = []
    for level in raw["levels"]:
        if not isinstance(level, dict) or not isinstance(level.get("coordinates"), list) or not isinstance(level.get("placement"), list):
            raise ValueError("construction blueprint level shape is invalid")
        origin = level["coordinates"]
        for row_index, row in enumerate(level["placement"]):
            if not isinstance(row, list):
                raise ValueError("construction blueprint placement row is invalid")
            for column_index, block in enumerate(row):
                if not isinstance(block, str):
                    raise ValueError("construction blueprint block must be text")
                cells.append({"position": {"x": origin[0] + column_index, "y": origin[1], "z": origin[2] + row_index}, "block": block})
    return cells


def _normalize_task(task_id: str, value: dict[str, object], source_ref: str) -> dict[str, object]:
    row = dict(value)
    row["task_id"] = f"{source_ref}::{task_id}"
    row["source_ref"] = source_ref
    goal = row.get("goal", task_id)
    if isinstance(goal, dict):
        goal = next((str(item) for item in goal.values() if str(item).strip()), task_id)
    row["goal"] = str(goal)
    row["agent_count"] = int(row.get("agent_count", 1))
    row["timeout"] = int(row.get("timeout", 300))
    inventory = row.get("initial_inventory", {})
    if isinstance(inventory, dict) and any(isinstance(item, dict) for item in inventory.values()):
        aggregate: dict[str, int] = {}
        for agent_inventory in inventory.values():
            if not isinstance(agent_inventory, dict):
                continue
            for item, count in agent_inventory.items():
                aggregate[str(item)] = aggregate.get(str(item), 0) + int(count)
        row["initial_inventory"] = aggregate
    if isinstance(row.get("target"), dict):
        targets = row["target"]
        first_item, first_count = next(iter(targets.items()))
        row["target"] = str(first_item)
        row["number_of_target"] = int(first_count)
    blocked = row.get("blocked_actions", [])
    if isinstance(blocked, dict):
        row["blocked_actions"] = [f"agent_{agent}:{action}" for agent, actions in blocked.items() if isinstance(actions, list) for action in actions]
    if "blueprint" in row:
        row["blueprint"] = _construction_cells(row["blueprint"])
    if row.get("human_count", 0) or "/human_ai/" in source_ref:
        row["human_count"] = int(row.get("human_count", 1)) or 1
    return row


def _iter_sources(source: Path):
    if source.is_file() and source.suffix == ".zip":
        with zipfile.ZipFile(source) as archive:
            for name in sorted(archive.namelist()):
                if "/tasks/" not in name or not name.endswith(".json"):
                    continue
                yield name, json.loads(archive.read(name).decode("utf-8"))
        return
    files = (source.rglob("*.json") if source.is_dir() else (source,))
    for path in sorted(files):
        yield str(path), json.loads(path.read_text(encoding="utf-8"))


def compile_manifest(source: Path) -> dict[str, object]:
    normalized: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    for source_ref, raw in _iter_sources(source):
        if isinstance(raw, dict) and isinstance(raw.get("tasks"), list):
            rows = [(str(index), row) for index, row in enumerate(raw["tasks"]) if isinstance(row, dict)]
        elif isinstance(raw, dict):
            rows = [(str(task_id), row) for task_id, row in raw.items() if isinstance(row, dict) and "type" in row]
        else:
            rows = [(str(index), row) for index, row in enumerate(_rows(raw))]
        for task_id, row in rows:
            if str(row.get("type")) == "construction" and not row.get("blueprint"):
                skipped.append({"source_ref": source_ref, "task_id": task_id, "reason": "construction template has no blueprint"})
                continue
            normalized.append(_normalize_task(task_id, row, source_ref))
    tasks = tuple(MinecraftTaskSpec.from_mapping(row) for row in normalized)
    ids = [task.task_id for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("task_id values must be unique")
    payload = {"schema_version": "minecraft-task-fixture.v1", "source": str(source), "tasks": [task.as_payload() for task in tasks], "skipped": skipped}
    return {**payload, "manifest_digest": canonical_digest(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = compile_manifest(args.input)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "task_count": len(manifest["tasks"]), "manifest_digest": manifest["manifest_digest"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
