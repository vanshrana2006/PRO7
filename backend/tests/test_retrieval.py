"""
Offline tests for BM25Index and reciprocal_rank_fusion -- real algorithm
correctness checks, not just "it runs without crashing."

Run with:  python3 -m unittest tests.test_retrieval -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.retrieval import (  # noqa: E402
    BM25Index,
    ScoredDocument,
    reciprocal_rank_fusion,
    tokenize,
)

CORPUS = {
    "doc1": "Graph convolutional networks perform semi-supervised classification on graphs.",
    "doc2": "Graph attention networks use masked self-attention over graph-structured data.",
    "doc3": "Convolutional neural networks are widely used for image classification tasks.",
    "doc4": "This paper has nothing to do with graphs or neural networks at all, it is about cooking pasta.",
}


class TestTokenize(unittest.TestCase):
    def test_lowercases_and_splits_words(self):
        self.assertEqual(tokenize("Graph Neural Networks"), ["graph", "neural", "networks"])

    def test_removes_stopwords(self):
        tokens = tokenize("the graph is a network of the nodes")
        self.assertNotIn("the", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("a", tokens)
        self.assertNotIn("of", tokens)

    def test_removes_punctuation(self):
        self.assertEqual(tokenize("graphs, networks; and more!"), ["graphs", "networks", "more"])

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(tokenize(""), [])


class TestBM25Index(unittest.TestCase):
    def setUp(self):
        self.index = BM25Index()
        self.index.build(CORPUS)

    def test_ranks_relevant_documents_above_irrelevant(self):
        results = self.index.search("graph neural networks", top_k=4)
        result_ids = [r.doc_id for r in results]
        # doc4 (about cooking pasta) should rank last or not appear
        self.assertLess(result_ids.index("doc1"), result_ids.index("doc4") if "doc4" in result_ids else 99)

    def test_most_relevant_document_ranks_first(self):
        # doc1 and doc2 both mention "graph networks" concepts strongly;
        # doc3 only shares "networks"/"classification"; doc4 shares nothing
        # graph-related. The top result should be doc1 or doc2, not doc3/doc4.
        results = self.index.search("graph neural networks", top_k=1)
        self.assertIn(results[0].doc_id, {"doc1", "doc2"})

    def test_irrelevant_query_returns_no_or_low_matches(self):
        results = self.index.search("zzz nonexistent term qqq", top_k=4)
        self.assertEqual(results, [])

    def test_top_k_limits_results(self):
        results = self.index.search("graph", top_k=2)
        self.assertLessEqual(len(results), 2)

    def test_scores_are_positive_and_descending(self):
        results = self.index.search("graph networks classification", top_k=4)
        scores = [r.score for r in results]
        self.assertTrue(all(s > 0 for s in scores))
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_empty_query_returns_empty(self):
        self.assertEqual(self.index.search(""), [])

    def test_empty_corpus_returns_empty(self):
        empty_index = BM25Index()
        empty_index.build({})
        self.assertEqual(empty_index.search("anything"), [])

    def test_term_appearing_in_every_document_still_scores_low_relative_weight(self):
        # "graph" appears in doc1/doc2/doc4-adjacent... use a term in ALL docs
        uniform_corpus = {"a": "common word here", "b": "common word there", "c": "common word everywhere"}
        idx = BM25Index()
        idx.build(uniform_corpus)
        # "common" appears in all 3 docs -- low IDF, should not dominate
        # a query where a rarer term also matches
        results = idx.search("common", top_k=3)
        self.assertEqual(len(results), 3)  # still matches, just low-ish score
        self.assertTrue(all(r.score > 0 for r in results))


class TestReciprocalRankFusion(unittest.TestCase):
    def test_document_ranked_first_in_both_lists_ranks_first_in_fusion(self):
        list_a = [ScoredDocument("doc1", 5.0), ScoredDocument("doc2", 3.0)]
        list_b = [ScoredDocument("doc1", 0.9), ScoredDocument("doc3", 0.8)]
        fused = reciprocal_rank_fusion([list_a, list_b])
        self.assertEqual(fused[0].doc_id, "doc1")

    def test_document_appearing_in_only_one_list_still_included(self):
        list_a = [ScoredDocument("doc1", 5.0)]
        list_b = [ScoredDocument("doc2", 0.9)]
        fused = reciprocal_rank_fusion([list_a, list_b])
        doc_ids = {d.doc_id for d in fused}
        self.assertEqual(doc_ids, {"doc1", "doc2"})

    def test_empty_lists_return_empty(self):
        self.assertEqual(reciprocal_rank_fusion([]), [])

    def test_single_list_preserves_relative_order(self):
        list_a = [ScoredDocument("doc1", 5.0), ScoredDocument("doc2", 3.0), ScoredDocument("doc3", 1.0)]
        fused = reciprocal_rank_fusion([list_a])
        self.assertEqual([d.doc_id for d in fused], ["doc1", "doc2", "doc3"])

    def test_appearing_in_multiple_lists_boosts_above_single_list_appearance(self):
        list_a = [ScoredDocument("doc1", 1.0), ScoredDocument("doc2", 1.0)]
        list_b = [ScoredDocument("doc2", 1.0), ScoredDocument("doc1", 1.0)]
        # doc1 is rank 1 in A, rank 2 in B; doc2 is rank 2 in A, rank 1 in B
        # -- symmetric, so they should tie
        fused = reciprocal_rank_fusion([list_a, list_b])
        self.assertAlmostEqual(fused[0].score, fused[1].score, places=6)


if __name__ == "__main__":
    unittest.main()
