"""Thin operator facade for the SEM Paper Minecraft application.

CLI/environment parsing and concrete provider composition live behind the typed
application boundary in ``scripts.sem_paper_minecraft_application``.  This
module intentionally owns only process entry and error-to-exit translation.
"""

from __future__ import annotations

from pathlib import Path
import sys

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from scripts.sem_paper_minecraft_application import (
    ExperimentConfigurationError,
    ExperimentInputs,
    _paired_workload_id,
    parse_inputs,
    run,
)


def main(argv: list[str] | None = None) -> int:
    try:
        request: ExperimentInputs = parse_inputs(argv)
        return run(request)
    except ExperimentConfigurationError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ExperimentConfigurationError",
    "ExperimentInputs",
    "_paired_workload_id",
    "main",
    "parse_inputs",
    "run",
]
