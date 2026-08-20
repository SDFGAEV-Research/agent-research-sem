from __future__ import annotations

from dataclasses import dataclass
from threading import Condition
import time


class ModelAdmissionTimeout(TimeoutError): pass


@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    capacity: int
    active: int
    waiting: int


class AdmissionLease:
    def __init__(self, controller: "ModelAdmissionController") -> None:
        self._controller=controller; self._released=False
    def release(self)->None:
        if not self._released:
            self._released=True; self._controller._release()
    def __enter__(self): return self
    def __exit__(self,exc_type,exc,tb): self.release()


class ModelAdmissionController:
    """Backpressure only. Saturation never changes model, precision, prompt, context or output budget."""
    def __init__(self,qualified_capacity:int) -> None:
        if qualified_capacity<=0: raise ValueError("qualified capacity must be positive")
        self.capacity=qualified_capacity; self._active=0; self._waiting=0; self._cv=Condition()

    def acquire(self,timeout_seconds:float|None=None)->AdmissionLease:
        deadline=None if timeout_seconds is None else time.monotonic()+timeout_seconds
        with self._cv:
            self._waiting+=1
            try:
                while self._active>=self.capacity:
                    remaining=None if deadline is None else deadline-time.monotonic()
                    if remaining is not None and remaining<=0: raise ModelAdmissionTimeout("model admission timed out; no quality fallback was attempted")
                    self._cv.wait(remaining)
                self._active+=1
                return AdmissionLease(self)
            finally:
                self._waiting-=1

    def _release(self)->None:
        with self._cv:
            if self._active<=0: raise RuntimeError("admission lease underflow")
            self._active-=1; self._cv.notify()

    def snapshot(self)->AdmissionSnapshot:
        with self._cv: return AdmissionSnapshot(self.capacity,self._active,self._waiting)
