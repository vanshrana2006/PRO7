"""
Offline tests for reference-to-corpus citation matching.

Run with:  python3 -m unittest tests.test_citation_matcher -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.citation_matcher import (  # noqa: E402
    CorpusPaper,
    match_references_to_corpus,
    normalize_title,
)

CORPUS = [
    CorpusPaper(paper_id="p1", title="Semi-Supervised Classification with Graph Convolutional Networks"),
    CorpusPaper(paper_id="p2", title="Graph Attention Networks"),
    CorpusPaper(paper_id="p3", title="Inductive Representation Learning on Large Graphs"),
]


class TestNormalizeTitle(unittest.TestCase):
    def test_lowercases_and_strips_punctuation(self):
        self.assertEqual(normalize_title("Graph Attention Networks!"), "graph attention networks")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_title("Graph   Attention\nNetworks"), "graph attention networks")


class TestMatchReferencesToCorpus(unittest.TestCase):
    def test_matches_reference_containing_full_title(self):
        references = [
            ("ref1", "Kipf, T. and Welling, M. Semi-Supervised Classification with Graph Convolutional Networks. ICLR 2017."),
        ]
        matches = match_references_to_corpus(references, CORPUS)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].cited_paper_id, "p1")
        self.assertEqual(matches[0].reference_id, "ref1")

    def test_matches_multiple_references_to_different_papers(self):
        references = [
            ("ref1", "Velickovic, P. et al. Graph Attention Networks. ICLR 2018."),
            ("ref2", "Hamilton, W. Inductive Representation Learning on Large Graphs. NeurIPS 2017."),
        ]
        matches = match_references_to_corpus(references, CORPUS)
        cited_ids = {m.cited_paper_id for m in matches}
        self.assertEqual(cited_ids, {"p2", "p3"})

    def test_no_match_for_unrelated_reference(self):
        references = [("ref1", "Smith, J. A completely unrelated paper about cooking. 2020.")]
        matches = match_references_to_corpus(references, CORPUS)
        self.assertEqual(matches, [])

    def test_confidence_is_between_0_and_1(self):
        references = [("ref1", "Velickovic, P. et al. Graph Attention Networks. ICLR 2018.")]
        matches = match_references_to_corpus(references, CORPUS)
        self.assertTrue(0.0 <= matches[0].match_confidence <= 1.0)

    def test_short_titles_are_excluded_to_avoid_false_positives(self):
        short_corpus = [CorpusPaper(paper_id="short", title="On Graphs")]
        references = [("ref1", "This reference happens to mention graphs in passing.")]
        matches = match_references_to_corpus(references, short_corpus, min_title_length=15)
        self.assertEqual(matches, [])

    def test_case_and_punctuation_insensitive_matching(self):
        references = [("ref1", "GRAPH ATTENTION NETWORKS: a new approach, 2018")]
        matches = match_references_to_corpus(references, CORPUS)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].cited_paper_id, "p2")

    def test_empty_references_returns_empty(self):
        self.assertEqual(match_references_to_corpus([], CORPUS), [])

    def test_empty_corpus_returns_empty(self):
        references = [("ref1", "Some reference text.")]
        self.assertEqual(match_references_to_corpus(references, []), [])


if __name__ == "__main__":
    unittest.main()
