class StateVersionConflict(RuntimeError):
    pass

class StateCorruptionError(RuntimeError):
    pass

__all__=["StateCorruptionError","StateVersionConflict"]
