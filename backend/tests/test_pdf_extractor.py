"""
Offline test for the PDF extraction pipeline.

Generates a real PDF on disk (via reportlab) shaped like a research paper,
then runs the actual pdfplumber-based extraction/segmentation code against
it -- this is a genuine end-to-end test of the extraction logic, not a
mock. Requires only pdfplumber/pypdf/reportlab, all pre-installed here.

Run with:  python3 -m unittest tests.test_pdf_extractor -v
"""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.pdf_extractor import (  # noqa: E402
    PDFExtractionError,
    extract_pdf,
    extract_references,
    segment_into_sections,
)
from tests.helpers.make_test_pdf import build_test_pdf  # noqa: E402


class TestPDFExtractor(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.pdf_path = str(pathlib.Path(cls.tmpdir.name) / "test_paper.pdf")
        build_test_pdf(cls.pdf_path)
        cls.result = extract_pdf(cls.pdf_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmpdir.cleanup()

    def test_extracts_correct_page_count(self):
        # 9 headings in PAPER_CONTENT -> 9 pages (one showPage() each)
        self.assertEqual(self.result.num_pages, 9)

    def test_full_text_contains_known_content(self):
        self.assertIn("Graph neural networks", self.result.full_text)
        self.assertIn("Cora", self.result.full_text)

    def test_segments_recognizable_sections(self):
        types_found = {s.section_type for s in self.result.sections}
        expected = {
            "abstract",
            "introduction",
            "related_work",
            "methodology",
            "experiments",
            "results",
            "limitations",
            "conclusion",
            "references",
        }
        self.assertTrue(
            expected.issubset(types_found),
            f"Missing section types: {expected - types_found}",
        )

    def test_sections_are_in_document_order(self):
        order_indices = [s.order_index for s in self.result.sections]
        self.assertEqual(order_indices, sorted(order_indices))

    def test_abstract_section_content_matches(self):
        abstract = next(s for s in self.result.sections if s.section_type == "abstract")
        self.assertIn("graph representation learning", abstract.content)

    def test_methodology_section_content_matches(self):
        methods = next(s for s in self.result.sections if s.section_type == "methodology")
        self.assertIn("message-passing", methods.content)

    def test_references_extracted_as_separate_entries(self):
        self.assertEqual(len(self.result.references), 3)

    def test_reference_years_parsed(self):
        years = sorted(r.parsed_year for r in self.result.references)
        self.assertEqual(years, [2017, 2017, 2018])

    def test_reference_raw_text_preserved(self):
        joined = " ".join(r.raw_text for r in self.result.references)
        self.assertIn("Kipf", joined)
        self.assertIn("Velickovic", joined)
        self.assertIn("Hamilton", joined)

    def test_no_references_section_returns_empty_list(self):
        sections = [s for s in self.result.sections if s.section_type != "references"]
        self.assertEqual(extract_references(sections), [])

    def test_unreadable_file_raises_extraction_error(self):
        bad_path = str(pathlib.Path(self.tmpdir.name) / "not_a_pdf.pdf")
        with open(bad_path, "w") as f:
            f.write("this is not a pdf")
        with self.assertRaises(PDFExtractionError):
            extract_pdf(bad_path)

    def test_empty_pages_list_segments_to_empty(self):
        self.assertEqual(segment_into_sections([]), [])


if __name__ == "__main__":
    unittest.main()
