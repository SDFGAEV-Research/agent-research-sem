class ActionRecoveryRequired(RuntimeError):
    """An external action cannot continue without authoritative reconciliation."""


class ActionNotApplied(ActionRecoveryRequired):
    """Reconciliation proved that the intended external action was not applied."""


class ActionSafetyCapabilityMissing(RuntimeError):
    """Crash-safe action execution lacks a required recovery capability."""


class ActionScientificCommitContradiction(ActionRecoveryRequired):
    """Method commit proof contradicts authoritative action reconciliation."""


__all__ = [
    "ActionNotApplied",
    "ActionRecoveryRequired",
    "ActionSafetyCapabilityMissing",
    "ActionScientificCommitContradiction",
]
