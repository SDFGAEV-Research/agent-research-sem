import unittest
from research_platform.platform.kernel import ImmutableModelIdentity
from research_platform.model.serving import ModelPhase, ModelRunState


class ModelStateTests(unittest.TestCase):
    def setUp(self):
        self.i = ImmutableModelIdentity("m","id","rev","sglang","v","bfloat16",None,262144)

    def test_happy_path(self):
        s = ModelRunState.initial("r", self.i, "d"*64)
        for p in (ModelPhase.INVENTORY, ModelPhase.PREPARE, ModelPhase.LOAD, ModelPhase.WARMUP, ModelPhase.READY, ModelPhase.RUNNING, ModelPhase.DRAINING, ModelPhase.STOPPING, ModelPhase.STOPPED):
            s = s.transition(p)
        self.assertEqual(s.phase, ModelPhase.STOPPED)

    def test_illegal_skip_fails(self):
        s = ModelRunState.initial("r", self.i, "d"*64)
        with self.assertRaises(ValueError):
            s.transition(ModelPhase.RUNNING)

if __name__ == "__main__":
    unittest.main()
