"""
Offline tests for the Semantic Scholar search response parser, against a
captured-shape fixture (matches the real Graph API's documented response
shape as of this writing).

Run with:  python3 -m unittest tests.test_semantic_scholar_parser -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.semantic_scholar_parser import (  # noqa: E402
    SemanticScholarParseError,
    parse_search_response,
)

FIXTURE_PAYLOAD = {
    "total": 2,
    "offset": 0,
    "data": [
        {
            "paperId": "abc123",
            "title": "Semi-Supervised Classification with Graph Convolutional Networks",
            "abstract": "We present a scalable approach for semi-supervised learning.",
            "year": 2017,
            "venue": "ICLR",
            "citationCount": 25000,
            "authors": [{"authorId": "1", "name": "Thomas N. Kipf"}, {"authorId": "2", "name": "Max Welling"}],
            "externalIds": {"ArXiv": "1609.02907", "DOI": "10.48550/arXiv.1609.02907"},
            "openAccessPdf": {"url": "https://arxiv.org/pdf/1609.02907"},
        },
        {
            "paperId": "def456",
            "title": "Graph Attention Networks",
            "abstract": "We present graph attention networks (GATs).",
            "year": 2018,
            "venue": "ICLR",
            "citationCount": 18000,
            "authors": [{"authorId": "3", "name": "Petar Velickovic"}],
            "externalIds": {"ArXiv": "1710.10903"},
            "openAccessPdf": None,
        },
    ],
}


class TestParseSearchResponse(unittest.TestCase):
    def test_parses_correct_number_of_entries(self):
        entries = parse_search_response(FIXTURE_PAYLOAD)
        self.assertEqual(len(entries), 2)

    def test_extracts_basic_fields(self):
        entries = parse_search_response(FIXTURE_PAYLOAD)
        self.assertEqual(entries[0].title, "Semi-Supervised Classification with Graph Convolutional Networks")
        self.assertEqual(entries[0].year, 2017)
        self.assertEqual(entries[0].citation_count, 25000)
        self.assertEqual(entries[0].venue, "ICLR")

    def test_extracts_authors_in_order(self):
        entries = parse_search_response(FIXTURE_PAYLOAD)
        self.assertEqual(entries[0].authors, ["Thomas N. Kipf", "Max Welling"])

    def test_arxiv_id_property_from_external_ids(self):
        entries = parse_search_response(FIXTURE_PAYLOAD)
        self.assertEqual(entries[0].arxiv_id, "1609.02907")
        self.assertEqual(entries[1].arxiv_id, "1710.10903")

    def test_doi_property_when_present(self):
        entries = parse_search_response(FIXTURE_PAYLOAD)
        self.assertEqual(entries[0].doi, "10.48550/arXiv.1609.02907")
        self.assertIsNone(entries[1].doi)

    def test_pdf_url_extracted_when_open_access(self):
        entries = parse_search_response(FIXTURE_PAYLOAD)
        self.assertEqual(entries[0].pdf_url, "https://arxiv.org/pdf/1609.02907")

    def test_pdf_url_none_when_open_access_pdf_is_null(self):
        entries = parse_search_response(FIXTURE_PAYLOAD)
        self.assertIsNone(entries[1].pdf_url)

    def test_published_at_derived_from_year(self):
        entries = parse_search_response(FIXTURE_PAYLOAD)
        self.assertEqual(entries[0].published_at.year, 2017)

    def test_missing_data_field_raises(self):
        with self.assertRaises(SemanticScholarParseError):
            parse_search_response({"total": 0})

    def test_non_dict_payload_raises(self):
        with self.assertRaises(SemanticScholarParseError):
            parse_search_response(["not", "a", "dict"])

    def test_malformed_individual_record_is_skipped_not_fatal(self):
        payload = {"data": [{"title": "missing paperId"}, FIXTURE_PAYLOAD["data"][0]]}
        entries = parse_search_response(payload)
        self.assertEqual(len(entries), 1)

    def test_empty_data_list_returns_empty(self):
        self.assertEqual(parse_search_response({"data": []}), [])


if __name__ == "__main__":
    unittest.main()
