from __future__ import annotations

import sys

import pytest


def main() -> int:
    return int(pytest.main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
