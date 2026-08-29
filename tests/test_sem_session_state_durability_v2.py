from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile

import pytest

from research_platform.platform.kernel import ExecutionContext
from projects.sem_paper.composition.session_state import (
    DurableSEMSessionStateError,
    DurableSEMSessionStateFactory,
    FileSEMSessionStateStore,
)
from projects.sem_paper.composition.session_state_storage import _decode, _document


def _primary(root: Path) -> Path:
    return next(root.glob("*.json"))


def test_cas_binds_revision_even_when_payload_digest_is_unchanged() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        DurableSEMSessionStateFactory(root).create("session-revision-cas")
        first = FileSEMSessionStateStore(_primary(root))
        second = FileSEMSessionStateStore(_primary(root))
        snapshot = first.read()
        stale = second.read()
        first.write(snapshot)
        with pytest.raises(DurableSEMSessionStateError):
            second.write(stale)


def test_parallel_store_writers_never_both_commit_one_observed_revision() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        DurableSEMSessionStateFactory(root).create("session-parallel-cas")
        left = FileSEMSessionStateStore(_primary(root))
        right = FileSEMSessionStateStore(_primary(root))
        left_snapshot = left.read()
        right_snapshot = right.read()

        def commit(pair) -> str:
            store, snapshot = pair
            try:
                store.write(snapshot)
            except DurableSEMSessionStateError:
                return "rejected"
            return "committed"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(
                executor.map(commit, ((left, left_snapshot), (right, right_snapshot)))
            )
        assert sorted(outcomes) == ["committed", "rejected"]


def test_durable_decoder_rejects_coercible_boolean_and_tampered_evidence() -> None:
    with tempfile.TemporaryDirectory() as directory:
        factory = DurableSEMSessionStateFactory(Path(directory))
        session = factory.create("session-strict-codec")
        context = ExecutionContext("run", "trace", "span", task_id="task")
        session.ingest({"kind": "WORLD_OBSERVATION", "entity": "tree"}, context)
        document = _document(session.snapshot_state())

        bad_bool = dict(document)
        bad_bool["lineage"] = dict(document["lineage"])
        bad_bool["lineage"]["mutation_tail"] = [
            dict(row) for row in document["lineage"]["mutation_tail"]
        ]
        bad_bool["lineage"]["mutation_tail"][0]["before_closed"] = "false"
        with pytest.raises(DurableSEMSessionStateError):
            _decode(bad_bool)

        bad_evidence = dict(document)
        bad_evidence["evidence"] = dict(document["evidence"])
        bad_evidence["evidence"]["rows"] = [
            dict(row) for row in document["evidence"]["rows"]
        ]
        bad_evidence["evidence"]["rows"][0]["payload"] = {"tampered": True}
        with pytest.raises(DurableSEMSessionStateError):
            _decode(bad_evidence)

        extra = dict(document)
        extra["projection"] = {}
        with pytest.raises(DurableSEMSessionStateError):
            _decode(extra)


def test_durable_envelope_rejects_coercible_revision_and_extra_fields() -> None:
    from projects.sem_paper.composition.session_state_storage import (
        _decode_envelope,
        _envelope,
    )

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        session = DurableSEMSessionStateFactory(root).create("session-envelope-codec")
        envelope, _, _ = _envelope(session.snapshot_state(), 1)
        source = root / "state.json"

        bool_revision = dict(envelope)
        bool_revision["revision"] = True
        with pytest.raises(DurableSEMSessionStateError):
            _decode_envelope(bool_revision, source=source)

        extra = dict(envelope)
        extra["projection"] = {}
        with pytest.raises(DurableSEMSessionStateError):
            _decode_envelope(extra, source=source)
