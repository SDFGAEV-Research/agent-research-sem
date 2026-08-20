from __future__ import annotations

from tests_support import build_fixed_memory_method, build_self_evolving_memory_method

from research_platform.participant.method.runtime import InMemoryMethodObservationSink

from tests_support import build_fixed_memory_method

import unittest

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import MethodServices, RecallRequest



class SEMHybridRetrievalV174Tests(unittest.TestCase):
    def _session(self):
        return build_fixed_memory_method().open_session(
            session_id="s",
            services=MethodServices(InMemoryMethodObservationSink()),
        )

    def test_relevant_older_evidence_beats_unrelated_latest_evidence(self) -> None:
        session = self._session()
        context = ExecutionContext("run", "trace", "span")
        session.ingest({"topic": "hydraulic pressure anomaly", "note": "sand plug pressure rise"}, context)
        session.ingest({"topic": "weather", "note": "sunny afternoon"}, context)
        session.ingest({"topic": "unrelated latest", "note": "coffee"}, context)
        result = session.recall(RecallRequest("sand plug pressure", context, limit=1))
        self.assertIn("sand plug pressure rise", result.context_text)
        self.assertNotIn("coffee", result.context_text)

    def test_recall_limit_is_a_hard_planner_and_serving_budget(self) -> None:
        session = self._session()
        context = ExecutionContext("run", "trace", "span")
        for value in range(6):
            session.ingest({"topic": "pressure", "value": value}, context)
        result = session.recall(RecallRequest("pressure", context, limit=2))
        self.assertEqual(len(result.context_text.splitlines()), 2)
        self.assertIn('"value":5', result.context_text)
        self.assertIn('"value":4', result.context_text)

    def test_no_match_falls_back_to_latest_only(self) -> None:
        session = self._session()
        context = ExecutionContext("run", "trace", "span")
        session.ingest({"known": "alpha"}, context)
        session.ingest({"known": "beta"}, context)
        result = session.recall(RecallRequest("totally-unseen-query", context, limit=8))
        self.assertEqual(result.context_text, '{"known":"beta"}')

    def test_cjk_bigram_features_match_short_query_inside_longer_phrase(self) -> None:
        session = self._session()
        context = ExecutionContext("run", "trace", "span")
        session.ingest({"note": "水力压裂砂堵风险预警模型"}, context)
        session.ingest({"note": "完全无关内容"}, context)
        result = session.recall(RecallRequest("砂堵预警", context, limit=1))
        self.assertIn("砂堵风险预警模型", result.context_text)


if __name__ == "__main__":
    unittest.main()
