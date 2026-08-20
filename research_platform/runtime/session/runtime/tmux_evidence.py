from __future__ import annotations

from research_platform.platform.kernel import canonical_digest


def tmux_evidence_ref(kind: str, payload: object) -> str:
    return f"tmux-{kind}:" + canonical_digest(payload)


__all__ = ["tmux_evidence_ref"]
