"""Entry point mono-source OpenAlex: baca dosen_source.csv, resolve author OpenAlex
(ORCID -> Scopus ID -> search nama+afiliasi UGM), fetch works, normalize, dedup,
lalu tulis file JSON/CSV siap-staging ke exports/.

Belum insert ke Postgres — staging DB menyusul di tahap berikutnya.
"""
from __future__ import annotations

import csv
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cleaners.merge import dedup_publications
from cleaners.normalize import extract_openalex_author_id, normalize_openalex_metrics, normalize_openalex_publication
from fetchers.openalex import create_client, fetch_lecturer_openalex_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pipeline_openalex.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("pipeline")

DOSEN_CSV = "dosen_source.csv"
EXPORTS_DIR = Path("exports")

# Daftar gelar akademik umum Indonesia — dipakai untuk memisahkan academic_title dari full_name.
_TITLE_TOKENS = [
    r"Prof\.", r"Dr\.-Ing\.", r"Dr\.Eng\.", r"Dr\.", r"Ir\.",
    r"S\.Kom\.", r"M\.Kom\.", r"S\.T\.", r"M\.T\.", r"M\.Eng\.",
    r"Ph\.D\.", r"M\.Sc\.", r"S\.Si\.", r"M\.Si\.", r"DEA\.",
    r"IPU\.", r"IPU", r"IPM\.", r"IPM", r"ASEAN Eng\.",
]
_TITLE_PATTERN = re.compile(r"^(?:" + "|".join(_TITLE_TOKENS) + r"|\s|,)+|(?:,\s*(?:" + "|".join(_TITLE_TOKENS) + r"))+\.?$")


def split_name_and_title(raw_name: str) -> tuple[str, str | None]:
    """Pisahkan gelar depan/belakang dari nama inti dosen."""
    raw_name = raw_name.strip()

    leading_titles = []
    remainder = raw_name
    while True:
        m = re.match(r"^(" + "|".join(_TITLE_TOKENS) + r")\s*", remainder)
        if not m:
            break
        leading_titles.append(m.group(1))
        remainder = remainder[m.end():]

    # Trailing titles: everything after the first comma is treated as academic title.
    trailing_title = None
    if "," in remainder:
        core, _, trailing = remainder.partition(",")
        remainder = core.strip()
        trailing_title = trailing.strip().rstrip(".").strip()

    full_name = remainder.strip().rstrip(".").strip()
    full_name = " ".join(w.capitalize() if w.islower() or w.isupper() else w for w in full_name.split())

    title_parts = leading_titles + ([trailing_title] if trailing_title else [])
    academic_title = ", ".join(t for t in title_parts if t) or None

    return full_name, academic_title


def extract_orcid(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw or raw == "-":
        return None
    m = re.search(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", raw)
    return m.group(1) if m else None


def clean_field(raw: str | None) -> str | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw or raw in ("-", "N/A", "n/a"):
        return None
    return raw


@dataclass
class LecturerRecord:
    row_ref: str
    full_name: str
    academic_title: str | None
    sinta_id: str | None
    scopus_author_id: str | None
    orcid_id: str | None
    google_scholar_id: str | None
    google_scholar_url: str | None
    openalex_author_id: str | None = None
    resolution_method: str = "not_found"
    metrics: dict | None = None


def load_dosen_csv(path: str) -> list[LecturerRecord]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # header is row 1
            full_name, academic_title = split_name_and_title(row["nama"])
            if not full_name:
                log.warning("Skip baris %d: nama kosong setelah cleaning", i)
                continue
            records.append(LecturerRecord(
                row_ref=f"{path}:{i}",
                full_name=full_name,
                academic_title=academic_title,
                sinta_id=clean_field(row.get("sinta")),
                scopus_author_id=clean_field(row.get("scopus")),
                orcid_id=extract_orcid(row.get("orchid")),
                google_scholar_id=clean_field(row.get("idscholar")),
                google_scholar_url=clean_field(row.get("urlscholar")),
            ))
    return records


def run() -> None:
    fetch_batch_id = f"openalex_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    log.info("Mulai batch %s", fetch_batch_id)

    EXPORTS_DIR.mkdir(exist_ok=True)
    lecturers = load_dosen_csv(DOSEN_CSV)
    log.info("Loaded %d dosen dari %s", len(lecturers), DOSEN_CSV)

    all_publications = []
    lecturer_pub_links: list[dict] = []  # {lecturer_row_ref, publication_index_key}
    all_metrics: dict[str, dict] = {}
    resolution_stats: dict[str, int] = {}

    with create_client() as client:
        for idx, lec in enumerate(lecturers, start=1):
            log.info("[%d/%d] Resolving %s", idx, len(lecturers), lec.full_name)
            try:
                result = fetch_lecturer_openalex_data(
                    client,
                    orcid_id=lec.orcid_id,
                    scopus_author_id=lec.scopus_author_id,
                    full_name=lec.full_name,
                )
            except Exception:
                log.exception("Gagal fetch untuk %s", lec.full_name)
                resolution_stats["error"] = resolution_stats.get("error", 0) + 1
                continue

            lec.resolution_method = result["resolution_method"]
            resolution_stats[lec.resolution_method] = resolution_stats.get(lec.resolution_method, 0) + 1

            author = result["author"]
            if not author:
                log.warning("Author OpenAlex tidak ditemukan untuk %s", lec.full_name)
                continue

            lec.openalex_author_id = extract_openalex_author_id(author)
            metrics = normalize_openalex_metrics(author)
            if metrics:
                all_metrics[lec.row_ref] = metrics.model_dump(mode="json")

            works = result["works"]
            log.info("  -> matched %s (%s), %d works", lec.openalex_author_id, lec.resolution_method, len(works))

            for raw_work in works:
                pub = normalize_openalex_publication(raw_work, fetch_batch_id=fetch_batch_id)
                if pub is None:
                    log.warning("  Skip work tanpa title/authors valid untuk %s: %s", lec.full_name, raw_work.get("id"))
                    continue
                all_publications.append(pub)
                lecturer_pub_links.append({"lecturer_row_ref": lec.row_ref, "publication_key": id(pub)})

    log.info("Resolution stats: %s", resolution_stats)
    log.info("Total publikasi mentah terkumpul: %d", len(all_publications))

    deduped, merged_pairs = dedup_publications(all_publications)
    log.info("Setelah dedup: %d publikasi (%d pasangan digabung)", len(deduped), len(merged_pairs))
    for a, b in merged_pairs:
        log.info("  Merged: '%s' (%s) <- '%s' (%s)", a.title[:60], a.doi, b.title[:60], b.doi)

    # Assign stable ids for export + relink after dedup (dedup replaces objects, so
    # re-derive links by re-matching original list identity isn't safe after merge;
    # instead we rebuild links via title+doi identity present in kept objects).
    pub_export = []
    pub_id_by_object: dict[int, str] = {}
    for pub in deduped:
        pub_id = str(uuid.uuid4())
        pub_id_by_object[id(pub)] = pub_id
        record = pub.model_dump(mode="json")
        record["id"] = pub_id
        pub_export.append(record)

    # Since dedup can merge multiple raw pubs into one kept object, rebuild
    # lecturer<->publication links by matching normalized doi/title+year against kept set.
    def _match_key(p) -> tuple:
        return (p.doi, None) if p.doi else (None, (p.title.lower().strip(), p.year))

    kept_by_key = {}
    for pub in deduped:
        kept_by_key[_match_key(pub)] = pub

    links_export = []
    seen_link_pairs = set()
    for orig_pub, link in zip(all_publications, lecturer_pub_links):
        key = _match_key(orig_pub)
        kept_pub = kept_by_key.get(key)
        if kept_pub is None:
            continue
        pub_id = pub_id_by_object.get(id(kept_pub))
        lec_row_ref = link["lecturer_row_ref"]
        pair = (lec_row_ref, pub_id)
        if pair in seen_link_pairs:
            continue
        seen_link_pairs.add(pair)
        links_export.append({"lecturer_row_ref": lec_row_ref, "publication_id": pub_id})

    lecturers_export = []
    for lec in lecturers:
        record = {
            "row_ref": lec.row_ref,
            "full_name": lec.full_name,
            "academic_title": lec.academic_title,
            "sinta_id": lec.sinta_id,
            "scopus_author_id": lec.scopus_author_id,
            "orcid_id": lec.orcid_id,
            "google_scholar_id": lec.google_scholar_id,
            "google_scholar_url": lec.google_scholar_url,
            "openalex_author_id": lec.openalex_author_id,
            "openalex_resolution_method": lec.resolution_method,
        }
        lecturers_export.append(record)

    with open(EXPORTS_DIR / "lecturers_openalex.json", "w", encoding="utf-8") as f:
        json.dump(lecturers_export, f, ensure_ascii=False, indent=2)

    with open(EXPORTS_DIR / "publications_openalex.json", "w", encoding="utf-8") as f:
        json.dump(pub_export, f, ensure_ascii=False, indent=2)

    with open(EXPORTS_DIR / "lecturer_publications_openalex.json", "w", encoding="utf-8") as f:
        json.dump(links_export, f, ensure_ascii=False, indent=2)

    with open(EXPORTS_DIR / "lecturer_metrics_openalex.json", "w", encoding="utf-8") as f:
        json.dump(
            [{"lecturer_row_ref": k, **v} for k, v in all_metrics.items()],
            f, ensure_ascii=False, indent=2,
        )

    _write_publications_csv(pub_export, EXPORTS_DIR / "publications_openalex.csv")
    _write_lecturers_csv(lecturers_export, EXPORTS_DIR / "lecturers_openalex.csv")

    log.info("Selesai. Output di %s/", EXPORTS_DIR)
    log.info("  lecturers: %d, publications: %d, links: %d, metrics: %d",
              len(lecturers_export), len(pub_export), len(links_export), len(all_metrics))


def _write_publications_csv(records: list[dict], path: Path) -> None:
    if not records:
        return
    fieldnames = list(records[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = dict(r)
            row["external_ids"] = json.dumps(row.get("external_ids") or {}, ensure_ascii=False)
            writer.writerow(row)


def _write_lecturers_csv(records: list[dict], path: Path) -> None:
    if not records:
        return
    fieldnames = list(records[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    run()
