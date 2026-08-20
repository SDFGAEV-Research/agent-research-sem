from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from research_platform.platform.kernel import ExecutionContext
from .contracts import LifecycleComponent, LifecycleEvidence, LifecyclePhase, LifecycleSpec


class LifecycleGraphError(RuntimeError): pass


@dataclass(frozen=True, slots=True)
class RollbackFailure:
    component_id: str
    error_type: str
    error: str


class LifecycleStartError(RuntimeError):
    def __init__(self, component_id: str, cause: BaseException, started: tuple[str,...], rollback_failures: tuple[RollbackFailure,...]):
        super().__init__(f"component start failed: {component_id}: {type(cause).__name__}: {cause}")
        self.component_id=component_id; self.cause=cause; self.started=started; self.rollback_failures=rollback_failures


class LifecycleStopError(RuntimeError):
    def __init__(self, failures: tuple[RollbackFailure,...]):
        super().__init__(f"component stop failures: {len(failures)}")
        self.failures=failures


@dataclass(frozen=True, slots=True)
class LifecycleRunReport:
    start_order: tuple[str,...]
    evidence: tuple[LifecycleEvidence,...]


class LifecycleManager:
    """Dependency-solved lifecycle manager. Graph validity is proven before any component side effect."""

    def __init__(self, components: Iterable[LifecycleComponent]) -> None:
        items=tuple(components); mapping={x.lifecycle_spec.component_id:x for x in items}
        if len(mapping)!=len(items): raise LifecycleGraphError("duplicate lifecycle component id")
        self.components=mapping
        self.order=self._topological_order(tuple(x.lifecycle_spec for x in items))

    @staticmethod
    def _topological_order(specs: tuple[LifecycleSpec,...]) -> tuple[str,...]:
        ids={x.component_id for x in specs}
        for spec in specs:
            missing=set(spec.depends_on)-ids
            if missing: raise LifecycleGraphError(f"component {spec.component_id} missing dependencies: {sorted(missing)}")
        deps={x.component_id:set(x.depends_on) for x in specs}; order=[]
        while deps:
            ready=sorted(k for k,v in deps.items() if not v)
            if not ready:
                cycle=sorted(deps)
                raise LifecycleGraphError(f"lifecycle dependency cycle among: {cycle}")
            order.extend(ready)
            for key in ready: deps.pop(key)
            for value in deps.values(): value.difference_update(ready)
        return tuple(order)

    def start_all(self, context: ExecutionContext) -> LifecycleRunReport:
        started=[]; evidence=[]
        for cid in self.order:
            component=self.components[cid]
            evidence.append(LifecycleEvidence(cid,LifecyclePhase.STARTING))
            try:
                refs=tuple(component.start(context.child(span_id=f"lifecycle:start:{cid}",component_id=cid)))
            except Exception as exc:
                rollback=[]
                for previous in reversed(started):
                    try: self.components[previous].stop(context.child(span_id=f"lifecycle:rollback:{previous}",component_id=previous))
                    except Exception as rb: rollback.append(RollbackFailure(previous,type(rb).__name__,str(rb)))
                raise LifecycleStartError(cid,exc,tuple(started),tuple(rollback)) from exc
            started.append(cid); evidence.append(LifecycleEvidence(cid,LifecyclePhase.READY,refs))
        return LifecycleRunReport(self.order,tuple(evidence))

    def stop_all(self, context: ExecutionContext) -> tuple[LifecycleEvidence,...]:
        evidence=[]; failures=[]
        for cid in reversed(self.order):
            evidence.append(LifecycleEvidence(cid,LifecyclePhase.STOPPING))
            try: refs=tuple(self.components[cid].stop(context.child(span_id=f"lifecycle:stop:{cid}",component_id=cid)))
            except Exception as exc:
                failures.append(RollbackFailure(cid,type(exc).__name__,str(exc))); evidence.append(LifecycleEvidence(cid,LifecyclePhase.FAILED))
            else: evidence.append(LifecycleEvidence(cid,LifecyclePhase.STOPPED,refs))
        if failures: raise LifecycleStopError(tuple(failures))
        return tuple(evidence)
