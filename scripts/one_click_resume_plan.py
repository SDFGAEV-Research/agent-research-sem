"""Generate the exact, non-degrading recovery sequence for an interrupted model run."""
from research_platform.platform.kernel import ImmutableModelIdentity
from research_platform.model.serving.api import ModelPhase, ModelRunState
from research_platform.model.serving.runtime import RecoveryPlanner


def main() -> None:
    identity = ImmutableModelIdentity(
        logical_name="qwen36_35b_a3b_primary",
        model_id="Qwen/Qwen3.6-35B-A3B",
        revision="PIN_EXACT_HF_COMMIT_BEFORE_DEPLOY",
        engine="sglang",
        engine_version="PIN_EXACT_STABLE_RELEASE",
        dtype="bfloat16",
        quantization=None,
        context_length=262144,
    )
    state = ModelRunState.initial("example_interrupted_run", identity).transition(ModelPhase.INVENTORY).transition(ModelPhase.PREPARE).transition(ModelPhase.INTERRUPTED)
    plan = RecoveryPlanner().plan(state, identity)
    for i, step in enumerate(plan.steps, 1):
        print(f"{i}. {step.value}")


if __name__ == "__main__":
    main()
