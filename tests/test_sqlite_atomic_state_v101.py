from research_platform.data.state.api import AggregateValue, AtomicMutation, StateCorruptionError, StateVersionConflict
from research_platform.data.state.runtime import SQLiteAtomicStateStore
import sqlite3
import tempfile
import unittest
from pathlib import Path



class SQLiteAtomicStateV101Tests(unittest.TestCase):
    def _path(self, td): return Path(td) / "state.sqlite3"

    def test_commit_survives_store_restart(self):
        with tempfile.TemporaryDirectory() as td:
            path=self._path(td)
            store=SQLiteAtomicStateStore(path,(AggregateValue("a",1,"g0","d0",{"x":0}),))
            out=store.commit_batch((AtomicMutation("a",1,"g0","g1","d1",{"x":1}),))
            self.assertEqual((out[0].version,out[0].generation),(2,"g1"))
            reopened=SQLiteAtomicStateStore(path)
            value=reopened.read("a")
            self.assertEqual((value.version,value.generation,value.payload),(2,"g1",{"x":1}))

    def test_batch_conflict_rolls_back_all_aggregates(self):
        with tempfile.TemporaryDirectory() as td:
            store=SQLiteAtomicStateStore(self._path(td),(
                AggregateValue("a",1,"g0","a0",{"x":0}),
                AggregateValue("b",1,"g0","b0",{"y":0}),
            ))
            with self.assertRaises(StateVersionConflict):
                store.commit_batch((
                    AtomicMutation("a",1,"g0","g1","a1",{"x":1}),
                    AtomicMutation("b",99,"g0","g1","b1",{"y":1}),
                ))
            self.assertEqual(store.read("a").generation,"g0")
            self.assertEqual(store.read("b").generation,"g0")

    def test_storage_checksum_detects_payload_corruption(self):
        with tempfile.TemporaryDirectory() as td:
            path=self._path(td)
            store=SQLiteAtomicStateStore(path,(AggregateValue("a",1,"g0","d0",{"x":0}),))
            with sqlite3.connect(path) as conn:
                conn.execute("UPDATE aggregates SET payload=? WHERE aggregate_id='a'",(b'{"x":999}',))
                conn.commit()
            with self.assertRaises(StateCorruptionError):
                store.read("a")


if __name__ == "__main__":
    unittest.main()
