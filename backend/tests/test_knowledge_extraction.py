"""
Offline tests for heuristic knowledge extraction.

Uses realistic paper-shaped text (loosely based on the GCN/GAT papers) to
verify method/dataset/metric/claim detection actually works, not just that
the functions run without crashing.

Run with:  python3 -m unittest tests.test_knowledge_extraction -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.knowledge_extraction import (  # noqa: E402
    extract_from_sections,
    _find_claim_sentences,
    _find_datasets,
    _find_metrics,
    _find_methods,
)

SECTIONS = {
    "introduction": (
        "Graph neural networks have shown strong results. In this paper, "
        "we propose GraphMix, a new hybrid message-passing architecture."
    ),
    "methodology": (
        "We propose GraphMix, which combines attention and convolution. "
        "We introduce a Contrastive Alignment loss to stabilize training."
    ),
    "experiments": (
        "We evaluate GraphMix on Cora, Citeseer, and PubMed, following the "
        "standard transductive split. We report accuracy and F1 score."
    ),
    "results": (
        "GraphMix achieves 84.2% accuracy on Cora, a 2.1 points improvement "
        "over GAT. On Citeseer, GraphMix reaches 73.5 percent accuracy."
    ),
}


class TestFindDatasets(unittest.TestCase):
    def test_finds_known_datasets_case_insensitively(self):
        text = "We test on cora and CITESEER and pubmed."
        found = _find_datasets(text)
        self.assertEqual(found, ["Citeseer", "Cora", "PubMed"])

    def test_no_false_positive_on_unrelated_text(self):
        self.assertEqual(_find_datasets("This paper discusses optimization theory."), [])

    def test_does_not_match_substring_of_another_word(self):
        # "PPI" should not match inside "SHIPPING" or similar
        self.assertEqual(_find_datasets("We discuss shipping logistics."), [])


class TestFindMetrics(unittest.TestCase):
    def test_finds_known_metrics(self):
        text = "We report accuracy, F1 score, and AUC on the test set."
        found = _find_metrics(text)
        self.assertIn("accuracy", found)
        self.assertIn("AUC", [f.upper() if f.lower()=="auc" else f for f in found] or found)

    def test_empty_text_returns_empty(self):
        self.assertEqual(_find_metrics(""), [])


class TestFindMethods(unittest.TestCase):
    def test_detects_we_propose_pattern(self):
        methods = _find_methods("In this work, we propose GraphMix for node classification.")
        self.assertIn("GraphMix", methods)

    def test_detects_we_introduce_pattern(self):
        methods = _find_methods("We introduce Contrastive Alignment as a new regularizer.")
        self.assertTrue(any("Contrastive Alignment" in m for m in methods))

    def test_no_method_found_in_plain_text(self):
        methods = _find_methods("This is a background paragraph with no proposal.")
        self.assertEqual(methods, [])


class TestFindClaimSentences(unittest.TestCase):
    def test_finds_sentences_with_percentages(self):
        text = "Our model is fast. It achieves 84.2% accuracy on Cora."
        claims = _find_claim_sentences(text)
        self.assertEqual(len(claims), 1)
        self.assertIn("84.2%", claims[0])

    def test_finds_sentences_with_point_improvement(self):
        text = "This is a 2.1 points improvement over the baseline."
        claims = _find_claim_sentences(text)
        self.assertEqual(len(claims), 1)

    def test_no_claims_in_text_without_numbers(self):
        self.assertEqual(_find_claim_sentences("This method is conceptually simple."), [])


class TestExtractFromSections(unittest.TestCase):
    def setUp(self):
        self.output = extract_from_sections(SECTIONS, paper_title="GraphMix Paper")

    def test_extracts_method_entity(self):
        method_names = [e.name for e in self.output.entities if e.entity_type == "method"]
        self.assertIn("GraphMix", method_names)

    def test_extracts_dataset_entities(self):
        dataset_names = {e.name for e in self.output.entities if e.entity_type == "dataset"}
        self.assertEqual(dataset_names, {"Cora", "Citeseer", "PubMed"})

    def test_extracts_metric_entities(self):
        metric_names = {e.name for e in self.output.entities if e.entity_type == "metric"}
        self.assertTrue({"accuracy"}.issubset({m.lower() for m in metric_names}))

    def test_extracts_claim_entities_with_evidence(self):
        claims = [e for e in self.output.entities if e.entity_type == "claim"]
        self.assertGreaterEqual(len(claims), 1)
        self.assertTrue(any("84.2%" in (c.description or "") for c in claims))

    def test_relationships_link_paper_to_entities(self):
        proposes_rels = [r for r in self.output.relationships if r.relationship_type == "proposes"]
        self.assertTrue(any(r.target_name == "GraphMix" for r in proposes_rels))
        for r in self.output.relationships:
            self.assertEqual(r.source_name, "GraphMix Paper")

    def test_empty_sections_produce_no_entities(self):
        output = extract_from_sections({}, paper_title="Empty Paper")
        self.assertEqual(output.entities, [])
        self.assertEqual(output.relationships, [])


if __name__ == "__main__":
    unittest.main()
