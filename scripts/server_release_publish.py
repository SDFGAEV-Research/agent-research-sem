from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.runtime.host.composition import compose_local_host
from research_platform.runtime.server.identity.composition import (
    compose_environment_server_identity,
)
from research_platform.runtime.server.lifecycle.api import (
    ServerReleaseDeploymentRequest,
    ServerReleaseLayout,
    ServerRemoteProfile,
)
from research_platform.runtime.server.lifecycle.composition import (
    compose_ssh_server_release_publisher,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish one exact release package to a managed server")
    parser.add_argument("server_id", help="logical server id; values come from RP_SERVER_<ID>_*")
    parser.add_argument("package", type=Path, help="local official release ZIP")
    parser.add_argument(
        "remote_root",
        nargs="?",
        help="optional absolute POSIX release root; defaults to the server profile",
    )
    parser.add_argument("--interactive", action="store_true", help="allow OpenSSH/scp to prompt on the terminal")
    args = parser.parse_args(argv)
    package = args.package.expanduser().resolve()
    try:
        meta = build_in_memory_platform_meta()
        host = compose_local_host(planner=meta.capability_composition)
        identity = compose_environment_server_identity(
            operating_system=host.operating_system,
            host_operating_system_offer=host.operating_system_offer,
            planner=meta.capability_composition,
        )
        connection = identity.connection_factory.from_environment(args.server_id)
        transfer = identity.file_transfer_factory.from_environment(args.server_id)
        remote_root = args.remote_root or ServerRemoteProfile.from_environment(args.server_id).release_root
        publisher = compose_ssh_server_release_publisher(
            connection=connection,
            transfer=transfer,
        )
        receipt = publisher.publish(
            ServerReleaseDeploymentRequest(
                release_digest=_sha256(package),
                local_package=package,
                layout=ServerReleaseLayout(remote_root),
            ),
            interactive=args.interactive,
        )
    except Exception as exc:
        print(json.dumps({
            "server_id": args.server_id,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "server_id": receipt.server_id,
        "release_digest": receipt.release_digest,
        "remote_archive": receipt.remote_archive,
        "remote_release_dir": receipt.remote_release_dir,
        "uploaded": receipt.uploaded,
        "preparation_return_code": receipt.preparation.return_code,
        "transfer_return_code": receipt.transfer.return_code if receipt.transfer else None,
        "finalization_return_code": receipt.finalization.return_code if receipt.finalization else None,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
