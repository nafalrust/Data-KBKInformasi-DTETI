"""Load exports/*_openalex.json ke staging Postgres (idempotent — upsert by
sinta_id/doi). Prasyarat: sql/schema_staging.sql dan sql/seed_vocabulary.sql
sudah dijalankan ke DB target (lihat DATABASE_URL di .env).

Jalankan: python -m db.load_openalex_to_staging
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from pathlib import Path
from uuid import UUID

from db.connection import get_engine, get_sessionmaker
from db.crud import link_lecturer_publication, upsert_lecturer, upsert_lecturer_metrics, upsert_publication

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("load_openalex")

EXPORTS_DIR = Path("exports")


def _lecturer_row_for_db(rec: dict) -> dict:
    return {
        "full_name": rec["full_name"],
        "academic_title": rec["academic_title"],
        # PLACEHOLDER: dosen_source.csv tidak punya kolom NIP, sinta_id dipakai
        # sementara — GANTI dengan NIP asli begitu didapat dari departemen.
        "nip_or_staff_id": rec["sinta_id"],
        "sinta_id": rec["sinta_id"],
        "scopus_author_id": rec["scopus_author_id"],
        "google_scholar_url": rec["google_scholar_url"],
        "google_scholar_id": rec["google_scholar_id"],
        "orcid_id": rec["orcid_id"],
        "openalex_author_id": rec["openalex_author_id"],
        "source_csv_row_ref": rec["row_ref"],
    }


def _parse_date(raw: str | None) -> date | None:
    return date.fromisoformat(raw) if raw else None


def _publication_row_for_db(rec: dict) -> dict:
    return {
        "title": rec["title"],
        "year": rec["year"],
        "publication_date": _parse_date(rec["publication_date"]),
        "authors_text": rec["authors_text"],
        "venue": rec["venue"],
        "publication_type": rec["publication_type"],
        "doi": rec["doi"],
        "url": rec["url"],
        "abstract": rec["abstract"],
        "citation_count": rec["citation_count"],
        "source": rec["source"],
        "external_ids": rec["external_ids"],
        "verified_status": rec["verified_status"],
        "fetch_batch_id": rec["fetch_batch_id"],
    }


async def run() -> None:
    lecturers = json.loads((EXPORTS_DIR / "lecturers_openalex.json").read_text(encoding="utf-8"))
    publications = json.loads((EXPORTS_DIR / "publications_openalex.json").read_text(encoding="utf-8"))
    links = json.loads((EXPORTS_DIR / "lecturer_publications_openalex.json").read_text(encoding="utf-8"))
    metrics_list = json.loads((EXPORTS_DIR / "lecturer_metrics_openalex.json").read_text(encoding="utf-8"))

    engine = get_engine()
    Session = get_sessionmaker(engine)

    lecturer_id_by_row_ref: dict[str, UUID] = {}
    publication_id_by_export_id: dict[str, UUID] = {}

    async with Session() as session:
        async with session.begin():
            conn = await session.connection()

            log.info("Upserting %d lecturers...", len(lecturers))
            for rec in lecturers:
                if not rec.get("openalex_author_id"):
                    log.warning("Skip lecturer tanpa openalex_author_id (not_found): %s", rec["full_name"])
                lecturer_id = await upsert_lecturer(conn, _lecturer_row_for_db(rec))
                lecturer_id_by_row_ref[rec["row_ref"]] = lecturer_id

            log.info("Upserting %d publications...", len(publications))
            for rec in publications:
                pub_id = await upsert_publication(conn, _publication_row_for_db(rec))
                publication_id_by_export_id[rec["id"]] = pub_id

            log.info("Linking %d lecturer<->publication pairs...", len(links))
            skipped_links = 0
            for link in links:
                lecturer_id = lecturer_id_by_row_ref.get(link["lecturer_row_ref"])
                pub_id = publication_id_by_export_id.get(link["publication_id"])
                if lecturer_id is None or pub_id is None:
                    skipped_links += 1
                    continue
                await link_lecturer_publication(conn, lecturer_id, pub_id)
            if skipped_links:
                log.warning("Skip %d link (lecturer/publication id tidak ketemu)", skipped_links)

            log.info("Upserting %d lecturer_metrics...", len(metrics_list))
            for m in metrics_list:
                lecturer_id = lecturer_id_by_row_ref.get(m["lecturer_row_ref"])
                if lecturer_id is None:
                    continue
                await upsert_lecturer_metrics(conn, lecturer_id, {
                    "h_index": m["h_index"],
                    "total_citations": m["total_citations"],
                    "sinta_score": m["sinta_score"],
                    "source": m["source"],
                })

    await engine.dispose()
    log.info("Selesai load ke staging DB.")


if __name__ == "__main__":
    asyncio.run(run())
