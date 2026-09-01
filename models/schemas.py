"""Pydantic schemas — WAJIB selaras dengan sql/schema_staging.sql."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PublicationType(str, Enum):
    JOURNAL = "JOURNAL"
    CONFERENCE = "CONFERENCE"
    BOOK_CHAPTER = "BOOK_CHAPTER"
    PREPRINT = "PREPRINT"
    OTHER = "OTHER"


class PublicationSource(str, Enum):
    OPENALEX = "OPENALEX"
    SEMANTIC_SCHOLAR = "SEMANTIC_SCHOLAR"
    CROSSREF = "CROSSREF"
    GOOGLE_SCHOLAR = "GOOGLE_SCHOLAR"
    SINTA = "SINTA"
    SCOPUS = "SCOPUS"
    CSV_IMPORT = "CSV_IMPORT"


class MetricsSource(str, Enum):
    OPENALEX = "OPENALEX"
    SINTA = "SINTA"
    GOOGLE_SCHOLAR = "GOOGLE_SCHOLAR"
    SEMANTIC_SCHOLAR = "SEMANTIC_SCHOLAR"


class PublicationSchema(BaseModel):
    title: str
    year: Optional[int] = None
    publication_date: Optional[date] = None
    authors_text: str
    venue: Optional[str] = None
    publication_type: PublicationType = PublicationType.OTHER
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    citation_count: Optional[int] = None
    source: PublicationSource
    external_ids: dict = Field(default_factory=dict)
    verified_status: str = "NEEDS_REVIEW"
    fetch_batch_id: Optional[str] = None


class LecturerSchema(BaseModel):
    full_name: str
    academic_title: Optional[str] = None
    nip_or_staff_id: str
    email: Optional[str] = None
    sinta_id: Optional[str] = None
    scopus_author_id: Optional[str] = None
    google_scholar_url: Optional[str] = None
    google_scholar_id: Optional[str] = None
    orcid_id: Optional[str] = None
    openalex_author_id: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    supervision_status: Optional[str] = None
    is_active: bool = True
    source_csv_row_ref: Optional[str] = None


class LecturerMetricsSchema(BaseModel):
    h_index: Optional[int] = None
    total_citations: Optional[int] = None
    sinta_score: Optional[float] = None
    source: MetricsSource
