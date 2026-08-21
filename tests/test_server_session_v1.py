from __future__ import annotations

from types import SimpleNamespace

from scripts.server_session import _remote_tmux


def _args(**overrides):
    values = {
        "tmux": "tmux",
        "session": "research-platform-shell",
        "cwd": "/data/research-platform/agent-research-platform-system",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_server_session_uses_a_pane_target_for_status() -> None:
    status = _remote_tmux(_args(), action="status")
    assert "=research-platform-shell:0.0" in status
    assert "display-message" in status


def test_server_session_quotes_operator_paths_and_rejects_unsafe_session() -> None:
    ensure = _remote_tmux(_args(cwd="/data/research platform"), action="ensure")
    assert "'/data/research platform'" in ensure
    try:
        _remote_tmux(_args(session="bad;rm"), action="ensure")
    except ValueError as exc:
        assert "session" in str(exc)
    else:
        raise AssertionError("unsafe session names must be rejected")
