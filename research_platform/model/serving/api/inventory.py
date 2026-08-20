from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True, slots=True)
class CPUNode:
    numa_node: int
    cpu_ids: tuple[int,...]
    memory_bytes: int


@dataclass(frozen=True, slots=True)
class CPUInventory:
    architecture: str
    logical_cpus: int
    allowed_cpu_ids: tuple[int,...]
    cgroup_quota_cpus: float | None
    numa_nodes: tuple[CPUNode,...]


@dataclass(frozen=True, slots=True)
class GPUInventory:
    uuid: str
    name: str
    total_memory_bytes: int
    free_memory_bytes: int
    pci_bus_id: str
    numa_node: int | None
    compute_capability: str | None
    power_limit_watts: float | None


@dataclass(frozen=True, slots=True)
class GPUFabricLink:
    a_uuid: str
    b_uuid: str
    link_type: str
    bandwidth_gbps: float


@dataclass(frozen=True, slots=True)
class MemoryInventory:
    physical_total_bytes: int
    physical_available_bytes: int
    cgroup_max_bytes: int | None
    cgroup_current_bytes: int | None

    @property
    def effective_available_bytes(self)->int:
        if self.cgroup_max_bytes is None or self.cgroup_current_bytes is None:
            return self.physical_available_bytes
        return min(self.physical_available_bytes,max(0,self.cgroup_max_bytes-self.cgroup_current_bytes))


@dataclass(frozen=True, slots=True)
class MountInventory:
    path: str
    filesystem: str
    device_identity: str
    total_bytes: int
    free_bytes: int
    free_inodes: int | None
    reflink_supported: bool | None


@dataclass(frozen=True, slots=True)
class RuntimeInventory:
    kernel: str
    python: str
    node: str | None
    java: str | None
    nvidia_driver: str | None
    cuda_driver_api: str | None
    nvml: str | None
    sglang: str | None
    vllm: str | None


@dataclass(frozen=True, slots=True)
class HostLimits:
    nofile_soft: int
    nofile_hard: int
    pids_max: int | None


@dataclass(frozen=True, slots=True)
class HostInventory:
    hostname: str
    captured_at_unix: float
    cpu: CPUInventory
    memory: MemoryInventory
    gpus: tuple[GPUInventory,...]
    fabric: tuple[GPUFabricLink,...]
    mounts: tuple[MountInventory,...]
    runtime: RuntimeInventory
    limits: HostLimits
    listening_ports: tuple[int,...]

    def __post_init__(self)->None:
        if len({g.uuid for g in self.gpus})!=len(self.gpus): raise ValueError("duplicate GPU UUID")
        if len(set(self.cpu.allowed_cpu_ids))!=len(self.cpu.allowed_cpu_ids): raise ValueError("duplicate allowed CPU")
        if len(set(self.listening_ports))!=len(self.listening_ports): raise ValueError("duplicate listening port")

    def identity_digest(self)->str:
        """Stable host/runtime compatibility identity; excludes transient capacity/occupancy."""
        payload={
            "hostname":self.hostname,
            "cpu":{
                "architecture":self.cpu.architecture,
                "logical_cpus":self.cpu.logical_cpus,
                "numa_nodes":tuple(
                    {"numa_node":n.numa_node,"cpu_ids":n.cpu_ids,"memory_bytes":n.memory_bytes}
                    for n in self.cpu.numa_nodes
                ),
            },
            "memory":{"physical_total_bytes":self.memory.physical_total_bytes},
            "gpus":tuple(
                {
                    "uuid":g.uuid,"name":g.name,"total_memory_bytes":g.total_memory_bytes,
                    "pci_bus_id":g.pci_bus_id,"numa_node":g.numa_node,
                    "compute_capability":g.compute_capability,"power_limit_watts":g.power_limit_watts,
                }
                for g in self.gpus
            ),
            "fabric":tuple(asdict(x) for x in self.fabric),
            "mounts":tuple(
                {
                    "path":m.path,"filesystem":m.filesystem,"device_identity":m.device_identity,
                    "total_bytes":m.total_bytes,"reflink_supported":m.reflink_supported,
                }
                for m in self.mounts
            ),
            "runtime":asdict(self.runtime),
        }
        raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def snapshot_digest(self)->str:
        """Full point-in-time inventory digest including free resources and listening ports."""
        raw=json.dumps(asdict(self),sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
        return hashlib.sha256(raw).hexdigest()
