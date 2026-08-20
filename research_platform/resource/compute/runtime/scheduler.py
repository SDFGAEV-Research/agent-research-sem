from __future__ import annotations
from research_platform.resource.compute.api import ComputeAllocation, ComputeRequirement
from research_platform.scope.api import ScopeIdentity
from .inventory import InMemoryComputeInventory

class InMemoryComputeScheduler:
    """Simple capacity scheduler; policy can be replaced without changing compute contracts."""
    def __init__(self, inventory: InMemoryComputeInventory) -> None:
        self._inventory = inventory
        self._allocations: dict[str, ComputeAllocation] = {}

    def _usage(self, host_id: str) -> tuple[int, int, set[str]]:
        rows=[x for x in self._allocations.values() if x.host_id == host_id]
        return sum(x.cpu_cores for x in rows), sum(x.memory_bytes for x in rows), {gpu for x in rows for gpu in x.gpu_ids}

    def candidates(self, requirement: ComputeRequirement, *, scope: ScopeIdentity | None = None):
        result=[]
        required_labels=dict(requirement.required_labels)
        for host in self._inventory.list_hosts(scope=scope):
            if not host.enabled or any(dict(host.labels).get(k) != v for k,v in required_labels.items()): continue
            cpu,memory,used_gpus=self._usage(host.host_id)
            available_gpus=tuple(g.gpu_id for g in host.gpus if g.gpu_id not in used_gpus and g.memory_bytes >= requirement.minimum_gpu_memory_bytes)
            if host.cpu_cores-cpu < requirement.cpu_cores or host.memory_bytes-memory < requirement.memory_bytes: continue
            if len(available_gpus) < requirement.gpu_count: continue
            result.append(host)
        return tuple(result)

    def allocate(self, allocation_id: str, scope: ScopeIdentity, requirement: ComputeRequirement) -> ComputeAllocation:
        if allocation_id in self._allocations: raise ValueError(f"allocation already exists: {allocation_id}")
        hosts=self.candidates(requirement)
        if not hosts: raise RuntimeError("no compute host satisfies requirement")
        host=hosts[0]
        _,_,used=self._usage(host.host_id)
        gpu_ids=tuple(g.gpu_id for g in host.gpus if g.gpu_id not in used and g.memory_bytes >= requirement.minimum_gpu_memory_bytes)[: requirement.gpu_count]
        row=ComputeAllocation(allocation_id, scope, host.host_id, requirement.cpu_cores, requirement.memory_bytes, gpu_ids)
        self._allocations[allocation_id]=row
        return row

    def release(self, allocation_id: str) -> None:
        self._allocations.pop(allocation_id, None)

    def allocations(self, *, scope: ScopeIdentity | None = None) -> tuple[ComputeAllocation, ...]:
        return tuple(sorted((x for x in self._allocations.values() if scope is None or x.scope == scope), key=lambda x:x.allocation_id))
