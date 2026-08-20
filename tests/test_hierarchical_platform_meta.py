from research_platform.experimentation.catalog.runtime import InMemoryExperimentationCatalog
from research_platform.experimentation.experiment.api import ExperimentSpec
from research_platform.experimentation.run.identity.api import RunIdentity
from research_platform.experimentation.study import StudySpec
from research_platform.portfolio.api import ProgramSpec, ProjectManifest, ProjectSpec, WorkspaceSpec
from research_platform.portfolio.runtime import InMemoryPortfolioCatalog
from research_platform.environment.catalog.api import (
    EnvironmentAssignment,
    EnvironmentOverlay,
    EnvironmentSpec,
    ExecutionEnvironmentKind,
)
from research_platform.environment.catalog.runtime import ExecutionEnvironmentCatalog
from research_platform.scope.api import ScopeIdentity, ScopeKind
from research_platform.scope.runtime import InMemoryScopeRegistry


def test_scope_portfolio_experiment_run_hierarchy_is_explicit():
    scopes = InMemoryScopeRegistry()
    portfolio = InMemoryPortfolioCatalog(scopes)
    portfolio.register_workspace(WorkspaceSpec("ws", "Workspace"))
    portfolio.register_program(ProgramSpec("prog", "ws", "Program"))
    portfolio.register_project(ProjectManifest(ProjectSpec("paper", "prog", "Paper"), study_ids=("main",)))

    experiments = InMemoryExperimentationCatalog(scopes)
    study = StudySpec("main", "paper", "Main", ("exp",))
    experiments.register_study(study)
    experiment = ExperimentSpec(
        experiment_id="exp",
        study_id="main",
        project_id="paper",
        participants=(),
        model_stack_digest="m",
        prompt_generation="p",
        workload_digest="w",
        seed_digest="s",
        repetitions=1,
        scientific_workflow_id="wf",
    )
    experiments.register_experiment(experiment)
    run = RunIdentity("run-1", "session-1", "trace-1")
    experiments.register_run("exp", run)

    assert [item.kind for item in scopes.ancestry(run.scope)] == [
        ScopeKind.RUN,
        ScopeKind.EXPERIMENT,
        ScopeKind.STUDY,
        ScopeKind.PROJECT,
        ScopeKind.PROGRAM,
        ScopeKind.WORKSPACE,
        ScopeKind.PLATFORM,
    ]


def test_environment_assignment_inherits_and_overlay_merges_without_copying_envs():
    scopes = InMemoryScopeRegistry()
    ws = ScopeIdentity(ScopeKind.WORKSPACE, "ws")
    project = ScopeIdentity(ScopeKind.PROJECT, "paper")
    study = ScopeIdentity(ScopeKind.STUDY, "study")
    scopes.register(ws, ScopeIdentity(ScopeKind.PLATFORM, "default"))
    program = ScopeIdentity(ScopeKind.PROGRAM, "prog")
    scopes.register(program, ws)
    scopes.register(project, program)
    scopes.register(study, project)

    catalog = ExecutionEnvironmentCatalog(scopes)
    base = EnvironmentSpec(
        "base",
        ExecutionEnvironmentKind.PYTHON,
        ws,
        requirements=(("python", "3.12"), ("torch", "2.6")),
    )
    sem = EnvironmentSpec(
        "sem",
        ExecutionEnvironmentKind.PYTHON,
        project,
        parent_spec_id="base",
        requirements=(("faiss", "1"),),
    )
    catalog.register_spec(base)
    catalog.register_spec(sem)
    catalog.assign(EnvironmentAssignment("method", "sem", project))
    catalog.register_overlay(EnvironmentOverlay("study-debug", "sem", study, requirements=(("debugpy", "1"),)))

    resolved = catalog.resolve("method", study)
    assert resolved.source_spec_ids == ("base", "sem")
    assert dict(resolved.requirements) == {"python": "3.12", "torch": "2.6", "faiss": "1", "debugpy": "1"}
    assert resolved.applied_overlay_ids == ("study-debug",)
