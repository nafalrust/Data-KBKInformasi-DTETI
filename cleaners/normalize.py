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


def _clean_text(raw: Optional[str]) -> Optional[str]:
    """Trim string bebas, treat placeholder kosong ("-", "N/A") sebagai None."""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw or raw in ("-", "N/A", "n/a"):
        return None
    return raw


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


# ---------------------------------------------------------------------------
# Google Scholar (via library `scholarly`) — lihat fetchers/google_scholar.py
# ---------------------------------------------------------------------------

_GSCHOLAR_TYPE_MAP = {
    "article": PublicationType.JOURNAL,
    "inproceedings": PublicationType.CONFERENCE,
    "incollection": PublicationType.BOOK_CHAPTER,
}


def _map_gscholar_publication_type(bib: dict[str, Any]) -> PublicationType:
    pub_type = (bib.get("pub_type") or "").strip().lower()
    if pub_type in _GSCHOLAR_TYPE_MAP:
        return _GSCHOLAR_TYPE_MAP[pub_type]
    # scholarly sering tidak isi pub_type sama sekali; heuristik dari field lain.
    if bib.get("journal"):
        return PublicationType.JOURNAL
    if bib.get("venue") or bib.get("publisher"):
        return PublicationType.CONFERENCE
    return PublicationType.OTHER


def normalize_google_scholar_publication(raw: dict[str, Any], fetch_batch_id: Optional[str] = None) -> Optional[PublicationSchema]:
    """Pure function: raw scholarly Publication dict -> PublicationSchema, atau None kalau reject.

    Publikasi dari Google Scholar seringkali minim metadata dibanding OpenAlex
    (tidak ada DOI eksplisit, `pub_year` berupa string, venue tercampur di
    field `journal`/`venue`/`publisher` tergantung tipe entri) — normalisasi
    ini sengaja permisif, dedup lintas sumber (cleaners/merge.py) yang
    menangani penggabungan title+year saat DOI tidak tersedia.
    """
    bib = raw.get("bib") or {}
    title = _clean_title(bib.get("title"))
    if not title:
        return None

    authors_text = _clean_text(bib.get("author"))
    if not authors_text:
        return None
    # scholarly memisahkan nama author dengan " and ", bukan "; " seperti sumber lain.
    authors_text = "; ".join(a.strip() for a in authors_text.split(" and ") if a.strip())

    external_ids: dict[str, str] = {}
    author_pub_id = raw.get("author_pub_id")
    if author_pub_id:
        external_ids["google_scholar"] = author_pub_id

    venue = _clean_text(bib.get("venue")) or _clean_text(bib.get("journal"))

    citation_count = raw.get("num_citations")
    if citation_count is not None:
        try:
            citation_count = max(0, int(citation_count))
        except (TypeError, ValueError):
            citation_count = None

    return PublicationSchema(
        title=title,
        year=_clean_year(bib.get("pub_year")),
        publication_date=None,  # scholarly cuma kasih tahun, bukan tanggal lengkap
        authors_text=authors_text,
        venue=venue,
        publication_type=_map_gscholar_publication_type(bib),
        doi=None,  # scholarly tidak expose DOI langsung
        url=_clean_url(raw.get("pub_url") or raw.get("eprint_url")),
        abstract=_clean_text(bib.get("abstract")),
        citation_count=citation_count,
        source=PublicationSource.GOOGLE_SCHOLAR,
        external_ids=external_ids,
        fetch_batch_id=fetch_batch_id,
    )


def normalize_google_scholar_metrics(raw_author: Optional[dict[str, Any]]) -> Optional[LecturerMetricsSchema]:
    """Pure function: raw scholarly Author dict -> LecturerMetricsSchema."""
    if not raw_author:
        return None
    h_index = raw_author.get("hindex")
    total_citations = raw_author.get("citedby")

    if h_index is None and total_citations is None:
        return None

    return LecturerMetricsSchema(
        h_index=int(h_index) if h_index is not None else None,
        total_citations=int(total_citations) if total_citations is not None else None,
        sinta_score=None,
        source=MetricsSource.GOOGLE_SCHOLAR,
    )


def extract_google_scholar_author_id(raw_author: Optional[dict[str, Any]]) -> Optional[str]:
    if not raw_author:
        return None
    return raw_author.get("scholar_id")


# ---------------------------------------------------------------------------
# Semantic Scholar (Graph API v1) — lihat fetchers/semantic_scholar.py
# ---------------------------------------------------------------------------

_S2_TYPE_MAP = {
    "journalarticle": PublicationType.JOURNAL,
    "conference": PublicationType.CONFERENCE,
    "book": PublicationType.BOOK_CHAPTER,
    "review": PublicationType.OTHER,
}


def _map_semantic_scholar_publication_type(publication_types: Optional[list[str]]) -> PublicationType:
    for raw_type in publication_types or []:
        mapped = _S2_TYPE_MAP.get((raw_type or "").strip().lower())
        if mapped:
            return mapped
    return PublicationType.OTHER


def _authors_text_from_s2_authors(authors: list[dict]) -> Optional[str]:
    names = [a.get("name", "").strip() for a in authors if a.get("name")]
    names = [n for n in names if n]
    if not names:
        return None
    return "; ".join(names)


def normalize_semantic_scholar_publication(raw: dict[str, Any], fetch_batch_id: Optional[str] = None) -> Optional[PublicationSchema]:
    """Pure function: raw Semantic Scholar Paper dict -> PublicationSchema, atau None kalau reject."""
    title = _clean_title(raw.get("title"))
    if not title:
        return None

    authors_text = _authors_text_from_s2_authors(raw.get("authors") or [])
    if not authors_text:
        return None

    external_ids: dict[str, str] = {}
    paper_id = raw.get("paperId")
    if paper_id:
        external_ids["semantic_scholar"] = paper_id

    ext_ids = raw.get("externalIds") or {}
    doi = normalize_doi(ext_ids.get("DOI"))
    if doi:
        external_ids["doi"] = doi

    citation_count = raw.get("citationCount")
    if citation_count is not None:
        try:
            citation_count = max(0, int(citation_count))
        except (TypeError, ValueError):
            citation_count = None

    return PublicationSchema(
        title=title,
        year=_clean_year(raw.get("year")),
        publication_date=_clean_date(raw.get("publicationDate")),
        authors_text=authors_text,
        venue=_clean_text(raw.get("venue")),
        publication_type=_map_semantic_scholar_publication_type(raw.get("publicationTypes")),
        doi=doi,
        url=None,  # Semantic Scholar landing page URL tidak diminta di PAPER_FIELDS (hemat kuota)
        abstract=_clean_text(raw.get("abstract")),
        citation_count=citation_count,
        source=PublicationSource.SEMANTIC_SCHOLAR,
        external_ids=external_ids,
        fetch_batch_id=fetch_batch_id,
    )


def normalize_semantic_scholar_metrics(raw_author: Optional[dict[str, Any]]) -> Optional[LecturerMetricsSchema]:
    """Pure function: raw Semantic Scholar Author dict -> LecturerMetricsSchema."""
    if not raw_author:
        return None
    h_index = raw_author.get("hIndex")
    total_citations = raw_author.get("citationCount")

    if h_index is None and total_citations is None:
        return None

    return LecturerMetricsSchema(
        h_index=int(h_index) if h_index is not None else None,
        total_citations=int(total_citations) if total_citations is not None else None,
        sinta_score=None,
        source=MetricsSource.SEMANTIC_SCHOLAR,
    )


def extract_semantic_scholar_author_id(raw_author: Optional[dict[str, Any]]) -> Optional[str]:
    if not raw_author:
        return None
    return raw_author.get("authorId")
