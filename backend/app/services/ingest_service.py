"""
Orchestrates the full ingest pipeline for a single paper:

  1. Look up metadata on arXiv (or reuse an existing DB row).
  2. Create/update the Paper + Author rows.
  3. Download the PDF to local storage.
  4. Run the extraction pipeline (sections, references).
  5. Persist everything, updating `extraction_status` at every step so the
     frontend can show real progress instead of a fake spinner.

Every failure path sets extraction_status='failed' with a real error
message on the paper row -- nothing fails silently.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.paper import Author, Paper, PaperReference, PaperSection
from app.services.arxiv_client import ArxivClient, ArxivClientError
from app.services.pdf_downloader import PDFDownloadError, download_pdf
from app.services.pdf_extractor import PDFExtractionError, extract_pdf
from app.core.tracing import span

logger = logging.getLogger(__name__)


class IngestError(RuntimeError):
    pass


async def _get_or_create_author(db: AsyncSession, name: str) -> Author:
    normalized = name.strip().lower()
    result = await db.execute(select(Author).where(Author.normalized_name == normalized))
    author = result.scalar_one_or_none()
    if author is None:
        author = Author(name=name.strip(), normalized_name=normalized)
        db.add(author)
        await db.flush()
    return author


async def ingest_arxiv_paper(db: AsyncSession, arxiv_id: str) -> Paper:
    """Full pipeline: search -> download -> extract -> persist."""
    result = await db.execute(select(Paper).where(Paper.arxiv_id == arxiv_id))
    existing = result.scalar_one_or_none()
    if existing is not None and existing.extraction_status == "completed":
        return existing

    client = ArxivClient()
    try:
        entry = await client.get_by_id(arxiv_id)
    except ArxivClientError as exc:
        raise IngestError(f"Could not fetch metadata for {arxiv_id}: {exc}") from exc

    if entry is None:
        raise IngestError(f"No arXiv paper found for id '{arxiv_id}'")

    paper = existing or Paper(arxiv_id=entry.arxiv_id)
    paper.title = entry.title
    paper.abstract = entry.abstract
    paper.published_at = entry.published_at
    paper.updated_at = entry.updated_at
    paper.primary_category = entry.primary_category
    paper.categories = ",".join(entry.categories)
    paper.pdf_url = entry.pdf_url
    paper.source = "arxiv"
    paper.extraction_status = "downloading"

    paper.authors = [await _get_or_create_author(db, name) for name in entry.authors]

    db.add(paper)
    await db.flush()

    if not entry.pdf_url:
        paper.extraction_status = "failed"
        paper.extraction_error = "No PDF URL available from arXiv for this entry"
        await db.commit()
        return paper

    try:
        with span("pdf_download", arxiv_id=arxiv_id, pdf_url=entry.pdf_url):
            local_path = await download_pdf(entry.pdf_url, dest_filename=f"{entry.arxiv_id}.pdf")
        paper.local_pdf_path = local_path
    except PDFDownloadError as exc:
        paper.extraction_status = "failed"
        paper.extraction_error = str(exc)
        await db.commit()
        logger.warning("PDF download failed for %s: %s", arxiv_id, exc)
        return paper

    paper.extraction_status = "extracting"
    await db.flush()

    try:
        with span("pdf_extraction", arxiv_id=arxiv_id, local_path=local_path):
            result_data = extract_pdf(local_path)
    except PDFExtractionError as exc:
        paper.extraction_status = "failed"
        paper.extraction_error = str(exc)
        await db.commit()
        logger.warning("PDF extraction failed for %s: %s", arxiv_id, exc)
        return paper

    paper.full_text = result_data.full_text
    paper.num_pages = result_data.num_pages

    for section in result_data.sections:
        db.add(
            PaperSection(
                paper_id=paper.id,
                heading=section.heading,
                section_type=section.section_type,
                order_index=section.order_index,
                page_start=section.page_start,
                page_end=section.page_end,
                content=section.content,
            )
        )

    for ref in result_data.references:
        db.add(
            PaperReference(
                paper_id=paper.id,
                raw_text=ref.raw_text,
                order_index=ref.order_index,
                parsed_year=ref.parsed_year,
                parsed_title=ref.parsed_title,
                parsed_authors=ref.parsed_authors,
            )
        )

    paper.extraction_status = "completed"
    paper.extraction_error = None
    await db.commit()

    # IMPORTANT: db.refresh(paper) only reloads column attributes, not
    # relationships -- callers downstream (ExtractionAgent, graph_service's
    # citation matching) access paper.sections/paper.references directly.
    # In an async session, an un-eager-loaded relationship access lazy-loads
    # synchronously and crashes with MissingGreenlet, so we explicitly
    # re-fetch with selectinload here rather than a bare refresh().
    result = await db.execute(
        select(Paper)
        .options(
            selectinload(Paper.authors),
            selectinload(Paper.sections),
            selectinload(Paper.references),
        )
        .where(Paper.id == paper.id)
    )
    return result.scalar_one()
