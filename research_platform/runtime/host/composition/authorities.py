from ..api import OperatingSystemRoute
from ..providers import LocalOperatingSystemRoute


def build_local_operating_system_route() -> OperatingSystemRoute:
    return LocalOperatingSystemRoute()


__all__ = ["build_local_operating_system_route"]
