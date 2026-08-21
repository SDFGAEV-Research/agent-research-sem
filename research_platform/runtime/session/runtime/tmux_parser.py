from __future__ import annotations

from research_platform.runtime.session.api import PersistentSessionSnapshot


class TmuxSnapshotParseError(RuntimeError):
    pass


def parse_tmux_snapshot(session_name: str, stdout: str) -> PersistentSessionSnapshot:
    line = stdout.rstrip("\n")
    # tmux 3.0a emits the format escape ``\\t`` literally, while newer
    # versions may emit an actual tab. Accept only these two exact encodings;
    # do not fall back to whitespace splitting because command/cwd identity is
    # part of the frozen session proof.
    separator = "\t" if "\t" in line else "\\t"
    parts = line.split(separator, 4)
    if len(parts) != 5 or parts[0] != session_name:
        raise TmuxSnapshotParseError("tmux returned malformed or non-exact session snapshot")
    try:
        controller_pid = int(parts[1])
    except ValueError as exc:
        raise TmuxSnapshotParseError("tmux returned invalid controller PID") from exc
    return PersistentSessionSnapshot(
        session_name=session_name,
        exists=True,
        controller_pid=controller_pid,
        controller_dead=parts[2] == "1",
        start_command=parts[3],
        current_path=parts[4],
    )


__all__ = ["TmuxSnapshotParseError", "parse_tmux_snapshot"]
