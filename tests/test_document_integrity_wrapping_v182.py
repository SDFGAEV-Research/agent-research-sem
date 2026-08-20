from __future__ import annotations

import json

from research_platform.reliability.failure.api import exception_correlation_refs
from research_platform.platform.kernel.durability import ChecksummedDocumentFailureCode
from research_platform.execution.runtime.manager.heartbeat_codec import (
    ServiceHeartbeatCodec,
    ServiceHeartbeatIntegrityError,
)


def test_domain_wrapper_keeps_machine_code_without_copying_lower_message() -> None:
    raw = json.dumps({"secret": "TOP-SECRET"}).encode()
    try:
        ServiceHeartbeatCodec().decode(raw)
    except ServiceHeartbeatIntegrityError as exc:
        assert exc.document_failure_code is ChecksummedDocumentFailureCode.SCHEMA_MISSING
        assert str(exc) == "service heartbeat document integrity failure"
        assert "TOP-SECRET" not in str(exc)
        assert exception_correlation_refs(exc) == ("document-integrity:schema_missing",)
    else:
        raise AssertionError("expected ServiceHeartbeatIntegrityError")
