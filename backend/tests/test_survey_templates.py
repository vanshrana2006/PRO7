"""
Offline tests for template-based survey generation.

Run with:  python3 -m unittest tests.test_survey_templates -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.survey_templates import generate_template_survey  # noqa: E402

SAMPLE_KNOWLEDGE = [
    {
        "paper_title": "GraphMix: A Hybrid Approach",
        "methods": ["GraphMix"],
        "datasets": ["Cora", "Citeseer"],
        "claims": ["GraphMix achieves 84.2% accuracy on Cora."],
    },
    {
        "paper_title": "Attention Is What Graphs Need",
        "methods": ["GAT"],
        "datasets": ["Cora", "PubMed"],
        "claims": [],
    },
]


class TestGenerateTemplateSurvey(unittest.TestCase):
    def test_empty_knowledge_returns_explanatory_message(self):
        result = generate_template_survey("quantum computing", [])
        self.assertIn("No papers were successfully ingested", result)
        self.assertIn("quantum computing", result)

    def test_includes_query_in_title(self):
        result = generate_template_survey("graph neural networks", SAMPLE_KNOWLEDGE)
        self.assertIn("# Literature Review: graph neural networks", result)

    def test_includes_paper_count(self):
        result = generate_template_survey("graph neural networks", SAMPLE_KNOWLEDGE)
        self.assertIn("2 paper(s)", result)

    def test_deduplicates_and_sorts_datasets_across_papers(self):
        result = generate_template_survey("q", SAMPLE_KNOWLEDGE)
        datasets_section = result.split("## Datasets Used")[1].split("##")[0]
        self.assertIn("Cora", datasets_section)
        self.assertIn("Citeseer", datasets_section)
        self.assertIn("PubMed", datasets_section)
        # Cora appears in both papers but should only be listed once
        self.assertEqual(datasets_section.count("Cora"), 1)

    def test_lists_all_methods(self):
        result = generate_template_survey("q", SAMPLE_KNOWLEDGE)
        self.assertIn("GraphMix", result)
        self.assertIn("GAT", result)

    def test_includes_per_paper_sections_with_headings(self):
        result = generate_template_survey("q", SAMPLE_KNOWLEDGE)
        self.assertIn("### GraphMix: A Hybrid Approach", result)
        self.assertIn("### Attention Is What Graphs Need", result)

    def test_includes_claims_when_present(self):
        result = generate_template_survey("q", SAMPLE_KNOWLEDGE)
        self.assertIn("84.2% accuracy on Cora", result)

    def test_omits_claims_section_for_paper_with_none(self):
        result = generate_template_survey("q", SAMPLE_KNOWLEDGE)
        second_paper_section = result.split("### Attention Is What Graphs Need")[1]
        self.assertNotIn("**Key claims:**", second_paper_section)


if __name__ == "__main__":
    unittest.main()
