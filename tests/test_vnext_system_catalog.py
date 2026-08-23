import json
from pathlib import Path
from importlib.resources import files

from research_platform.governance.system_registry.api import system_catalog

def test_vnext_catalog_has_unique_keys_and_parent_first_order():
    rows=system_catalog(); keys=[row.identity.key for row in rows]
    assert len(keys)==len(set(keys))
    seen=set()
    for row in rows:
        assert row.parent_key in seen or row.parent_key is None
        seen.add(row.identity.key)

def test_each_node_declares_one_authority_and_standard_package_shape():
    for row in system_catalog():
        assert len(row.authorities)==1
        assert row.authorities[0].authority_id
        assert row.package_prefix.startswith('research_platform.')
        assert row.owns
        assert row.must_not_own
        assert row.shape == ('api', 'runtime', 'providers', 'composition')


def test_runtime_descriptor_preserves_canonical_catalog_semantics():
    catalog = json.loads(
        files('research_platform.governance.system_registry').joinpath('catalog.json').read_text(encoding='utf-8')
    )
    for row in system_catalog():
        source = catalog[row.identity.key]
        assert row.authority_id == source['authority']
        assert row.owns == source['owns']
        assert row.must_not_own == source['must_not_own']
        assert list(row.shape) == source['shape']


def test_documentation_catalog_mirrors_packaged_catalog():
    packaged = files('research_platform.governance.system_registry').joinpath('catalog.json').read_bytes()
    documented = (Path(__file__).parents[1] / 'docs' / 'architecture' / 'VNEXT_SYSTEM_CATALOG.json').read_bytes()
    assert packaged == documented

def test_catalog_covers_all_top_level_systems():
    tops={row.identity.system_id for row in system_catalog() if row.identity.is_system}
    assert tops == {
        'platform','scope','portfolio','experimentation','execution','participant',
        'scientific','resource','environment','model','runtime','data','artifact',
        'reliability','observability','governance','operator'
    }

def test_logging_is_decomposed_into_independent_authorities():
    keys={row.identity.key for row in system_catalog()}
    for key in {
        'observability/logging/context','observability/logging/record','observability/logging/routing',
        'observability/logging/sink','observability/logging/storage','observability/logging/query',
        'observability/logging/projection','observability/logging/retention','observability/logging/capture'
    }:
        assert key in keys

def test_reliability_separates_failure_recovery_reconciliation_and_diagnostics():
    keys={row.identity.key for row in system_catalog()}
    assert {'reliability/failure/envelope','reliability/recovery/plan','reliability/reconciliation/effect','reliability/diagnostics/causal'} <= keys


def test_packaged_catalog_is_the_single_topology_declaration_authority():
    topology_source = (
        Path(__file__).parents[1]
        / "research_platform"
        / "governance"
        / "system_registry"
        / "api"
        / "topology.py"
    ).read_text(encoding="utf-8")
    assert "_SYSTEM_TOPOLOGY" not in topology_source
    catalog = json.loads(
        files("research_platform.governance.system_registry")
        .joinpath("catalog.json")
        .read_text(encoding="utf-8")
    )
    assert list(catalog) == [row.identity.key for row in system_catalog()]
