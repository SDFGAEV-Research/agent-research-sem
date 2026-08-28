"""Thin operator facade for the SEM non-Minecraft conformance application."""

from __future__ import annotations

from pathlib import Path
import sys

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from scripts.sem_paper_non_minecraft_application import (
    NonMinecraftExperimentConfigurationError,
    NonMinecraftExperimentInputs,
    parse_inputs,
    run,
)


def main(argv: list[str] | None = None) -> int:
    try:
        inputs: NonMinecraftExperimentInputs = parse_inputs(argv)
        return run(inputs)
    except NonMinecraftExperimentConfigurationError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
