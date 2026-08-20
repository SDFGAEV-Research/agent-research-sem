#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from research_platform.runtime.session.runtime import (
    DirectoryPersistentSessionBindingStore,
    PersistentSessionManager,
    PersistentSessionSpec,
    TmuxCli,
)


def _cli(args) -> TmuxCli:
    environment: dict[str, str] = {}
    if args.home is not None:
        environment["HOME"] = args.home
    if args.tmpdir is not None:
        environment["TMPDIR"] = args.tmpdir
    return TmuxCli(
        tmux_executable=args.tmux_executable,
        server_label=args.server_label,
        client_environment=environment,
    )


def _manager(args) -> PersistentSessionManager:
    return PersistentSessionManager(
        _cli(args),
        DirectoryPersistentSessionBindingStore(args.binding_root),
    )


def _emit(payload: dict[str, object]) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str))
    return 0


def ensure(args) -> int:
    release_dir = args.release_root.resolve() / "releases" / args.release_digest
    if not release_dir.is_dir() or release_dir.is_symlink():
        raise RuntimeError(f"immutable release directory missing/invalid: {release_dir}")
    if not args.command:
        raise ValueError("controller command required after --")
    safe_control = "".join(ch if ch.isalnum() or ch in "_.-" else "-" for ch in args.control_id)[:32] or "runtime"
    import hashlib
    control_hash = hashlib.sha256(args.control_id.encode()).hexdigest()[:8]
    session_name = f"rp-{safe_control}-{control_hash}-{args.runtime_manifest_digest[:12]}"
    spec = PersistentSessionSpec(
        session_name,
        tuple(args.command),
        str(release_dir),
        args.control_id,
        args.runtime_manifest_digest,
    )
    report = _manager(args).ensure(spec)
    return _emit(
        {
            "session_name": report.snapshot.session_name,
            "session_exact": True,
            "reused": report.reused,
            "pane_pid": report.snapshot.pane_pid,
            "spec_digest": report.spec_digest,
            "attach_argv": report.attach_argv,
            "evidence_refs": report.evidence_refs,
            "release_dir": str(release_dir),
        }
    )


def status(args) -> int:
    store = DirectoryPersistentSessionBindingStore(args.binding_root)
    binding = store.read(args.session_name)
    if binding is None:
        return _emit({"session_name": args.session_name, "binding": "missing", "exact": False})
    manager = PersistentSessionManager(_cli(args), store)
    snapshot = manager.inspect(binding.spec)
    return _emit(
        {
            "session_name": snapshot.session_name,
            "binding": "exact",
            "exact": True,
            "pane_pid": snapshot.pane_pid,
            "pane_dead": snapshot.pane_dead,
            "spec_digest": binding.spec_digest,
            "runtime_manifest_digest": binding.spec.runtime_manifest_digest,
            "control_id": binding.spec.control_id,
            "attach_argv": manager.control.attach_argv(snapshot.session_name),
            "evidence_refs": snapshot.evidence_refs,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Host the exact RuntimeManager controller in an immutable tmux session."
    )
    sub = parser.add_subparsers(dest="action", required=True)

    def common(p):
        p.add_argument("--binding-root", type=Path, required=True)
        p.add_argument("--tmux-executable", default="/usr/bin/tmux")
        p.add_argument("--server-label", default="research-platform")
        p.add_argument("--home")
        p.add_argument("--tmpdir", default="/tmp")

    p = sub.add_parser("ensure")
    common(p)
    p.add_argument("--release-root", type=Path, required=True)
    p.add_argument("--release-digest", required=True)
    p.add_argument("--runtime-manifest-digest", required=True)
    p.add_argument("--control-id", required=True)
    p.add_argument("command", nargs=argparse.REMAINDER)
    p.set_defaults(func=ensure)

    p = sub.add_parser("status")
    common(p)
    p.add_argument("session_name")
    p.set_defaults(func=status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(args, "release_digest") and len(args.release_digest) != 64:
        raise ValueError("release digest must be SHA-256")
    if hasattr(args, "runtime_manifest_digest") and len(args.runtime_manifest_digest) != 64:
        raise ValueError("runtime manifest digest must be SHA-256")
    if getattr(args, "command", None) and args.command[0] == "--":
        args.command = args.command[1:]
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
