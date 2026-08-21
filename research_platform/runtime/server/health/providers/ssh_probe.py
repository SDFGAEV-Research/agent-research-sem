from __future__ import annotations

from research_platform.runtime.server.identity.api import ServerConnectionPort

from ..api import ServerHealthProbePort, ServerHealthReport


class SSHServerHealthProbe(ServerHealthProbePort):
    """Collect stable controller-facing facts through the identity connection port."""

    COMMAND = (
        "printf 'host='; hostname; "
        "printf 'python='; python3 --version 2>&1; "
        "printf 'git='; git --version 2>&1; "
        "printf 'tmux='; tmux -V 2>&1; "
        "printf 'disk='; df -h / /data 2>&1"
    )

    def probe(
        self,
        connection: ServerConnectionPort,
        *,
        interactive: bool = False,
    ) -> ServerHealthReport:
        result = connection.execute(self.COMMAND, interactive=interactive)
        values: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return ServerHealthReport(
            server_id=result.server_id,
            reachable=result.succeeded,
            host_name=values.get("host"),
            python_version=values.get("python"),
            git_version=values.get("git"),
            tmux_version=values.get("tmux"),
            raw=result,
        )


__all__ = ["SSHServerHealthProbe"]
