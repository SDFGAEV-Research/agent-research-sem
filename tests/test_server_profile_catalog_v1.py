from __future__ import annotations

import pytest

from research_platform.runtime.server.identity.api import ServerProfileCatalogError
from research_platform.runtime.server.identity.providers import build_server_profile_catalog


def test_profile_catalog_projects_explicit_membership_without_cross_server_values() -> None:
    values = {
        "PATH": "/usr/bin",
        "RP_SERVER_CATALOG_IDS": "sem-ubuntu,lab-02",
        "RP_SERVER_SEM_UBUNTU_HOST": "sem.example",
        "RP_SERVER_SEM_UBUNTU_PORT": "60320",
        "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
        "RP_SERVER_LAB_02_HOST": "lab.example",
        "RP_SERVER_LAB_02_PORT": "22",
        "RP_SERVER_LAB_02_USER": "runner",
    }
    catalog = build_server_profile_catalog(values, source="test-profile")

    assert catalog.server_ids == ("sem-ubuntu", "lab-02")
    selected = catalog.environment_for("sem-ubuntu")
    assert selected["PATH"] == "/usr/bin"
    assert selected["RP_SERVER_SEM_UBUNTU_HOST"] == "sem.example"
    assert "RP_SERVER_LAB_02_HOST" not in selected


def test_profile_catalog_reports_incomplete_identity_before_network() -> None:
    catalog = build_server_profile_catalog(
        {
            "RP_SERVER_CATALOG_IDS": "sem-ubuntu",
            "RP_SERVER_SEM_UBUNTU_HOST": "sem.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
        }
    )

    entry = catalog.entry("sem-ubuntu")
    assert entry.missing_identity_fields == ("USER",)
    assert not entry.composition_ready


def test_profile_catalog_rejects_undeclared_server_namespace() -> None:
    with pytest.raises(ServerProfileCatalogError, match="outside declared catalog membership"):
        build_server_profile_catalog(
            {
                "RP_SERVER_CATALOG_IDS": "sem-ubuntu",
                "RP_SERVER_SEM_UBUNTU_HOST": "sem.example",
                "RP_SERVER_SEM_UBUNTU_PORT": "60320",
                "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
                "RP_SERVER_OTHER_HOST": "other.example",
            }
        )


def test_profile_catalog_requires_explicit_membership() -> None:
    with pytest.raises(ServerProfileCatalogError, match="RP_SERVER_CATALOG_IDS"):
        build_server_profile_catalog(
            {
                "RP_SERVER_SEM_UBUNTU_HOST": "sem.example",
                "RP_SERVER_SEM_UBUNTU_PORT": "60320",
                "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
            }
        )
