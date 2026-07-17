"""OpenAlex fetcher — resolve dosen ke OpenAlex Author, lalu ambil semua Works-nya.

Strategi resolusi author, sesuai urutan prioritas:
  1. Match by ORCID (paling akurat, OpenAlex Author API punya filter `orcid`)
  2. Match by Scopus ID (author.ids.scopus di OpenAlex, kalau ORCID tidak ada/tidak ketemu)
  3. Fallback: search by display_name + filter afiliasi UGM (kurang akurat, hasil butuh review manual)

Semua response mentah di-cache ke raw_cache/openalex/ untuk audit & supaya re-run tidak re-fetch.
"""
from __future__ import annotations

from typing import Any, Optional

from config import CRAWLER_EMAIL, OPENALEX_BASE_URL, OPENALEX_RATE_LIMIT_PER_SECOND, OPENALEX_TIMEOUT, RAW_CACHE_DIR
from fetchers.base import HttpClient, read_cache, write_cache

SOURCE = "openalex"

UGM_ROR_ID = "https://ror.org/03ke6d638"  # Universitas Gadjah Mada


def create_client() -> HttpClient:
    return HttpClient(
        base_url=OPENALEX_BASE_URL,
        requests_per_second=OPENALEX_RATE_LIMIT_PER_SECOND,
        timeout=OPENALEX_TIMEOUT,
        headers={"User-Agent": f"kbk-data-pipeline (mailto:{CRAWLER_EMAIL})"},
    )


def _mailto_params(extra: Optional[dict] = None) -> dict:
    params = {"mailto": CRAWLER_EMAIL}
    if extra:
        params.update(extra)
    return params


def find_author_by_orcid(client: HttpClient, orcid_id: str, use_cache: bool = True) -> Optional[dict]:
    cache_key = f"author_by_orcid_{orcid_id}"
    if use_cache:
        cached = read_cache(SOURCE, cache_key, RAW_CACHE_DIR)
        if cached is not None:
            return cached or None

    resp = client.get("/authors", params=_mailto_params({"filter": f"orcid:{orcid_id}"}))
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    author = results[0] if results else None
    write_cache(SOURCE, cache_key, author, RAW_CACHE_DIR)
    return author


def find_author_by_scopus_id(client: HttpClient, scopus_id: str, use_cache: bool = True) -> Optional[dict]:
    cache_key = f"author_by_scopus_{scopus_id}"
    if use_cache:
        cached = read_cache(SOURCE, cache_key, RAW_CACHE_DIR)
        if cached is not None:
            return cached or None

    resp = client.get("/authors", params=_mailto_params({"filter": f"scopus:{scopus_id}"}))
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    author = results[0] if results else None
    write_cache(SOURCE, cache_key, author, RAW_CACHE_DIR)
    return author


def search_author_by_name(client: HttpClient, display_name: str, use_cache: bool = True) -> Optional[dict]:
    """Fallback: search nama + filter afiliasi UGM. Kurang akurat, hasil butuh review manual."""
    cache_key = f"author_search_{display_name}"
    if use_cache:
        cached = read_cache(SOURCE, cache_key, RAW_CACHE_DIR)
        if cached is not None:
            return cached or None

    resp = client.get(
        "/authors",
        params=_mailto_params({
            "search": display_name,
            "filter": f"affiliations.institution.ror:{UGM_ROR_ID}",
        }),
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    author = results[0] if results else None
    write_cache(SOURCE, cache_key, author, RAW_CACHE_DIR)
    return author


def resolve_author(
    client: HttpClient,
    *,
    orcid_id: Optional[str] = None,
    scopus_author_id: Optional[str] = None,
    full_name: Optional[str] = None,
    use_cache: bool = True,
) -> tuple[Optional[dict], str]:
    """Return (author_object_or_None, method) where method in
    {"orcid", "scopus", "name_search", "not_found"}."""
    if orcid_id:
        author = find_author_by_orcid(client, orcid_id, use_cache)
        if author:
            return author, "orcid"

    if scopus_author_id:
        author = find_author_by_scopus_id(client, scopus_author_id, use_cache)
        if author:
            return author, "scopus"

    if full_name:
        author = search_author_by_name(client, full_name, use_cache)
        if author:
            return author, "name_search"

    return None, "not_found"


def fetch_works_for_author(client: HttpClient, openalex_author_id: str, use_cache: bool = True) -> list[dict]:
    """Fetch semua Works milik satu Author ID OpenAlex, dengan cursor pagination."""
    author_id_short = openalex_author_id.rsplit("/", 1)[-1]
    cache_key = f"works_{author_id_short}"
    if use_cache:
        cached = read_cache(SOURCE, cache_key, RAW_CACHE_DIR)
        if cached is not None:
            return cached

    works: list[dict] = []
    cursor = "*"
    while cursor:
        resp = client.get(
            "/works",
            params=_mailto_params({
                "filter": f"authorships.author.id:{openalex_author_id}",
                "per-page": 200,
                "cursor": cursor,
            }),
        )
        resp.raise_for_status()
        data = resp.json()
        works.extend(data.get("results", []))
        cursor = data.get("meta", {}).get("next_cursor")

    write_cache(SOURCE, cache_key, works, RAW_CACHE_DIR)
    return works


def fetch_lecturer_openalex_data(
    client: HttpClient,
    *,
    orcid_id: Optional[str] = None,
    scopus_author_id: Optional[str] = None,
    full_name: Optional[str] = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """High-level: resolve author lalu ambil semua works-nya.

    Return dict: {"author": dict|None, "resolution_method": str, "works": list[dict]}
    """
    author, method = resolve_author(
        client,
        orcid_id=orcid_id,
        scopus_author_id=scopus_author_id,
        full_name=full_name,
        use_cache=use_cache,
    )
    if not author:
        return {"author": None, "resolution_method": method, "works": []}

    works = fetch_works_for_author(client, author["id"], use_cache=use_cache)
    return {"author": author, "resolution_method": method, "works": works}
