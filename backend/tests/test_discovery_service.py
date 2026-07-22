"""
Offline tests for the pure result-normalization functions in
discovery_service.py. The network-fanning function itself
(search_all_sources) isn't covered here since it requires live APIs --
consistent with arxiv_client.py/semantic_scholar_client.py already being
untested at the network layer in this sandbox.

Run with:  python3 -m unittest tests.test_discovery_service -v
"""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.arxiv_parser import ArxivEntry  # noqa: E402
from app.services.discovery_converters import from_arxiv, from_semantic_scholar  # noqa: E402
from app.services.discovery_types import UnifiedResult  # noqa: E402
from app.services.semantic_scholar_parser import SemanticScholarEntry  # noqa: E402


class TestFromArxiv(unittest.TestCase):
    def test_maps_fields_correctly(self):
        entry = ArxivEntry(
            arxiv_id="1609.02907v4",
            title="GCN Paper",
            abstract="An abstract.",
            authors=["Thomas Kipf"],
            published_at=dt.datetime(2016, 9, 9),
            updated_at=None,
            primary_category="cs.LG",
            categories=["cs.LG"],
            pdf_url="http://arxiv.org/pdf/1609.02907v4",
        )
        result = from_arxiv(entry)
        self.assertEqual(result.source, "arxiv")
        self.assertEqual(result.source_id, "1609.02907v4")
        self.assertEqual(result.arxiv_id, "1609.02907v4")
        self.assertEqual(result.year, 2016)
        self.assertIsNone(result.venue)
        self.assertIsNone(result.citation_count)

    def test_year_is_none_when_no_published_date(self):
        entry = ArxivEntry(
            arxiv_id="x", title="t", abstract="a", authors=[],
            published_at=None, updated_at=None, primary_category=None,
            categories=[], pdf_url=None,
        )
        self.assertIsNone(from_arxiv(entry).year)


class TestFromSemanticScholar(unittest.TestCase):
    def test_maps_fields_correctly(self):
        entry = SemanticScholarEntry(
            paper_id="abc123",
            title="GAT Paper",
            abstract="An abstract.",
            authors=["Petar Velickovic"],
            year=2018,
            venue="ICLR",
            citation_count=18000,
            external_ids={"ArXiv": "1710.10903"},
            pdf_url="https://arxiv.org/pdf/1710.10903",
        )
        result = from_semantic_scholar(entry)
        self.assertEqual(result.source, "semantic_scholar")
        self.assertEqual(result.source_id, "abc123")
        self.assertEqual(result.arxiv_id, "1710.10903")
        self.assertEqual(result.venue, "ICLR")
        self.assertEqual(result.citation_count, 18000)

    def test_arxiv_id_none_when_no_external_id(self):
        entry = SemanticScholarEntry(
            paper_id="xyz", title="t", abstract="a", authors=[],
            year=None, venue=None, citation_count=None, external_ids={}, pdf_url=None,
        )
        self.assertIsNone(from_semantic_scholar(entry).arxiv_id)


if __name__ == "__main__":
    unittest.main()
