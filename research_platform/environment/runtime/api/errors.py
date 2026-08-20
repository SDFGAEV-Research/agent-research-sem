class ActionRecoveryRequired(RuntimeError):
    """An external action cannot be safely continued without authoritative reconciliation."""


class ActionNotApplied(ActionRecoveryRequired):
    """Reconciliation proved the intended external action was not applied."""


class ActionSafetyCapabilityMissing(RuntimeError):
    """Crash-safe action execution was requested but the Environment lacks a required recovery capability."""


class ActionScientificCommitContradiction(ActionRecoveryRequired):
    """Method commit proof contradicts authoritative external-action reconciliation."""
