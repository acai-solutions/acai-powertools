import unittest

from acai.ai_tools.bm25_index import BM25Index


class TestBM25IndexInit(unittest.TestCase):
    def test_default_params(self):
        idx = BM25Index()
        self.assertEqual(idx.k1, 1.5)
        self.assertEqual(idx.b, 0.75)
        self.assertEqual(len(idx), 0)

    def test_custom_params(self):
        idx = BM25Index(k1=2.0, b=0.5)
        self.assertEqual(idx.k1, 2.0)
        self.assertEqual(idx.b, 0.5)

    def test_repr(self):
        idx = BM25Index()
        self.assertIn("BM25VectorStore", repr(idx))
        self.assertIn("count=0", repr(idx))
        self.assertIn("index_built=False", repr(idx))


class TestAddDocument(unittest.TestCase):
    def test_add_valid_document(self):
        idx = BM25Index()
        idx.add_document({"content": "hello world"})
        self.assertEqual(len(idx), 1)

    def test_add_multiple_documents(self):
        idx = BM25Index()
        idx.add_document({"content": "first document"})
        idx.add_document({"content": "second document"})
        self.assertEqual(len(idx), 2)

    def test_add_document_with_extra_fields(self):
        idx = BM25Index()
        idx.add_document({"content": "hello", "id": "123", "meta": {"key": "val"}})
        self.assertEqual(len(idx), 1)

    def test_add_non_dict_raises_type_error(self):
        idx = BM25Index()
        with self.assertRaises(TypeError):
            idx.add_document("not a dict")

    def test_add_missing_content_raises_value_error(self):
        idx = BM25Index()
        with self.assertRaises(ValueError):
            idx.add_document({"title": "no content"})

    def test_add_non_string_content_raises_type_error(self):
        idx = BM25Index()
        with self.assertRaises(TypeError):
            idx.add_document({"content": 123})


class TestDefaultTokenizer(unittest.TestCase):
    def test_lowercase_and_split(self):
        idx = BM25Index()
        tokens = idx._default_tokenizer("Hello World! Foo-Bar")
        self.assertEqual(tokens, ["hello", "world", "foo", "bar"])

    def test_empty_string(self):
        idx = BM25Index()
        tokens = idx._default_tokenizer("")
        self.assertEqual(tokens, [])


class TestCustomTokenizer(unittest.TestCase):
    def test_custom_tokenizer_is_used(self):
        def custom(text):
            return text.split(",")

        idx = BM25Index(tokenizer=custom)
        idx.add_document({"content": "a,b,c"})
        self.assertEqual(idx._corpus_tokens[0], ["a", "b", "c"])


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.idx = BM25Index()
        self.idx.add_document({"content": "the quick brown fox", "id": "1"})
        self.idx.add_document({"content": "the lazy brown dog", "id": "2"})
        self.idx.add_document(
            {"content": "quick fox jumped over the lazy dog", "id": "3"}
        )

    def test_search_returns_relevant_results(self):
        results = self.idx.search("quick fox", k=3)
        self.assertGreater(len(results), 0)
        # All results should be (doc, score) tuples
        for doc, score in results:
            self.assertIsInstance(doc, dict)
            self.assertIsInstance(score, float)

    def test_search_top_result_for_exact_match(self):
        results = self.idx.search("quick brown fox", k=1)
        self.assertEqual(len(results), 1)
        doc, _ = results[0]
        self.assertEqual(doc["id"], "1")

    def test_search_k_limits_results(self):
        results = self.idx.search("the", k=2)
        self.assertLessEqual(len(results), 2)

    def test_search_empty_index(self):
        empty = BM25Index()
        results = empty.search("anything")
        self.assertEqual(results, [])

    def test_search_no_match(self):
        results = self.idx.search("zzzznotaword", k=3)
        self.assertEqual(results, [])

    def test_search_non_string_query_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.idx.search(123)

    def test_search_k_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.idx.search("fox", k=0)

    def test_search_k_negative_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.idx.search("fox", k=-1)

    def test_scores_are_normalized(self):
        """Normalized scores should be between 0 and 1 (exponential decay)."""
        results = self.idx.search("quick fox", k=3)
        for _, score in results:
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_scores_sorted_ascending(self):
        """Results are sorted by normalized score ascending (lower = better)."""
        results = self.idx.search("quick fox", k=3)
        scores = [s for _, s in results]
        self.assertEqual(scores, sorted(scores))


class TestSearchNormalization(unittest.TestCase):
    def test_normalization_factor_affects_scores(self):
        idx = BM25Index()
        idx.add_document({"content": "apple banana cherry"})
        results_default = idx.search("apple", k=1, score_normalization_factor=0.1)
        results_high = idx.search("apple", k=1, score_normalization_factor=1.0)
        # Higher normalization factor should produce lower score
        self.assertGreater(results_default[0][1], results_high[0][1])


if __name__ == "__main__":
    unittest.main()
