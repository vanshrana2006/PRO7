"""
Offline test for the arXiv Atom feed parser.

Uses stdlib `unittest` (not pytest) so it runs in any Python 3 environment,
including this sandbox, with zero third-party dependencies -- exercising
real parsing logic against a real-shaped fixture captured from the actual
arXiv API response format.

Run with:  python3 -m unittest tests.test_arxiv_client -v
"""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.arxiv_parser import ArxivParseError, parse_atom_feed  # noqa: E402

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "arxiv_response.xml"


class TestParseAtomFeed(unittest.TestCase):
    def setUp(self) -> None:
        self.xml_text = FIXTURE_PATH.read_text(encoding="utf-8")

    def test_parses_correct_number_of_entries(self):
        entries = parse_atom_feed(self.xml_text)
        self.assertEqual(len(entries), 2)

    def test_extracts_arxiv_id_without_url_prefix(self):
        entries = parse_atom_feed(self.xml_text)
        self.assertEqual(entries[0].arxiv_id, "1609.02907v4")
        self.assertEqual(entries[1].arxiv_id, "1710.10903v3")

    def test_title_is_whitespace_normalized(self):
        entries = parse_atom_feed(self.xml_text)
        self.assertEqual(
            entries[0].title,
            "Semi-Supervised Classification with Graph Convolutional Networks",
        )
        self.assertNotIn("\n", entries[0].title)

    def test_abstract_is_cleaned(self):
        entries = parse_atom_feed(self.xml_text)
        self.assertTrue(entries[0].abstract.startswith("We present a scalable approach"))
        self.assertNotIn("\n", entries[0].abstract)

    def test_authors_extracted_in_order(self):
        entries = parse_atom_feed(self.xml_text)
        self.assertEqual(entries[0].authors, ["Thomas N. Kipf", "Max Welling"])
        self.assertEqual(
            entries[1].authors,
            ["Petar Velickovic", "Guillem Cucurull", "Arantxa Casanova"],
        )

    def test_dates_parsed_to_datetime(self):
        entries = parse_atom_feed(self.xml_text)
        self.assertEqual(
            entries[0].published_at, dt.datetime(2016, 9, 9, 15, 22, 39)
        )
        self.assertEqual(
            entries[0].updated_at, dt.datetime(2017, 2, 22, 18, 59, 35)
        )

    def test_primary_category_and_categories(self):
        entries = parse_atom_feed(self.xml_text)
        self.assertEqual(entries[0].primary_category, "cs.LG")
        self.assertEqual(entries[0].categories, ["cs.LG", "stat.ML"])

    def test_pdf_url_extracted_from_link_title(self):
        entries = parse_atom_feed(self.xml_text)
        self.assertEqual(entries[0].pdf_url, "http://arxiv.org/pdf/1609.02907v4")

    def test_malformed_xml_raises_client_error_not_silent_failure(self):
        with self.assertRaises(ArxivParseError):
            parse_atom_feed("<not><valid xml")

    def test_empty_feed_returns_empty_list(self):
        empty_feed = (
            '<?xml version="1.0"?>'
            '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        )
        self.assertEqual(parse_atom_feed(empty_feed), [])

    def test_missing_pdf_link_falls_back_to_conventional_url(self):
        xml_without_pdf_link = self.xml_text.replace(
            '<link title="pdf" href="http://arxiv.org/pdf/1609.02907v4" rel="related" type="application/pdf"/>',
            "",
        )
        entries = parse_atom_feed(xml_without_pdf_link)
        self.assertEqual(entries[0].pdf_url, "https://arxiv.org/pdf/1609.02907v4")


if __name__ == "__main__":
    unittest.main()
