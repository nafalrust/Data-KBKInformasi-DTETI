"""Semantic Scholar fetcher — resolve dosen ke Semantic Scholar Author, lalu
ambil semua Papers-nya.

API resmi (Graph API v1), gratis. Rate limit jauh lebih ketat dibanding
OpenAlex: dengan API key ~1 req/detik untuk endpoint ini (lihat
config.SEMANTIC_SCHOLAR_RATE_LIMIT_PER_SECOND); tanpa key jauh lebih
ketat lagi (shared pool publik, sering 429) — daftar key gratis di
https://www.semanticscholar.org/product/api. `HttpClient` di fetchers/base.py
sudah menangani retry otomatis untuk 429/5xx, jadi tanpa key pipeline tetap
selesai, hanya lebih lambat.

Strategi resolusi author, sesuai urutan prioritas:
  1. Match by ORCID lewat endpoint pencarian author (query nama + filter manual
     terhadap externalIds.ORCID pada hasil) — Semantic Scholar tidak punya
     filter ORCID langsung di endpoint /author/search seperti OpenAlex.
  2. Fallback: search by nama, ambil hasil pertama (kurang akurat, hasil
     butuh review manual — sama seperti fallback name-search di OpenAlex).

Semua response mentah di-cache ke raw_cache/semantic_scholar/ untuk audit &
supaya re-run tidak re-fetch.
"""
from __future__ import annotations

from typing import Any, Optional

from config import (
    RAW_CACHE_DIR,
    SEMANTIC_SCHOLAR_API_KEY,
    SEMANTIC_SCHOLAR_BASE_URL,
    SEMANTIC_SCHOLAR_RATE_LIMIT_PER_SECOND,
    SEMANTIC_SCHOLAR_TIMEOUT,
)
from fetchers.base import HttpClient, read_cache, write_cache

SOURCE = "semantic_scholar"

# Field yang diminta dari API untuk tiap paper — minim tapi cukup untuk
# normalize_semantic_scholar_publication() di cleaners/normalize.py.
PAPER_FIELDS = "title,year,publicationDate,authors,venue,publicationTypes,externalIds,abstract,citationCount"
AUTHOR_SEARCH_FIELDS = "name,affiliations,externalIds,hIndex,citationCount,paperCount"


# Skip cepat, bukan retry berkali-kali — tanpa API key rate limit Semantic
# Scholar sangat ketat (429 sering, bukan error transient sesaat), jadi
# retry bertingkat cuma buang waktu. Kalau satu dosen gagal, biarkan gagal
# untuk dosen itu di batch ini, lanjut ke dosen berikutnya (lihat
# pipeline.py::_fetch_semantic_scholar_for_lecturer). Bandingkan dengan
# OpenAlex yang pakai default HttpClient (max_attempts=4) karena jauh lebih
# stabil.
SEMANTIC_SCHOLAR_MAX_ATTEMPTS = 1


def create_client() -> HttpClient:
    headers = {"User-Agent": "kbk-data-pipeline"}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    return HttpClient(
        base_url=SEMANTIC_SCHOLAR_BASE_URL,
        requests_per_second=SEMANTIC_SCHOLAR_RATE_LIMIT_PER_SECOND,
        timeout=SEMANTIC_SCHOLAR_TIMEOUT,
        headers=headers,
        max_attempts=SEMANTIC_SCHOLAR_MAX_ATTEMPTS,
    )


def _find_author_by_orcid(client: HttpClient, orcid_id: str, full_name: str, use_cache: bool = True) -> Optional[dict]:
    """Semantic Scholar tidak punya filter ORCID di /author/search — search by
    nama, lalu cocokkan manual terhadap externalIds.ORCID pada tiap hasil."""
    cache_key = f"author_by_orcid_{orcid_id}"
    if use_cache:
        cached = read_cache(SOURCE, cache_key, RAW_CACHE_DIR)
        if cached is not None:
            return cached or None

    resp = client.get(
        "/author/search",
        params={"query": full_name, "fields": AUTHOR_SEARCH_FIELDS},
    )
    resp.raise_for_status()
    data = resp.json()
    author = None
    for candidate in data.get("data", []):
        ext_ids = candidate.get("externalIds") or {}
        if ext_ids.get("ORCID") == orcid_id:
            author = candidate
            break

    write_cache(SOURCE, cache_key, author, RAW_CACHE_DIR)
    return author


def search_author_by_name(client: HttpClient, full_name: str, use_cache: bool = True) -> Optional[dict]:
    """Fallback: search nama, ambil hasil pertama. Kurang akurat, hasil butuh review manual."""
    cache_key = f"author_search_{full_name}"
    if use_cache:
        cached = read_cache(SOURCE, cache_key, RAW_CACHE_DIR)
        if cached is not None:
            return cached or None

    resp = client.get(
        "/author/search",
        params={"query": full_name, "fields": AUTHOR_SEARCH_FIELDS},
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("data", [])
    author = results[0] if results else None
    write_cache(SOURCE, cache_key, author, RAW_CACHE_DIR)
    return author


def resolve_author(
    client: HttpClient,
    *,
    orcid_id: Optional[str] = None,
    full_name: Optional[str] = None,
    use_cache: bool = True,
) -> tuple[Optional[dict], str]:
    """Return (author_object_or_None, method) where method in
    {"orcid", "name_search", "not_found"}."""
    if orcid_id and full_name:
        author = _find_author_by_orcid(client, orcid_id, full_name, use_cache)
        if author:
            return author, "orcid"

    if full_name:
        author = search_author_by_name(client, full_name, use_cache)
        if author:
            return author, "name_search"

    return None, "not_found"


def fetch_papers_for_author(client: HttpClient, author_id: str, use_cache: bool = True) -> list[dict]:
    """Fetch semua Papers milik satu Author ID Semantic Scholar, dengan offset pagination."""
    cache_key = f"papers_{author_id}"
    if use_cache:
        cached = read_cache(SOURCE, cache_key, RAW_CACHE_DIR)
        if cached is not None:
            return cached

    papers: list[dict] = []
    offset = 0
    limit = 100
    while True:
        resp = client.get(
            f"/author/{author_id}/papers",
            params={"fields": PAPER_FIELDS, "offset": offset, "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("data", [])
        papers.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    write_cache(SOURCE, cache_key, papers, RAW_CACHE_DIR)
    return papers


def fetch_lecturer_semantic_scholar_data(
    client: HttpClient,
    *,
    orcid_id: Optional[str] = None,
    full_name: Optional[str] = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """High-level: resolve author lalu ambil semua papers-nya.

    Return dict: {"author": dict|None, "resolution_method": str, "papers": list[dict]}
    """
    author, method = resolve_author(client, orcid_id=orcid_id, full_name=full_name, use_cache=use_cache)
    if not author:
        return {"author": None, "resolution_method": method, "papers": []}

    papers = fetch_papers_for_author(client, author["authorId"], use_cache=use_cache)
    return {"author": author, "resolution_method": method, "papers": papers}
