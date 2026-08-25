from __future__ import annotations

import sys

def _fallback_without_pytest(arguments: list[str]) -> int:
    """Run one dependency-free fixture module for runner lifecycle tests only."""

    import inspect
    from pathlib import Path
    import runpy
    import signal

    # Keep the fixture alive until the release runner's force phase so the
    # process-group reaper is exercised under the same failure timing as the
    # real pytest worker.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)

    paths = [Path(item) for item in arguments if not item.startswith("-")]
    if not paths:
        paths = sorted(Path.cwd().glob("test_*.py"))
    if len(paths) != 1 or not paths[0].is_file():
        print("PYTEST_UNAVAILABLE: full release regression requires pytest", file=sys.stderr)
        return 2
    namespace = runpy.run_path(str(paths[0]))
    tests = [
        value for name, value in namespace.items()
        if name.startswith("test") and callable(value) and not inspect.signature(value).parameters
    ]
    if "--collect-only" in arguments:
        print(f"{len(tests)} test collected")
        return 0
    for test in tests:
        test()
    print(f"{len(tests)} passed")
    return 0


def main() -> int:
    try:
        import pytest
    except ModuleNotFoundError:
        return _fallback_without_pytest(sys.argv[1:])
    return int(pytest.main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
