"""
Core ORM models for Phase 1: papers, authors, and extracted references.

Later phases add Method/Dataset/Claim/etc. entities and a knowledge-graph
layer (Phase 2) without touching these tables.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Table, Column, String, Text, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


paper_authors = Table(
    "paper_authors",
    Base.metadata,
    Column("paper_id", String, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", String, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
    Column("author_order", Integer, nullable=False, default=0),
)


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    affiliation: Mapped[str | None] = mapped_column(String, nullable=True)

    papers: Mapped[list["Paper"]] = relationship(
        "Paper", secondary=paper_authors, back_populates="authors"
    )


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)

    # External identifiers
    arxiv_id: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    doi: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    primary_category: Mapped[str | None] = mapped_column(String, nullable=True)
    categories: Mapped[str | None] = mapped_column(String, nullable=True)  # comma-separated

    pdf_url: Mapped[str | None] = mapped_column(String, nullable=True)
    local_pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)

    source: Mapped[str] = mapped_column(String, default="arxiv")

    # Populated once the PDF has been downloaded + text-extracted.
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String, default="not_started")
    # one of: not_started | downloading | extracting | completed | failed
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    num_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    authors: Mapped[list[Author]] = relationship(
        "Author", secondary=paper_authors, back_populates="papers", order_by=paper_authors.c.author_order
    )
    sections: Mapped[list["PaperSection"]] = relationship(
        "PaperSection", back_populates="paper", cascade="all, delete-orphan"
    )
    references: Mapped[list["PaperReference"]] = relationship(
        "PaperReference", back_populates="paper", cascade="all, delete-orphan"
    )


class PaperSection(Base):
    """A structural section of the paper (Introduction, Methods, Results, ...)
    extracted from the PDF layout rather than treated as flat text."""

    __tablename__ = "paper_sections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey("papers.id", ondelete="CASCADE"), index=True)

    heading: Mapped[str] = mapped_column(String, nullable=False)
    section_type: Mapped[str] = mapped_column(String, default="body")
    # one of: abstract | introduction | related_work | methodology | experiments |
    #         results | discussion | limitations | future_work | conclusion |
    #         references | body
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    paper: Mapped[Paper] = relationship("Paper", back_populates="sections")


class PaperReference(Base):
    """A single entry from the paper's bibliography, as extracted from the
    References/Bibliography section text."""

    __tablename__ = "paper_references"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey("papers.id", ondelete="CASCADE"), index=True)

    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Best-effort parsed fields (heuristic in Phase 1; LLM-refined in Phase 2)
    parsed_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_authors: Mapped[str | None] = mapped_column(Text, nullable=True)

    paper: Mapped[Paper] = relationship("Paper", back_populates="references")
