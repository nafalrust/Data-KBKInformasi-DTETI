"""normalize_<sumber>() — pure functions, raw dict in, Pydantic schema out.

Aturan lengkap: docs/CLEANING_NORMALIZATION_CONTRACT.md
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

from models.schemas import LecturerMetricsSchema, MetricsSource, PublicationSchema, PublicationSource, PublicationType

CURRENT_YEAR = datetime.now().year

_OPENALEX_TYPE_MAP = {
    "article": PublicationType.JOURNAL,
    "journal-article": PublicationType.JOURNAL,
    "proceedings-article": PublicationType.CONFERENCE,
    "conference-paper": PublicationType.CONFERENCE,
    "book-chapter": PublicationType.BOOK_CHAPTER,
    "posted-content": PublicationType.PREPRINT,
    "preprint": PublicationType.PREPRINT,
}


def normalize_doi(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    doi = raw.strip().lower()
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi if doi.startswith("10.") else None


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _clean_title(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    title = _strip_html(raw).strip()
    return title or None


def _clean_year(raw: Optional[int]) -> Optional[int]:
    if raw is None:
        return None
    try:
        year = int(raw)
    except (TypeError, ValueError):
        return None
    if year < 1900 or year > CURRENT_YEAR + 1:
        return None
    return year


def _clean_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _clean_url(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return None


def _map_publication_type(raw_type: Optional[str]) -> PublicationType:
    if not raw_type:
        return PublicationType.OTHER
    return _OPENALEX_TYPE_MAP.get(raw_type.strip().lower(), PublicationType.OTHER)


def _reconstruct_abstract(inverted_index: Optional[dict[str, list[int]]]) -> Optional[str]:
    if not inverted_index:
        return None
    positions: dict[int, str] = {}
    for word, idxs in inverted_index.items():
        for idx in idxs:
            positions[idx] = word
    if not positions:
        return None
    ordered = [positions[i] for i in sorted(positions.keys())]
    text = " ".join(ordered).strip()
    return text or None


def _authors_text_from_authorships(authorships: list[dict]) -> Optional[str]:
    names = []
    for a in authorships:
        name = (a.get("author") or {}).get("display_name")
        if name:
            names.append(name.strip())
    if not names:
        return None
    return "; ".join(names)


def normalize_openalex_publication(raw: dict[str, Any], fetch_batch_id: Optional[str] = None) -> Optional[PublicationSchema]:
    """Pure function: raw OpenAlex Work dict -> PublicationSchema, atau None kalau baris wajib reject."""
    title = _clean_title(raw.get("title") or raw.get("display_name"))
    if not title:
        return None

    authors_text = _authors_text_from_authorships(raw.get("authorships") or [])
    if not authors_text:
        return None

    openalex_id = raw.get("id")
    external_ids: dict[str, str] = {}
    if openalex_id:
        external_ids["openalex"] = openalex_id

    doi = normalize_doi(raw.get("doi"))
    if doi:
        external_ids["doi"] = doi

    primary_location = raw.get("primary_location") or {}
    venue = None
    source_obj = primary_location.get("source") or {}
    if source_obj.get("display_name"):
        venue = source_obj["display_name"].strip()

    citation_count = raw.get("cited_by_count")
    if citation_count is not None:
        try:
            citation_count = max(0, int(citation_count))
        except (TypeError, ValueError):
            citation_count = None

    return PublicationSchema(
        title=title,
        year=_clean_year(raw.get("publication_year")),
        publication_date=_clean_date(raw.get("publication_date")),
        authors_text=authors_text,
        venue=venue,
        publication_type=_map_publication_type(raw.get("type")),
        doi=doi,
        url=_clean_url(primary_location.get("landing_page_url")),
        abstract=_reconstruct_abstract(raw.get("abstract_inverted_index")),
        citation_count=citation_count,
        source=PublicationSource.OPENALEX,
        external_ids=external_ids,
        fetch_batch_id=fetch_batch_id,
    )


def normalize_openalex_metrics(raw_author: dict[str, Any]) -> Optional[LecturerMetricsSchema]:
    """Pure function: raw OpenAlex Author dict -> LecturerMetricsSchema."""
    if not raw_author:
        return None
    stats = raw_author.get("summary_stats") or {}
    h_index = stats.get("h_index")
    total_citations = raw_author.get("cited_by_count")

    return LecturerMetricsSchema(
        h_index=int(h_index) if h_index is not None else None,
        total_citations=int(total_citations) if total_citations is not None else None,
        sinta_score=None,
        source=MetricsSource.OPENALEX,
    )


def extract_openalex_author_id(raw_author: Optional[dict[str, Any]]) -> Optional[str]:
    if not raw_author:
        return None
    return raw_author.get("id")
