from __future__ import annotations

import shlex

from research_platform.runtime.server.identity.api import ServerConnectionPort
from research_platform.runtime.server.api import ServerOperationEffect

from ..api import ServerHealthProbePort, ServerHealthReport, ServerRuntimeHealthSpec


def _line_command(executable: str, *arguments: str) -> str:
    return shlex.join((executable, *arguments))


class SSHServerHealthProbe(ServerHealthProbePort):
    """Collect connectivity and managed-runtime facts through SSH."""

    BASIC_COMMAND = (
        "printf 'host='; hostname; "
        "printf 'python='; python3 --version 2>&1; "
        "printf 'git='; git --version 2>&1; "
        "printf 'tmux='; tmux -V 2>&1; "
        "printf 'disk='; df -h / /data 2>&1"
    )

    @staticmethod
    def _managed_command(specification: ServerRuntimeHealthSpec) -> str:
        checks = (
            ("remote_home", "directory", specification.remote_home),
            ("platform_root", "directory", specification.platform_root),
            ("release_root", "directory", specification.release_root),
            ("python_executable", "executable", specification.python_executable),
            ("node_executable", "executable", specification.node_executable),
            ("java_executable", "executable", specification.java_executable),
            ("platform_management_executable", "executable", specification.platform_management_executable),
            ("tmux_executable", "executable", specification.tmux_executable),
            ("sha256sum_executable", "executable", specification.sha256sum_executable),
        )
        parts = [
            "set +e",
            "printf 'host='; hostname 2>&1",
            f"python_version=$({_line_command(specification.python_executable, '--version')} 2>&1); printf 'python_version=%s\\n' \"$python_version\"",
            "python_packages_probe=$(mktemp); "
            f"{_line_command(specification.python_executable, '-m', 'pip', 'freeze', '--all')} >\"$python_packages_probe\" 2>&1; "
            "python_packages_status=$?; "
            f"if test \"$python_packages_status\" -eq 0; then python_packages_digest=$(LC_ALL=C sort \"$python_packages_probe\" | {_line_command(specification.sha256sum_executable)}); else python_packages_digest=UNAVAILABLE; fi; "
            "rm -f -- \"$python_packages_probe\"; "
            "printf 'python_packages_status=%s\\n' \"$python_packages_status\"; "
            "printf 'python_packages_digest=%s\\n' \"$python_packages_digest\"",
            f"node_version=$({_line_command(specification.node_executable, '--version')} 2>&1); printf 'node_version=%s\\n' \"$node_version\"",
            f"java_version=$({_line_command(specification.java_executable, '-version')} 2>&1); printf 'java_version=%s\\n' \"$java_version\"",
            f"printf 'python_binary_digest='; {_line_command(specification.sha256sum_executable, '--', specification.python_executable)} 2>&1",
            f"printf 'node_binary_digest='; {_line_command(specification.sha256sum_executable, '--', specification.node_executable)} 2>&1",
            f"printf 'java_binary_digest='; {_line_command(specification.sha256sum_executable, '--', specification.java_executable)} 2>&1",
            f"printf 'platform_management_binary_digest='; {_line_command(specification.sha256sum_executable, '--', specification.platform_management_executable)} 2>&1",
            f"printf 'tmux_digest='; {_line_command(specification.sha256sum_executable, '--', specification.tmux_executable)} 2>&1",
        ]
        for key, kind, path in checks:
            quoted = shlex.quote(path)
            test = "-d" if kind == "directory" else "-x"
            parts.append(f"if test {test} {quoted}; then printf '{key}=present\\n'; else printf '{key}=missing\\n'; fi")
        return "; ".join(parts)

    @staticmethod
    def _parse(stdout: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in stdout.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values

    @staticmethod
    def _managed_result(
        values: dict[str, str],
        result,
        specification: ServerRuntimeHealthSpec,
    ) -> tuple[bool, tuple[tuple[str, str], ...], tuple[str, ...]]:
        checks = {
            key: values.get(key, "missing")
            for key in (
                "remote_home",
                "platform_root",
                "release_root",
                "python_executable",
                "node_executable",
                "java_executable",
                "platform_management_executable",
                "tmux_executable",
                "sha256sum_executable",
            )
        }
        issues = [key for key, value in checks.items() if value != "present"]
        digest_line = values.get("tmux_digest", "")
        actual_digest = digest_line.split()[0].lower() if digest_line.split() else ""
        checks["tmux_binary_identity"] = "verified" if actual_digest == specification.tmux_binary_sha256.lower() else "mismatch"
        if checks["tmux_binary_identity"] != "verified":
            issues.append("tmux_binary_identity")
        package_status = values.get("python_packages_status", "1")
        package_digest = values.get("python_packages_digest", "").split()[0].lower()
        checks["python_packages_identity"] = (
            "verified"
            if package_status == "0" and package_digest == specification.python_packages_sha256.lower()
            else "mismatch"
        )
        if checks["python_packages_identity"] != "verified":
            issues.append("python_packages_identity")
        for check_name, digest_key, expected in (
            ("python_binary_identity", "python_binary_digest", specification.python_binary_sha256),
            ("node_binary_identity", "node_binary_digest", specification.node_binary_sha256),
            ("java_binary_identity", "java_binary_digest", specification.java_binary_sha256),
            (
                "platform_management_binary_identity",
                "platform_management_binary_digest",
                specification.platform_management_binary_sha256,
            ),
        ):
            actual = values.get(digest_key, "").split()[0].lower()
            checks[check_name] = "verified" if actual == expected.lower() else "mismatch"
            if checks[check_name] != "verified":
                issues.append(check_name)
        checks_tuple = tuple(sorted(checks.items()))
        return result.succeeded and not issues, checks_tuple, tuple(issues)

    def probe(
        self,
        connection: ServerConnectionPort,
        *,
        interactive: bool = False,
        specification: ServerRuntimeHealthSpec | None = None,
    ) -> ServerHealthReport:
        if specification is None:
            result = connection.execute(
                self.BASIC_COMMAND,
                interactive=interactive,
                effect=ServerOperationEffect.OBSERVATION,
            )
            values = self._parse(result.stdout)
            return ServerHealthReport(
                server_id=result.server_id,
                reachable=result.succeeded,
                host_name=values.get("host"),
                python_version=values.get("python"),
                git_version=values.get("git"),
                tmux_version=values.get("tmux"),
                raw=result,
                platform_ready=result.succeeded,
            )
        result = connection.execute(
            self._managed_command(specification),
            interactive=interactive,
            effect=ServerOperationEffect.OBSERVATION,
        )
        values = self._parse(result.stdout)
        ready, checks, issues = self._managed_result(values, result, specification)
        return ServerHealthReport(
            server_id=result.server_id,
            reachable=result.succeeded,
            host_name=values.get("host"),
            python_version=values.get("python_version"),
            git_version=None,
            tmux_version=None,
            raw=result,
            platform_ready=ready,
            checks=checks,
            issues=issues,
        )


__all__ = ["SSHServerHealthProbe"]
