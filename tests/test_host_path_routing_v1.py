from __future__ import annotations

from pathlib import Path

from research_platform.runtime.host.api import OperatingSystemFamily
from research_platform.runtime.host.composition import build_local_operating_system_route
from research_platform.scope.path.api import (
    PathFlavor,
    is_absolute_target_path,
    require_absolute_target_path,
)
from research_platform.scope.path.composition import build_target_path_resolver


def test_target_path_contract_accepts_both_remote_path_flavors() -> None:
    assert is_absolute_target_path("/srv/research")
    assert is_absolute_target_path(r"C:\research")
    assert not is_absolute_target_path("relative/research")
    assert require_absolute_target_path("/srv/research", field="cwd") == "/srv/research"


def test_target_path_resolver_keeps_explicit_flavor() -> None:
    resolver = build_target_path_resolver()
    assert resolver.normalize("/srv/../data", flavor=PathFlavor.POSIX) == "/data"
    assert resolver.normalize(r"C:\srv\..\data", flavor=PathFlavor.WINDOWS) == r"C:\data"


def test_local_os_route_exposes_one_host_identity_and_conventions() -> None:
    route = build_local_operating_system_route()
    assert route.identity.family in set(OperatingSystemFamily)
    assert route.temporary_root().is_absolute()
    assert route.null_device()
