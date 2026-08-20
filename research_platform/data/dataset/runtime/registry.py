from __future__ import annotations
from research_platform.data.dataset.api import DatasetIdentity, DatasetQuery, DatasetVersion
class InMemoryDatasetRegistry:
    def __init__(self)->None: self._rows: dict[DatasetIdentity,DatasetVersion]={}
    def register(self,dataset:DatasetVersion)->None:
        current=self._rows.get(dataset.identity)
        if current is not None and current != dataset: raise ValueError(f"dataset version already fixed: {dataset.identity.key}")
        self._rows[dataset.identity]=dataset
    def get(self,identity:DatasetIdentity)->DatasetVersion:
        try:return self._rows[identity]
        except KeyError as exc: raise KeyError(identity.key) from exc
    def query(self,query:DatasetQuery=DatasetQuery())->tuple[DatasetVersion,...]:
        rows=(x for x in self._rows.values() if (query.dataset_id is None or x.identity.dataset_id==query.dataset_id) and (query.scope is None or x.scope==query.scope) and (query.tag is None or query.tag in x.tags))
        return tuple(sorted(rows,key=lambda x:x.identity.key))
