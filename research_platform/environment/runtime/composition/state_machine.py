from __future__ import annotations

from dataclasses import dataclass

from ..api import StateMachineDynamicsPort, StateMachineEnvironmentSpec
from ..runtime.state_machine import (
    StateMachineEnvironmentImplementation,
    StateMachineEnvironmentRuntime,
)


@dataclass(frozen=True, slots=True)
class StateMachineEnvironmentAssembly:
    implementation: StateMachineEnvironmentImplementation
    runtime: StateMachineEnvironmentRuntime


def compose_state_machine_environment(
    spec: StateMachineEnvironmentSpec,
    *,
    dynamics: StateMachineDynamicsPort,
) -> StateMachineEnvironmentAssembly:
    implementation = StateMachineEnvironmentImplementation(spec, dynamics)
    return StateMachineEnvironmentAssembly(
        implementation=implementation,
        runtime=StateMachineEnvironmentRuntime(),
    )


__all__ = ["StateMachineEnvironmentAssembly", "compose_state_machine_environment"]
