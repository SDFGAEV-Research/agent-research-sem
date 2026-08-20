from __future__ import annotations
from research_platform.resource.compute.api import ComputeCluster, ComputeHost
from research_platform.scope.api import ScopeIdentity

class InMemoryComputeInventory:
    def __init__(self) -> None:
        self._hosts: dict[str, ComputeHost] = {}
        self._clusters: dict[str, ComputeCluster] = {}

    def register_host(self, host: ComputeHost) -> None:
        current = self._hosts.get(host.host_id)
        if current is not None and current != host:
            raise ValueError(f"host identity already registered: {host.host_id}")
        self._hosts[host.host_id] = host

    def host(self, host_id: str) -> ComputeHost:
        try: return self._hosts[host_id]
        except KeyError as exc: raise KeyError(host_id) from exc

    def list_hosts(self, *, scope: ScopeIdentity | None = None) -> tuple[ComputeHost, ...]:
        return tuple(sorted((x for x in self._hosts.values() if scope is None or x.scope == scope), key=lambda x: x.host_id))

    def register_cluster(self, cluster: ComputeCluster) -> None:
        for host_id in cluster.host_ids: self.host(host_id)
        current = self._clusters.get(cluster.cluster_id)
        if current is not None and current != cluster:
            raise ValueError(f"cluster identity already registered: {cluster.cluster_id}")
        self._clusters[cluster.cluster_id] = cluster

    def cluster(self, cluster_id: str) -> ComputeCluster:
        try: return self._clusters[cluster_id]
        except KeyError as exc: raise KeyError(cluster_id) from exc
