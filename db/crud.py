"""Insert/upsert helpers untuk tabel staging. Dipakai oleh script load_*_to_staging.py.

Prinsip: idempotent — script load boleh dijalankan ulang tanpa duplikat
(upsert by natural key: lecturers by sinta_id, publications by doi kalau ada).
"""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def upsert_lecturer(conn: AsyncConnection, lecturer: dict[str, Any]) -> UUID:
    """Upsert by sinta_id (field wajib & dianggap stabil untuk dosen KBK TI)."""
    result = await conn.execute(
        text("""
            INSERT INTO lecturers (
                full_name, academic_title, nip_or_staff_id, sinta_id,
                scopus_author_id, google_scholar_url, google_scholar_id,
                orcid_id, openalex_author_id, source_csv_row_ref
            ) VALUES (
                :full_name, :academic_title, :nip_or_staff_id, :sinta_id,
                :scopus_author_id, :google_scholar_url, :google_scholar_id,
                :orcid_id, :openalex_author_id, :source_csv_row_ref
            )
            ON CONFLICT (sinta_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                academic_title = EXCLUDED.academic_title,
                scopus_author_id = EXCLUDED.scopus_author_id,
                google_scholar_url = EXCLUDED.google_scholar_url,
                google_scholar_id = EXCLUDED.google_scholar_id,
                orcid_id = EXCLUDED.orcid_id,
                openalex_author_id = EXCLUDED.openalex_author_id,
                source_csv_row_ref = EXCLUDED.source_csv_row_ref,
                updated_at = now()
            RETURNING id
        """),
        lecturer,
    )
    return result.scalar_one()


async def upsert_publication(conn: AsyncConnection, publication: dict[str, Any]) -> UUID:
    """Upsert by doi kalau ada; publikasi tanpa doi selalu di-insert baru (dedup
    tanpa DOI sudah ditangani cleaners/merge.py sebelum sampai sini)."""
    params = dict(publication)
    params["external_ids"] = json.dumps(publication.get("external_ids") or {})

    if publication.get("doi"):
        result = await conn.execute(
            text("""
                INSERT INTO publications (
                    title, year, publication_date, authors_text, venue,
                    publication_type, doi, url, abstract, citation_count,
                    source, external_ids, verified_status, fetch_batch_id
                ) VALUES (
                    :title, :year, :publication_date, :authors_text, :venue,
                    :publication_type, :doi, :url, :abstract, :citation_count,
                    :source, CAST(:external_ids AS JSONB), :verified_status, :fetch_batch_id
                )
                ON CONFLICT (doi) DO UPDATE SET
                    title = EXCLUDED.title,
                    year = EXCLUDED.year,
                    publication_date = EXCLUDED.publication_date,
                    authors_text = EXCLUDED.authors_text,
                    venue = EXCLUDED.venue,
                    publication_type = EXCLUDED.publication_type,
                    url = EXCLUDED.url,
                    abstract = EXCLUDED.abstract,
                    citation_count = EXCLUDED.citation_count,
                    external_ids = EXCLUDED.external_ids,
                    fetch_batch_id = EXCLUDED.fetch_batch_id,
                    updated_at = now()
                RETURNING id
            """),
            params,
        )
    else:
        result = await conn.execute(
            text("""
                INSERT INTO publications (
                    title, year, publication_date, authors_text, venue,
                    publication_type, doi, url, abstract, citation_count,
                    source, external_ids, verified_status, fetch_batch_id
                ) VALUES (
                    :title, :year, :publication_date, :authors_text, :venue,
                    :publication_type, NULL, :url, :abstract, :citation_count,
                    :source, CAST(:external_ids AS JSONB), :verified_status, :fetch_batch_id
                )
                RETURNING id
            """),
            params,
        )
    return result.scalar_one()


async def link_lecturer_publication(conn: AsyncConnection, lecturer_id: UUID, publication_id: UUID) -> None:
    await conn.execute(
        text("""
            INSERT INTO lecturer_publications (lecturer_id, publication_id)
            VALUES (:lecturer_id, :publication_id)
            ON CONFLICT (lecturer_id, publication_id) DO NOTHING
        """),
        {"lecturer_id": lecturer_id, "publication_id": publication_id},
    )


async def upsert_lecturer_metrics(conn: AsyncConnection, lecturer_id: UUID, metrics: dict[str, Any]) -> None:
    await conn.execute(
        text("""
            INSERT INTO lecturer_metrics (lecturer_id, h_index, total_citations, sinta_score, source, fetched_at)
            VALUES (:lecturer_id, :h_index, :total_citations, :sinta_score, :source, now())
            ON CONFLICT (lecturer_id) DO UPDATE SET
                h_index = EXCLUDED.h_index,
                total_citations = EXCLUDED.total_citations,
                sinta_score = EXCLUDED.sinta_score,
                source = EXCLUDED.source,
                fetched_at = now()
        """),
        {"lecturer_id": lecturer_id, **metrics},
    )
