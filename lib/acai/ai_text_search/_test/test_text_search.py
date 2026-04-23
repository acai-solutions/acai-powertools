import unittest

from acai.ai_text_search.domain.exceptions import ConfigurationError, TextSearchError
from acai.ai_text_search.domain.text_search_config import TextSearchConfig
from acai.ai_text_search.domain.text_search_result import TextSearchResult
from acai.ai_text_search.ports.text_search_port import TextSearchPort


# ---------------------------------------------------------------------------
# TextSearchResult (frozen dataclass)
# ---------------------------------------------------------------------------
class TestTextSearchResult(unittest.TestCase):
    def test_creation(self):
        r = TextSearchResult(record_id="abc", content="hello", score=0.95)
        self.assertEqual(r.record_id, "abc")
        self.assertEqual(r.content, "hello")
        self.assertAlmostEqual(r.score, 0.95)
        self.assertEqual(r.metadata, {})

    def test_with_metadata(self):
        r = TextSearchResult(
            record_id="1", content="x", score=0.5, metadata={"law": "OR"}
        )
        self.assertEqual(r.metadata["law"], "OR")

    def test_frozen(self):
        r = TextSearchResult(record_id="1", content="x", score=0.5)
        with self.assertRaises(AttributeError):
            r.record_id = "2"

    def test_equality(self):
        r1 = TextSearchResult(record_id="1", content="x", score=0.5)
        r2 = TextSearchResult(record_id="1", content="x", score=0.5)
        self.assertEqual(r1, r2)

    def test_inequality(self):
        r1 = TextSearchResult(record_id="1", content="x", score=0.5)
        r2 = TextSearchResult(record_id="2", content="x", score=0.5)
        self.assertNotEqual(r1, r2)


# ---------------------------------------------------------------------------
# TextSearchConfig (frozen dataclass)
# ---------------------------------------------------------------------------
class TestTextSearchConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = TextSearchConfig()
        self.assertEqual(cfg.language, "german")
        self.assertEqual(cfg.table, "app.law_embeddings")
        self.assertEqual(cfg.content_column, "embedding_text")
        self.assertEqual(cfg.id_column, "external_id")

    def test_custom_values(self):
        cfg = TextSearchConfig(
            language="english",
            table="public.docs",
            content_column="body",
            id_column="doc_id",
        )
        self.assertEqual(cfg.language, "english")
        self.assertEqual(cfg.table, "public.docs")

    def test_frozen(self):
        cfg = TextSearchConfig()
        with self.assertRaises(AttributeError):
            cfg.language = "french"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class TestExceptions(unittest.TestCase):
    def test_text_search_error(self):
        self.assertTrue(issubclass(TextSearchError, Exception))

    def test_configuration_error_is_subclass(self):
        self.assertTrue(issubclass(ConfigurationError, TextSearchError))

    def test_message(self):
        err = ConfigurationError("bad config")
        self.assertEqual(str(err), "bad config")


# ---------------------------------------------------------------------------
# Port contract (abstract)
# ---------------------------------------------------------------------------
class TestTextSearchPort(unittest.TestCase):
    def test_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            TextSearchPort()

    def test_concrete_implementation(self):
        class DummySearch(TextSearchPort):
            def search(self, query_text, *, top_k=10):
                return []

            def close(self):
                pass

        searcher = DummySearch()
        self.assertEqual(searcher.search("query"), [])


if __name__ == "__main__":
    unittest.main()
