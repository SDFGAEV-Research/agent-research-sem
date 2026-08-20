from __future__ import annotations

from research_platform.runtime.service.api import ServiceProcessIdentity
from dataclasses import asdict, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from research_platform.runtime.service.runtime.state_storage import FileServiceStateStore
from research_platform.platform.kernel.durability import ChecksummedDocumentFailureCode
from research_platform.runtime.service.runtime import (
    ServiceExitClass,
    ServiceStateIntegrityError,
    ServiceSupervisorState,
)


class ServiceStateCodecV142Tests(unittest.TestCase):
    def _state(self) -> ServiceSupervisorState:
        return replace(
            ServiceSupervisorState.initial("model.planner", "a" * 64),
            attempt=3,
            process=ServiceProcessIdentity(42, "pid:42:start:7", 42),
            last_exit_class=ServiceExitClass.SOFTWARE,
        )

    def test_new_document_is_versioned_checksummed_and_round_trips(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "service.json"
            store = FileServiceStateStore(path)
            state = self._state()
            store.write(state)
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["schema"], "service-supervisor-state.v2")
            self.assertEqual(len(document["payload_sha256"]), 64)
            self.assertEqual(store.read(), state)

    def test_payload_tampering_is_detected_before_state_construction(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "service.json"
            store = FileServiceStateStore(path)
            store.write(self._state())
            document = json.loads(path.read_text(encoding="utf-8"))
            document["payload"]["attempt"] = 999
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ServiceStateIntegrityError) as caught:
                store.read()
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.CHECKSUM_MISMATCH)

    def test_unknown_future_schema_fails_closed(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "service.json"
            path.write_text(json.dumps({"schema": "service-supervisor-state.v999"}), encoding="utf-8")
            with self.assertRaises(ServiceStateIntegrityError) as caught:
                FileServiceStateStore(path).read()
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.UNSUPPORTED_SCHEMA)

    def test_unenveloped_state_is_rejected(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "service.json"
            state = self._state()
            payload = asdict(state)
            payload["phase"] = state.phase.value
            payload["last_exit_class"] = int(state.last_exit_class)
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ServiceStateIntegrityError) as caught:
                FileServiceStateStore(path).read()
            self.assertIs(caught.exception.document_failure_code, ChecksummedDocumentFailureCode.SCHEMA_MISSING)


if __name__ == "__main__":
    unittest.main()
