from __future__ import annotations

import json
from pathlib import Path

from scripts.sem_paper_non_minecraft_application import (
    NonMinecraftExperimentInputs,
    run,
)


def test_reference_closed_world_runs_real_sem_stack_without_scientific_claim(tmp_path) -> None:
    tasks_path = (
        Path(__file__).resolve().parents[1]
        / "projects"
        / "sem_paper"
        / "experiments"
        / "manifests"
        / "closed_world_reference_v1.json"
    )
    output = tmp_path / "run"

    status = run(
        NonMinecraftExperimentInputs(
            run_id="closed-world-e2e",
            output_dir=output,
            tasks_path=tasks_path,
            task_ids=(),
            repetitions=1,
        )
    )

    assert status == 0
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    observations = json.loads(
        (output / "study" / "observations.json").read_text(encoding="utf-8")
    )
    assert result["status"] == "completed"
    assert result["scientific_claim"] is False
    assert result["observation_count"] == 2
    assert {row["assignment"]["variant_id"] for row in observations} == {
        "control",
        "candidate",
    }
    assert all(dict(row["metrics"])["success_rate"] == 1.0 for row in observations)
    assert all(dict(row["metrics"])["memory_queries_total"] > 0 for row in observations)
    assert (output / "method_observations" / "control_rep_0.jsonl").stat().st_size > 0
    assert (output / "method_observations" / "candidate_rep_0.jsonl").stat().st_size > 0
