from __future__ import annotations

from dataclasses import dataclass

from research_platform.artifact.content.composition import compose_artifact_acquisition
from research_platform.artifact.content.providers import (
    HttpOpener,
    SafeTarArchiveMaterializer,
)
from research_platform.runtime.toolchain.api import JavaRuntimeProvisioningPort
from research_platform.runtime.toolchain.providers import (
    EclipseAdoptiumTemurinProvider,
    JavaCommandRunner,
)


@dataclass(frozen=True, slots=True)
class JavaRuntimeToolchainAssembly:
    provisioner: JavaRuntimeProvisioningPort


def compose_eclipse_adoptium_java_runtime(
    *,
    metadata_opener: HttpOpener | None = None,
    artifact_opener: HttpOpener | None = None,
    command_runner: JavaCommandRunner | None = None,
) -> JavaRuntimeToolchainAssembly:
    acquisition = compose_artifact_acquisition(opener=artifact_opener)
    materializer = SafeTarArchiveMaterializer()
    options = {} if command_runner is None else {"command_runner": command_runner}
    return JavaRuntimeToolchainAssembly(
        provisioner=EclipseAdoptiumTemurinProvider(
            acquisition.acquirer,
            materializer,
            materializer,
            metadata_opener=metadata_opener,
            **options,
        )
    )


__all__ = ["JavaRuntimeToolchainAssembly", "compose_eclipse_adoptium_java_runtime"]
