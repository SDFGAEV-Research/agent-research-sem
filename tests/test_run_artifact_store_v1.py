from __future__ import annotations
from tests._concurrency_support import run_artifact_store

import json

import pytest

from research_platform.experimentation.run.api import RunArtifactKind
from research_platform.experimentation.run.runtime import DirectoryRunArtifactStore


def test_directory_run_artifact_store_publishes_atomic_json(tmp_path):
    store = run_artifact_store(tmp_path / "run")

    path = store.publish_json(
        "nested/result.json",
        {"status": "ok", "value": 3},
        kind=RunArtifactKind.RESULT,
    )

    assert json.loads((tmp_path / "run" / "nested" / "result.json").read_text()) == {
        "status": "ok",
        "value": 3,
    }
    assert path.endswith("nested\\result.json") or path.endswith("nested/result.json")


def test_directory_run_artifact_store_rejects_escape(tmp_path):
    store = run_artifact_store(tmp_path / "run")
    with pytest.raises(ValueError):
        store.path("../outside.json", kind=RunArtifactKind.RESULT)


def test_directory_run_artifact_store_publishes_text_atomically(tmp_path):
    store = run_artifact_store(tmp_path / "run")
    path = store.publish_text(
        "evidence/j_eval.jsonl",
        '{"eval_id":"one"}\n',
        kind=RunArtifactKind.EVIDENCE,
    )
    assert (tmp_path / "run" / "evidence" / "j_eval.jsonl").read_text() == '{"eval_id":"one"}\n'
    assert path.endswith("j_eval.jsonl")
