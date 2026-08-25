from __future__ import annotations

from research_platform.platform.kernel import canonical_digest


from research_platform.platform.kernel import JsonValue


def tmux_evidence_ref(kind: str, payload: JsonValue) -> str:
    return f"tmux-{kind}:" + canonical_digest(payload)


__all__ = ["tmux_evidence_ref"]
