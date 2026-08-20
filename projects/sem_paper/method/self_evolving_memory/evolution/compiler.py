from __future__ import annotations
import hashlib, json
from research_platform.platform.kernel import canonical_digest
from .contracts import CandidateArchitecture, EditKind, PrimitiveEdit, PrimitiveEditKind, StructuralIntent

class StructuralCompiler:
    """SPLIT/MERGE are semantic sugar; trusted execution sees CREATE/RETIRE only."""
    def __init__(self,target_builder): self.target_builder=target_builder
    def _primitive(self,intent:StructuralIntent)->tuple[PrimitiveEdit,...]:
        payload=intent.payload if isinstance(intent.payload,dict) else {}
        if intent.edit==EditKind.CREATE: return (PrimitiveEdit(PrimitiveEditKind.CREATE,str(payload.get("node_id","new_node")),payload.get("spec")),)
        if intent.edit==EditKind.RETIRE: return (PrimitiveEdit(PrimitiveEditKind.RETIRE,str(payload.get("node_id","node"))),)
        if intent.edit==EditKind.SPLIT:
            parent=str(payload.get("parent","node")); children=tuple(payload.get("children",()))
            if len(children)<2: raise ValueError("SPLIT requires at least two children")
            return tuple(PrimitiveEdit(PrimitiveEditKind.CREATE,str(x),None) for x in children)+(PrimitiveEdit(PrimitiveEditKind.RETIRE,parent),)
        if intent.edit==EditKind.MERGE:
            sources=tuple(payload.get("sources",())); target=str(payload.get("target","merged"))
            if len(sources)<2: raise ValueError("MERGE requires at least two sources")
            return (PrimitiveEdit(PrimitiveEditKind.CREATE,target,None),)+tuple(PrimitiveEdit(PrimitiveEditKind.RETIRE,str(x)) for x in sources)
        raise ValueError("NO_EDIT cannot be compiled")
    def compile(self,intent:StructuralIntent,base_generation:str)->CandidateArchitecture:
        edits=self._primitive(intent); target_spec,contracts=self.target_builder(base_generation,edits,intent)
        digest=canonical_digest(target_spec)
        cid="candidate_"+hashlib.sha256((base_generation+digest+intent.edit.value).encode()).hexdigest()[:20]
        return CandidateArchitecture(base_generation,cid,target_spec,digest,edits,tuple(contracts))

class OperationalVerifier:
    """Operational safety only; never semantic utility or acceptance."""
    def verify(self,candidate:CandidateArchitecture)->None:
        if not candidate.primitive_edits: raise ValueError("candidate has no primitive edits")
        if any(e.kind not in {PrimitiveEditKind.CREATE,PrimitiveEditKind.RETIRE} for e in candidate.primitive_edits): raise ValueError("unsupported primitive edit")
        if not candidate.materialization_contracts: raise ValueError("candidate must provide complete target materialization plan")
