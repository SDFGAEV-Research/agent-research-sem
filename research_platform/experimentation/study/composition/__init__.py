from ..runtime import BasicStudyMetricAggregator, DeterministicStudyAssignment
from ..providers import RunArtifactStudyPublication
from research_platform.experimentation.run.api import RunArtifactStorePort


def build_default_study_protocol_services() -> tuple[DeterministicStudyAssignment, BasicStudyMetricAggregator]:
    return DeterministicStudyAssignment(), BasicStudyMetricAggregator()


def build_run_study_publication(artifacts: RunArtifactStorePort) -> RunArtifactStudyPublication:
    return RunArtifactStudyPublication(artifacts)


__all__ = ["build_default_study_protocol_services", "build_run_study_publication"]
