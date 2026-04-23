import unittest

from acai.ai_hybrid_search.adapters.outbound.rrf_hybrid_search import (
    RRFConfig,
    RRFHybridSearchAdapter,
)
from acai.ai_hybrid_search.domain.exceptions import HybridSearchError
from acai.ai_hybrid_search.domain.hybrid_search_result import HybridSearchResult


# ---------------------------------------------------------------------------
# Stub logger for tests
# ---------------------------------------------------------------------------
class _StubLogger:
    def info(self, msg, **kw):
        pass

    def debug(self, msg, **kw):
        pass

    def warning(self, msg, **kw):
        pass

    def error(self, msg, **kw):
        pass


# ---------------------------------------------------------------------------
# Domain value objects
# ---------------------------------------------------------------------------
class TestHybridSearchResult(unittest.TestCase):
    def test_defaults(self):
        r = HybridSearchResult(record_id="1", content="hello")
        self.assertEqual(r.record_id, "1")
        self.assertEqual(r.content, "hello")
        self.assertEqual(r.semantic_score, 0.0)
        self.assertEqual(r.text_score, 0.0)
        self.assertEqual(r.hybrid_score, 0.0)
        self.assertEqual(r.metadata, {})

    def test_frozen(self):
        r = HybridSearchResult(record_id="1", content="x")
        with self.assertRaises(AttributeError):
            r.record_id = "2"

    def test_metadata(self):
        r = HybridSearchResult(record_id="1", content="x", metadata={"k": "v"})
        self.assertEqual(r.metadata["k"], "v")


class TestHybridSearchError(unittest.TestCase):
    def test_is_exception(self):
        self.assertTrue(issubclass(HybridSearchError, Exception))

    def test_message(self):
        err = HybridSearchError("boom")
        self.assertEqual(str(err), "boom")


# ---------------------------------------------------------------------------
# RRFConfig
# ---------------------------------------------------------------------------
class TestRRFConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = RRFConfig()
        self.assertEqual(cfg.k, 60)
        self.assertEqual(cfg.semantic_weight, 1.0)
        self.assertEqual(cfg.text_weight, 1.0)
        self.assertEqual(cfg.fetch_multiplier, 3)

    def test_frozen(self):
        cfg = RRFConfig()
        with self.assertRaises(AttributeError):
            cfg.k = 99

    def test_custom_values(self):
        cfg = RRFConfig(k=40, semantic_weight=0.7, text_weight=0.3, fetch_multiplier=5)
        self.assertEqual(cfg.k, 40)
        self.assertEqual(cfg.semantic_weight, 0.7)
        self.assertEqual(cfg.text_weight, 0.3)
        self.assertEqual(cfg.fetch_multiplier, 5)


# ---------------------------------------------------------------------------
# RRFHybridSearchAdapter
# ---------------------------------------------------------------------------
def _make_semantic_fn(hits):
    """Return a callable that returns *hits* regardless of input."""

    def fn(vector, top_k):
        return hits[:top_k]

    return fn


def _make_text_fn(hits):
    def fn(query, top_k):
        return hits[:top_k]

    return fn


class TestRRFSearch(unittest.TestCase):
    def test_empty_sources(self):
        adapter = RRFHybridSearchAdapter(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn([]),
            text_search_fn=_make_text_fn([]),
        )
        results = adapter.search("hello", [0.1, 0.2], top_k=5)
        self.assertEqual(results, [])

    def test_only_semantic_hits(self):
        sem_hits = [
            ("doc1", "content1", 0.9, {"src": "sem"}),
            ("doc2", "content2", 0.7, {}),
        ]
        adapter = RRFHybridSearchAdapter(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn(sem_hits),
            text_search_fn=_make_text_fn([]),
        )
        results = adapter.search("query", [0.1], top_k=5)
        self.assertEqual(len(results), 2)
        # doc1 should rank higher (rank 1 in semantic)
        self.assertEqual(results[0].record_id, "doc1")
        self.assertGreater(results[0].hybrid_score, results[1].hybrid_score)

    def test_only_text_hits(self):
        txt_hits = [
            ("docA", "textA", 5.0, {"src": "txt"}),
            ("docB", "textB", 3.0, {}),
        ]
        adapter = RRFHybridSearchAdapter(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn([]),
            text_search_fn=_make_text_fn(txt_hits),
        )
        results = adapter.search("query", [0.1], top_k=5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].record_id, "docA")

    def test_overlapping_hits_merged(self):
        sem_hits = [
            ("shared", "sem_content", 0.9, {"a": 1}),
            ("sem_only", "only_sem", 0.5, {}),
        ]
        txt_hits = [
            ("shared", "txt_content", 4.0, {"b": 2}),
            ("txt_only", "only_txt", 2.0, {}),
        ]
        adapter = RRFHybridSearchAdapter(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn(sem_hits),
            text_search_fn=_make_text_fn(txt_hits),
        )
        results = adapter.search("query", [0.1], top_k=10)
        ids = {r.record_id for r in results}
        self.assertEqual(ids, {"shared", "sem_only", "txt_only"})

        # "shared" should have highest hybrid_score (appears in both lists)
        shared = [r for r in results if r.record_id == "shared"][0]
        self.assertEqual(results[0].record_id, "shared")
        # Metadata should be merged
        self.assertEqual(shared.metadata["a"], 1)
        self.assertEqual(shared.metadata["b"], 2)

    def test_top_k_limits_results(self):
        sem_hits = [(f"d{i}", f"c{i}", 0.9 - i * 0.1, {}) for i in range(10)]
        adapter = RRFHybridSearchAdapter(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn(sem_hits),
            text_search_fn=_make_text_fn([]),
        )
        results = adapter.search("q", [0.1], top_k=3)
        self.assertEqual(len(results), 3)

    def test_text_scores_normalized(self):
        """Text scores should be normalized to [0, 1] via max-norm."""
        txt_hits = [
            ("d1", "c1", 10.0, {}),
            ("d2", "c2", 5.0, {}),
        ]
        adapter = RRFHybridSearchAdapter(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn([]),
            text_search_fn=_make_text_fn(txt_hits),
        )
        results = adapter.search("q", [0.1], top_k=5)
        for r in results:
            self.assertLessEqual(r.text_score, 1.0)
            self.assertGreaterEqual(r.text_score, 0.0)

    def test_custom_weights(self):
        sem_hits = [("d1", "c1", 0.9, {})]
        txt_hits = [("d2", "c2", 5.0, {})]
        cfg = RRFConfig(k=60, semantic_weight=0.0, text_weight=1.0)
        adapter = RRFHybridSearchAdapter(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn(sem_hits),
            text_search_fn=_make_text_fn(txt_hits),
            config=cfg,
        )
        results = adapter.search("q", [0.1], top_k=5)
        d1 = [r for r in results if r.record_id == "d1"][0]
        # semantic_weight=0 => d1 (only in semantic) should have hybrid_score == 0
        self.assertAlmostEqual(d1.hybrid_score, 0.0)

    def test_results_sorted_descending(self):
        sem_hits = [(f"d{i}", f"c{i}", 0.9 - i * 0.1, {}) for i in range(5)]
        txt_hits = [(f"d{i}", f"c{i}", 5.0 - i, {}) for i in range(5)]
        adapter = RRFHybridSearchAdapter(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn(sem_hits),
            text_search_fn=_make_text_fn(txt_hits),
        )
        results = adapter.search("q", [0.1], top_k=5)
        scores = [r.hybrid_score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
class TestFactory(unittest.TestCase):
    def test_create_hybrid_search_returns_port(self):
        from acai.ai_hybrid_search import create_hybrid_search
        from acai.ai_hybrid_search.ports import HybridSearchPort

        hs = create_hybrid_search(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn([]),
            text_search_fn=_make_text_fn([]),
        )
        self.assertIsInstance(hs, HybridSearchPort)

    def test_factory_weight_derivation(self):
        """text_weight should be 1 - semantic_weight."""
        from acai.ai_hybrid_search import create_hybrid_search

        hs = create_hybrid_search(
            logger=_StubLogger(),
            semantic_search_fn=_make_semantic_fn([]),
            text_search_fn=_make_text_fn([]),
            semantic_weight=0.7,
        )
        # Access the internal config
        self.assertAlmostEqual(hs._config.semantic_weight, 0.7)
        self.assertAlmostEqual(hs._config.text_weight, 0.3)


if __name__ == "__main__":
    unittest.main()
