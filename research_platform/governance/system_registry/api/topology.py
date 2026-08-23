from __future__ import annotations

import json
from dataclasses import replace
from functools import lru_cache
from importlib.resources import files

from .contracts import (
    STANDARD_SYSTEM_SHAPE,
    AuthorityDescriptor,
    SystemDescriptor,
    SystemIdentity,
    SystemLayer,
)

_NODE_METADATA: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    'artifact': (('scope',), (), ()),
    'artifact/catalog': ((), ('artifact.registry',), ()),
    'data': (('scope',), (), ()),
    'data/dataset': ((), ('dataset.registry',), ()),
    'data/fact': ((), ('durable.fact',), ()),
    'data/projection': ((), ('projection.runtime',), ()),
    'data/record': ((), ('record.plane',), ()),
    'data/state': ((), ('state.atomic',), ()),
    'environment': (('platform', 'reliability', 'resource', 'scope'), (), ()),
    'environment/catalog': ((), ('environment.catalog',), ()),
    'environment/minecraft': (('artifact', 'environment', 'reliability', 'resource', 'runtime'), ('environment.minecraft.contract',), ()),
    'environment/python': ((), ('python-environment.registry', 'python-environment.lifecycle', 'python-environment.execution', 'python-environment.packages'), ()),
    'environment/runtime': ((), ('environment.contract',), ()),
    'execution': (('environment', 'governance', 'model', 'observability', 'participant', 'platform', 'reliability', 'runtime', 'scope'), (), ()),
    'execution/capability': ((), ('capability.invocation', 'capability.registration'), ()),
    'execution/workflow': ((), ('workflow.runtime',), ()),
    'experimentation': (('environment', 'execution', 'participant', 'platform', 'scope'), (), ()),
    'experimentation/checkpoint': ((), ('run.checkpoint',), ()),
    'experimentation/experiment': ((), ('experiment.definition', 'experiment.runtime'), ()),
    'experimentation/run': ((), ('run.lifecycle', 'run.decision'), ()),
    'experimentation/study': ((), ('study.definition',), ()),
    'governance': (('platform',), (), ()),
    'governance/architecture': (('scope',), ('architecture.audit',), ()),
    'governance/quality': ((), ('quality.audit',), ()),
    'governance/release': ((), ('release.freeze',), ()),
    'model': (('environment', 'platform', 'resource', 'runtime', 'scope'), (), ()),
    'model/asset': ((), ('model.asset', 'model.asset-acquisition'), ()),
    'model/assignment': ((), ('model.assignment',), ()),
    'model/deployment': ((), ('model.deployment', 'model.deployment-control'), ()),
    'model/request': ((), ('model.request',), ()),
    'model/serving': ((), ('model.serving', 'model.qualification'), ()),
    'observability': (('data', 'governance', 'platform', 'scope'), (), ()),
    'observability/logging': ((), ('logging.observation',), ()),
    'observability/status': ((), ('status.read-model',), ()),
    'observability/telemetry': ((), ('telemetry.metrics',), ()),
    'operator': (('environment', 'governance', 'model', 'observability', 'platform', 'reliability', 'resource', 'scope'), (), ()),
    'participant': (('data', 'platform', 'reliability'), (), ()),
    'participant/agent': ((), ('agent.contract',), ()),
    'participant/capability': ((), ('capability.contract',), ()),
    'participant/method': (('governance',), ('method.contract', 'method.runtime'), ()),
    'portfolio': (('scope',), (), ()),
    'reliability': (('data', 'governance', 'observability', 'platform', 'scope'), (), ()),
    'reliability/diagnostics': ((), ('diagnostics.causal',), ()),
    'reliability/effect': ((), ('effect.safety', 'effect.journal'), ()),
    'reliability/failure': ((), ('failure.truth',), ()),
    'reliability/forensics': ((), ('forensics.ledger',), ()),
    'reliability/recovery': ((), ('recovery.runtime',), ()),
    'resource': (('platform', 'scope'), (), ()),
    'resource/allocation': (('resource/lease',), ('resource.endpoint-allocation',), ()) ,
    'resource/compute': ((), ('compute.inventory', 'compute.scheduler'), ()),
    'resource/directory': ((), ('directory.layout', 'workspace.storage'), ()),
    'resource/resolution': ((), ('resource.hierarchical-resolution',), ()),
    'resource/lease': (('scope',), ('resource.lease',), ()),
    'runtime': (('governance', 'observability', 'platform', 'reliability', 'scope'), (), ()),
    'runtime/host': ((), ('host.runtime',), ()),
    'runtime/process': ((), ('process.execution', 'process.capture'), ()),
    'runtime/service': ((), ('service.runtime',), ()),
    'runtime/session': ((), ('persistent-session.runtime',), ()),
    'runtime/toolchain': (('artifact',), ('runtime.toolchain',), ()),
    'scientific': (('data', 'experimentation', 'participant', 'platform'), (), ()),
}


def _apply_node_metadata(descriptor: SystemDescriptor) -> SystemDescriptor:
    metadata = _NODE_METADATA.get(descriptor.identity.key)
    if metadata is None:
        return descriptor
    requires, provides, components = metadata
    return replace(
        descriptor,
        requires=requires,
        provides=provides,
        components=components,
    )


@lru_cache(maxsize=1)
def _load_catalog_semantics() -> dict[str, dict[str, object]]:
    """Load the canonical recursive system topology and ownership semantics.

    ``catalog.json`` is the single declaration authority for node identity,
    ordering, parentage, package ownership and authority identity.  Python code
    may attach runtime-only capability metadata, but it must not redeclare the
    system tree.
    """

    catalog_resource = files("research_platform.governance.system_registry").joinpath("catalog.json")
    try:
        raw = json.loads(catalog_resource.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("cannot load packaged canonical system catalog") from exc
    if not isinstance(raw, dict) or not raw:
        raise RuntimeError("packaged canonical system catalog is not a non-empty object")

    required = {"authority", "must_not_own", "owns", "package_prefix", "parent", "shape"}
    result: dict[str, dict[str, object]] = {}
    seen: set[str] = set()
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, dict) or set(value) != required:
            raise RuntimeError(f"invalid packaged catalog descriptor for {key!r}")
        if value["shape"] != list(STANDARD_SYSTEM_SHAPE):
            raise RuntimeError(f"unsupported packaged system shape for {key!r}")
        parts = tuple(part for part in key.split("/") if part)
        if not parts or "/".join(parts) != key:
            raise RuntimeError(f"invalid packaged catalog identity for {key!r}")
        expected_parent = None if len(parts) == 1 else "/".join(parts[:-1])
        source_parent = value["parent"]
        if isinstance(source_parent, str):
            source_parent = source_parent.replace(".", "/")
        if source_parent != expected_parent:
            raise RuntimeError(f"parent drift for {key!r}")
        if expected_parent is not None and expected_parent not in seen:
            raise RuntimeError(f"catalog parent must precede child: {key!r}")
        seen.add(key)
        result[key] = value
    return result


def _descriptor_from_catalog(key: str, semantics: dict[str, object]) -> SystemDescriptor:
    parts = key.split("/")
    authority = semantics["authority"]
    owns = semantics["owns"]
    must_not_own = semantics["must_not_own"]
    package_prefix = semantics["package_prefix"]
    if not all(
        isinstance(item, str) and item.strip()
        for item in (authority, owns, must_not_own, package_prefix)
    ):
        raise RuntimeError(f"invalid ownership semantics for {key}")
    descriptor = SystemDescriptor(
        identity=SystemIdentity(parts[0], tuple(parts[1:])),
        layer=SystemLayer(parts[0]),
        package_prefix=package_prefix,
        authorities=(AuthorityDescriptor(authority),),
        owns=owns,
        must_not_own=must_not_own,
        shape=tuple(semantics["shape"]),
    )
    return _apply_node_metadata(descriptor)


SYSTEM_CATALOG: tuple[SystemDescriptor, ...] = tuple(
    _descriptor_from_catalog(key, semantics)
    for key, semantics in _load_catalog_semantics().items()
)


def system_catalog() -> tuple[SystemDescriptor, ...]:
    """Return the canonical recursive platform system tree."""

    return SYSTEM_CATALOG


__all__ = ["SYSTEM_CATALOG", "system_catalog"]
