"""
Offline tests for research-intelligence heuristics.

Run with:  python3 -m unittest tests.test_research_intelligence -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.research_intelligence import (  # noqa: E402
    assess_novelty,
    build_benchmark_timelines,
    compute_paper_analyses,
    detect_contradictions,
    detect_gaps,
    detect_missing_citations,
    recommend_related_papers,
)

CONTRADICTORY_KNOWLEDGE = [
    {
        "paper_title": "Paper A",
        "methods": ["MethodA"],
        "datasets": ["Cora"],
        "claims": ["MethodA achieves 84.2% accuracy on Cora."],
    },
    {
        "paper_title": "Paper B",
        "methods": ["MethodB"],
        "datasets": ["Cora"],
        "claims": ["MethodB achieves 71.0% accuracy on Cora."],
    },
]

AGREEING_KNOWLEDGE = [
    {
        "paper_title": "Paper A",
        "methods": ["MethodA"],
        "datasets": ["Cora"],
        "claims": ["MethodA achieves 84.2% accuracy on Cora."],
    },
    {
        "paper_title": "Paper B",
        "methods": ["MethodB"],
        "datasets": ["Cora"],
        "claims": ["MethodB achieves 83.9% accuracy on Cora."],
    },
]


class TestDetectContradictions(unittest.TestCase):
    def test_flags_large_spread_on_same_dataset(self):
        contradictions = detect_contradictions(CONTRADICTORY_KNOWLEDGE)
        self.assertEqual(len(contradictions), 1)
        self.assertEqual(contradictions[0].dataset, "Cora")
        self.assertAlmostEqual(contradictions[0].spread, 13.2, places=1)

    def test_does_not_flag_small_spread(self):
        contradictions = detect_contradictions(AGREEING_KNOWLEDGE, min_spread=5.0)
        self.assertEqual(contradictions, [])

    def test_single_paper_per_dataset_is_not_a_contradiction(self):
        knowledge = [CONTRADICTORY_KNOWLEDGE[0]]
        self.assertEqual(detect_contradictions(knowledge), [])

    def test_empty_knowledge_returns_empty(self):
        self.assertEqual(detect_contradictions([]), [])

    def test_claims_without_numbers_are_ignored(self):
        knowledge = [
            {"paper_title": "P", "methods": [], "datasets": ["Cora"], "claims": ["This method is fast."]},
        ]
        self.assertEqual(detect_contradictions(knowledge), [])


class TestDetectGaps(unittest.TestCase):
    def test_flags_dataset_used_by_only_one_paper(self):
        knowledge = [
            {"paper_title": "A", "methods": ["M1"], "datasets": ["RareSet"], "claims": []},
            {"paper_title": "B", "methods": ["M2"], "datasets": ["Cora"], "claims": []},
            {"paper_title": "C", "methods": ["M3"], "datasets": ["Cora"], "claims": []},
        ]
        gaps = detect_gaps(knowledge)
        underexplored = [g for g in gaps if g.kind == "underexplored_dataset"]
        self.assertEqual(len(underexplored), 1)
        self.assertEqual(underexplored[0].subject, "RareSet")

    def test_flags_method_with_no_dataset(self):
        knowledge = [{"paper_title": "A", "methods": ["OrphanMethod"], "datasets": [], "claims": []}]
        gaps = detect_gaps(knowledge)
        unevaluated = [g for g in gaps if g.kind == "unevaluated_method"]
        self.assertEqual(len(unevaluated), 1)
        self.assertEqual(unevaluated[0].subject, "OrphanMethod")

    def test_no_gaps_when_dataset_used_widely_and_methods_evaluated(self):
        knowledge = [
            {"paper_title": "A", "methods": ["M1"], "datasets": ["Cora"], "claims": []},
            {"paper_title": "B", "methods": ["M2"], "datasets": ["Cora"], "claims": []},
        ]
        self.assertEqual(detect_gaps(knowledge), [])

    def test_empty_knowledge_returns_empty(self):
        self.assertEqual(detect_gaps([]), [])


class TestAssessNovelty(unittest.TestCase):
    def test_unique_method_gets_full_novelty_score(self):
        knowledge = [{"paper_title": "A", "methods": ["QuantumFlow"], "datasets": [], "claims": []}]
        assessments = assess_novelty(knowledge)
        self.assertEqual(assessments[0].novelty_score, 1.0)
        self.assertEqual(assessments[0].similar_to, [])

    def test_similar_named_methods_reduce_novelty_score(self):
        knowledge = [
            {"paper_title": "A", "methods": ["GraphMix"], "datasets": [], "claims": []},
            {"paper_title": "B", "methods": ["GraphMix Plus"], "datasets": [], "claims": []},
        ]
        assessments = assess_novelty(knowledge)
        graphmix = next(a for a in assessments if a.method_name == "GraphMix")
        self.assertLess(graphmix.novelty_score, 1.0)
        self.assertIn("GraphMix Plus", graphmix.similar_to)

    def test_completely_different_methods_dont_affect_each_other(self):
        knowledge = [
            {"paper_title": "A", "methods": ["AlphaNet"], "datasets": [], "claims": []},
            {"paper_title": "B", "methods": ["BetaTransformer"], "datasets": [], "claims": []},
        ]
        assessments = assess_novelty(knowledge)
        for a in assessments:
            self.assertEqual(a.novelty_score, 1.0)

    def test_empty_knowledge_returns_empty(self):
        self.assertEqual(assess_novelty([]), [])


class TestBuildBenchmarkTimelines(unittest.TestCase):
    def test_builds_timeline_for_dataset_with_multiple_dated_papers(self):
        knowledge = [
            {"paper_title": "A", "year": 2017, "methods": ["GCN"], "datasets": ["Cora"], "claims": ["GCN achieves 81.5% accuracy on Cora."]},
            {"paper_title": "B", "year": 2018, "methods": ["GAT"], "datasets": ["Cora"], "claims": ["GAT achieves 83.0% accuracy on Cora."]},
            {"paper_title": "C", "year": 2020, "methods": ["NewMethod"], "datasets": ["Cora"], "claims": ["NewMethod achieves 84.2% accuracy on Cora."]},
        ]
        timelines = build_benchmark_timelines(knowledge)
        self.assertEqual(len(timelines), 1)
        self.assertEqual(timelines[0].dataset, "Cora")
        years = [p.year for p in timelines[0].points]
        self.assertEqual(years, sorted(years))

    def test_marks_improved_when_later_value_higher(self):
        knowledge = [
            {"paper_title": "A", "year": 2017, "methods": [], "datasets": ["Cora"], "claims": ["81.5% accuracy on Cora."]},
            {"paper_title": "B", "year": 2020, "methods": [], "datasets": ["Cora"], "claims": ["84.2% accuracy on Cora."]},
        ]
        timelines = build_benchmark_timelines(knowledge)
        self.assertTrue(timelines[0].improved)

    def test_excludes_papers_without_year(self):
        knowledge = [
            {"paper_title": "A", "year": None, "methods": [], "datasets": ["Cora"], "claims": ["81.5% accuracy on Cora."]},
            {"paper_title": "B", "year": 2020, "methods": [], "datasets": ["Cora"], "claims": ["84.2% accuracy on Cora."]},
        ]
        timelines = build_benchmark_timelines(knowledge)
        # Only 1 dated point -- below default min_points=2, so no timeline
        self.assertEqual(timelines, [])

    def test_single_paper_dataset_below_min_points_excluded(self):
        knowledge = [{"paper_title": "A", "year": 2020, "methods": [], "datasets": ["Cora"], "claims": ["81.5% accuracy on Cora."]}]
        self.assertEqual(build_benchmark_timelines(knowledge), [])

    def test_empty_knowledge_returns_empty(self):
        self.assertEqual(build_benchmark_timelines([]), [])


class TestComputePaperAnalyses(unittest.TestCase):
    def test_impact_score_reflects_shared_datasets(self):
        knowledge = [
            {"paper_id": "1", "paper_title": "A", "methods": ["M1"], "datasets": ["Cora"], "claims": []},
            {"paper_id": "2", "paper_title": "B", "methods": ["M2"], "datasets": ["Cora"], "claims": []},
            {"paper_id": "3", "paper_title": "C", "methods": ["M3"], "datasets": ["Other"], "claims": []},
        ]
        analyses = compute_paper_analyses(knowledge)
        a = next(x for x in analyses if x.paper_title == "A")
        # A shares "Cora" with B (1 of 2 other papers) -> impact 0.5
        self.assertEqual(a.impact_score, 0.5)

    def test_novelty_score_none_when_no_methods_proposed(self):
        knowledge = [{"paper_id": "1", "paper_title": "A", "methods": [], "datasets": ["Cora"], "claims": []}]
        analyses = compute_paper_analyses(knowledge)
        self.assertIsNone(analyses[0].novelty_score)

    def test_novelty_score_present_when_methods_proposed(self):
        knowledge = [{"paper_id": "1", "paper_title": "A", "methods": ["UniqueMethodXYZ"], "datasets": [], "claims": []}]
        analyses = compute_paper_analyses(knowledge)
        self.assertEqual(analyses[0].novelty_score, 1.0)

    def test_evidence_density_counts_claims_per_concept(self):
        knowledge = [
            {
                "paper_id": "1", "paper_title": "A", "methods": ["M1"], "datasets": ["Cora"],
                "claims": ["claim one", "claim two"],
            }
        ]
        analyses = compute_paper_analyses(knowledge)
        # 2 claims / 2 concepts (1 method + 1 dataset) = 1.0
        self.assertEqual(analyses[0].evidence_density, 1.0)

    def test_key_contributions_matches_methods(self):
        knowledge = [{"paper_id": "1", "paper_title": "A", "methods": ["M1", "M2"], "datasets": [], "claims": []}]
        analyses = compute_paper_analyses(knowledge)
        self.assertEqual(analyses[0].key_contributions, ["M1", "M2"])

    def test_summary_mentions_methods_and_datasets(self):
        knowledge = [{"paper_id": "1", "paper_title": "A", "methods": ["M1"], "datasets": ["Cora"], "claims": []}]
        analyses = compute_paper_analyses(knowledge)
        self.assertIn("M1", analyses[0].summary)
        self.assertIn("Cora", analyses[0].summary)

    def test_empty_knowledge_returns_empty(self):
        self.assertEqual(compute_paper_analyses([]), [])

    def test_single_paper_impact_score_is_zero(self):
        knowledge = [{"paper_id": "1", "paper_title": "A", "methods": ["M1"], "datasets": [], "claims": []}]
        analyses = compute_paper_analyses(knowledge)
        self.assertEqual(analyses[0].impact_score, 0.0)


class TestDetectMissingCitations(unittest.TestCase):
    def test_flags_dataset_reuse_without_citation(self):
        knowledge = [
            {"paper_title": "Origin Paper", "methods": [], "datasets": ["Cora"], "claims": [], "cites": []},
            {"paper_title": "Reusing Paper", "methods": [], "datasets": ["Cora"], "claims": [], "cites": []},
        ]
        missing = detect_missing_citations(knowledge)
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].citing_paper_title, "Reusing Paper")
        self.assertEqual(missing[0].likely_source_paper, "Origin Paper")
        self.assertEqual(missing[0].concept, "Cora")

    def test_does_not_flag_when_citation_present(self):
        knowledge = [
            {"paper_title": "Origin Paper", "methods": [], "datasets": ["Cora"], "claims": [], "cites": []},
            {"paper_title": "Reusing Paper", "methods": [], "datasets": ["Cora"], "claims": [], "cites": ["Origin Paper"]},
        ]
        self.assertEqual(detect_missing_citations(knowledge), [])

    def test_does_not_flag_the_origin_paper_itself(self):
        knowledge = [{"paper_title": "Origin Paper", "methods": [], "datasets": ["Cora"], "claims": [], "cites": []}]
        self.assertEqual(detect_missing_citations(knowledge), [])

    def test_missing_cites_key_defaults_to_empty_not_error(self):
        knowledge = [
            {"paper_title": "Origin Paper", "methods": [], "datasets": ["Cora"], "claims": []},
            {"paper_title": "Reusing Paper", "methods": [], "datasets": ["Cora"], "claims": []},
        ]
        # No KeyError even though "cites" key is entirely absent
        missing = detect_missing_citations(knowledge)
        self.assertEqual(len(missing), 1)

    def test_empty_knowledge_returns_empty(self):
        self.assertEqual(detect_missing_citations([]), [])


class TestRecommendRelatedPapers(unittest.TestCase):
    def test_recommends_paper_with_shared_dataset(self):
        knowledge = [
            {"paper_title": "A", "methods": ["M1"], "datasets": ["Cora"], "claims": []},
            {"paper_title": "B", "methods": ["M2"], "datasets": ["Cora"], "claims": []},
            {"paper_title": "C", "methods": ["M3"], "datasets": ["Unrelated"], "claims": []},
        ]
        recs = recommend_related_papers(knowledge)
        titles_for_a = [r.recommended_paper_title for r in recs["A"]]
        self.assertIn("B", titles_for_a)
        self.assertNotIn("C", titles_for_a)

    def test_shared_concepts_are_reported(self):
        knowledge = [
            {"paper_title": "A", "methods": [], "datasets": ["Cora", "Citeseer"], "claims": []},
            {"paper_title": "B", "methods": [], "datasets": ["Cora"], "claims": []},
        ]
        recs = recommend_related_papers(knowledge)
        self.assertEqual(recs["A"][0].shared_concepts, ["Cora"])

    def test_respects_top_k(self):
        knowledge = [
            {"paper_title": "A", "methods": [], "datasets": ["Cora"], "claims": []},
            {"paper_title": "B", "methods": [], "datasets": ["Cora"], "claims": []},
            {"paper_title": "C", "methods": [], "datasets": ["Cora"], "claims": []},
            {"paper_title": "D", "methods": [], "datasets": ["Cora"], "claims": []},
        ]
        recs = recommend_related_papers(knowledge, top_k=2)
        self.assertLessEqual(len(recs["A"]), 2)

    def test_no_recommendations_when_no_overlap(self):
        knowledge = [
            {"paper_title": "A", "methods": [], "datasets": ["X"], "claims": []},
            {"paper_title": "B", "methods": [], "datasets": ["Y"], "claims": []},
        ]
        recs = recommend_related_papers(knowledge)
        self.assertEqual(recs["A"], [])

    def test_every_paper_gets_an_entry_even_if_empty(self):
        knowledge = [{"paper_title": "A", "methods": [], "datasets": [], "claims": []}]
        recs = recommend_related_papers(knowledge)
        self.assertIn("A", recs)
        self.assertEqual(recs["A"], [])

    def test_empty_knowledge_returns_empty_dict(self):
        self.assertEqual(recommend_related_papers([]), {})


if __name__ == "__main__":
    unittest.main()
