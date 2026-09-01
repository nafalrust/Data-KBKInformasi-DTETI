"""Entry point multi-source (OpenAlex + Google Scholar + Semantic Scholar): baca dosen_source.csv,
resolve author di tiap sumber, fetch works, normalize, dedup lintas sumber,
lalu tulis CSV siap-staging ke exports/.

Cron-ready: exit code 0 kalau sukses (termasuk kalau sebagian dosen gagal
resolve — itu hal normal, dicatat di log), exit code 1 kalau pipeline gagal
total (mis. dosen_source.csv tidak terbaca). Tidak menulis apapun ke stdin,
aman dipanggil dari cron/systemd timer/orchestrator apapun.

Belum insert ke Postgres — jalankan db/load_staging.py setelahnya untuk itu.
"""
from __future__ import annotations

import csv
import logging
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cleaners.merge import dedup_publications
from cleaners.normalize import (
    extract_google_scholar_author_id,
    extract_openalex_author_id,
    extract_semantic_scholar_author_id,
    normalize_google_scholar_metrics,
    normalize_google_scholar_publication,
    normalize_openalex_metrics,
    normalize_openalex_publication,
    normalize_semantic_scholar_metrics,
    normalize_semantic_scholar_publication,
)
from fetchers.google_scholar import fetch_lecturer_google_scholar_data
from fetchers.openalex import create_client as create_openalex_client, fetch_lecturer_openalex_data
from fetchers.semantic_scholar import create_client as create_semantic_scholar_client, fetch_lecturer_semantic_scholar_data

class _ColorFormatter(logging.Formatter):
    """Warnai level WARNING/ERROR di terminal supaya gampang di-scan sekilas
    di antara baris INFO progress biasa. Tidak berpengaruh di file log (plain)
    atau kalau stdout bukan terminal (cron/redirect ke file) — kode ANSI di
    file teks mentah cuma jadi karakter aneh, jadi dicek isatty() dulu."""

    _COLORS = {
        logging.WARNING: "\033[33m",  # kuning
        logging.ERROR: "\033[31m",    # merah
        logging.CRITICAL: "\033[1;31m",
    }
    _RESET = "\033[0m"

    def __init__(self, fmt: str, use_color: bool):
        super().__init__(fmt)
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self._COLORS.get(record.levelno) if self._use_color else None
        return f"{color}{message}{self._RESET}" if color else message


_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"

# stdout: ringkas, level INFO ke atas, tanpa traceback untuk error terduga
# (network fail, dosen tidak ketemu, dll — lihat pemakaian log.warning di
# _fetch_*_for_lecturer). Warna aktif hanya kalau memang terminal interaktif.
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_ColorFormatter(_LOG_FORMAT, use_color=sys.stdout.isatty()))

# pipeline.log: level DEBUG, termasuk traceback lengkap (exc_info=True) untuk
# debugging mendalam kalau perlu — tidak nyampur ke stdout supaya progress
# run tetap gampang dipindai.
_file_handler = logging.FileHandler("pipeline.log", encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

logging.basicConfig(level=logging.DEBUG, handlers=[_console_handler, _file_handler])
log = logging.getLogger("pipeline")

DOSEN_CSV = "dosen_source.csv"
EXPORTS_DIR = Path("exports")

# Jeda antar-dosen sebelum lanjut ke fetch Google Scholar berikutnya — lihat
# alasannya di pemakaian (mengurangi pola request yang mudah dikenali bot).
GOOGLE_SCHOLAR_LECTURER_DELAY_SECONDS = 5.0

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
    openalex_resolution_method: str = "not_found"
    google_scholar_resolution_method: str = "not_found"
    semantic_scholar_id: str | None = None
    semantic_scholar_resolution_method: str = "not_found"
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


def _fetch_openalex_for_lecturer(client, lec: LecturerRecord, fetch_batch_id: str) -> tuple[list, dict | None]:
    """Return (publications, metrics_dict_or_None) dari OpenAlex untuk satu dosen."""
    try:
        result = fetch_lecturer_openalex_data(
            client,
            orcid_id=lec.orcid_id,
            scopus_author_id=lec.scopus_author_id,
            full_name=lec.full_name,
        )
    except Exception as e:
        log.warning("  OpenAlex: gagal fetch untuk %s (%s: %s)", lec.full_name, type(e).__name__, e)
        log.debug("Detail error OpenAlex untuk %s", lec.full_name, exc_info=True)
        lec.openalex_resolution_method = "error"
        return [], None

    lec.openalex_resolution_method = result["resolution_method"]
    author = result["author"]
    if not author:
        log.warning("  OpenAlex: author tidak ditemukan untuk %s", lec.full_name)
        return [], None

    lec.openalex_author_id = extract_openalex_author_id(author)
    metrics = normalize_openalex_metrics(author)
    metrics_dict = metrics.model_dump(mode="json") if metrics else None

    publications = []
    for raw_work in result["works"]:
        pub = normalize_openalex_publication(raw_work, fetch_batch_id=fetch_batch_id)
        if pub is None:
            log.warning("  OpenAlex: skip work tanpa title/authors valid untuk %s: %s", lec.full_name, raw_work.get("id"))
            continue
        publications.append(pub)

    log.info("  OpenAlex -> %s (%s), %d publikasi", lec.openalex_author_id, lec.openalex_resolution_method, len(publications))
    return publications, metrics_dict


def _fetch_google_scholar_for_lecturer(lec: LecturerRecord, fetch_batch_id: str) -> tuple[list, dict | None]:
    """Return (publications, metrics_dict_or_None) dari Google Scholar untuk satu dosen."""
    try:
        result = fetch_lecturer_google_scholar_data(lec.google_scholar_id)
    except Exception as e:
        log.warning("  Google Scholar: gagal fetch untuk %s (%s: %s)", lec.full_name, type(e).__name__, e)
        log.debug("Detail error Google Scholar untuk %s", lec.full_name, exc_info=True)
        lec.google_scholar_resolution_method = "error"
        return [], None

    lec.google_scholar_resolution_method = result["resolution_method"]
    author = result["author"]
    if not author:
        if result["resolution_method"] != "no_id":
            log.warning("  Google Scholar: author tidak ditemukan untuk %s", lec.full_name)
        return [], None

    metrics = normalize_google_scholar_metrics(author)
    metrics_dict = metrics.model_dump(mode="json") if metrics else None

    publications = []
    for raw_pub in result["publications"]:
        pub = normalize_google_scholar_publication(raw_pub, fetch_batch_id=fetch_batch_id)
        if pub is None:
            continue
        publications.append(pub)

    log.info("  Google Scholar -> %s, %d publikasi", lec.google_scholar_id, len(publications))
    return publications, metrics_dict


def _fetch_semantic_scholar_for_lecturer(client, lec: LecturerRecord, fetch_batch_id: str) -> tuple[list, dict | None]:
    """Return (publications, metrics_dict_or_None) dari Semantic Scholar untuk satu dosen."""
    try:
        result = fetch_lecturer_semantic_scholar_data(client, orcid_id=lec.orcid_id, full_name=lec.full_name)
    except Exception as e:
        log.warning("  Semantic Scholar: gagal fetch untuk %s (%s: %s)", lec.full_name, type(e).__name__, e)
        log.debug("Detail error Semantic Scholar untuk %s", lec.full_name, exc_info=True)
        lec.semantic_scholar_resolution_method = "error"
        return [], None

    lec.semantic_scholar_resolution_method = result["resolution_method"]
    author = result["author"]
    if not author:
        log.warning("  Semantic Scholar: author tidak ditemukan untuk %s", lec.full_name)
        return [], None

    lec.semantic_scholar_id = extract_semantic_scholar_author_id(author)
    metrics = normalize_semantic_scholar_metrics(author)
    metrics_dict = metrics.model_dump(mode="json") if metrics else None

    publications = []
    for raw_paper in result["papers"]:
        pub = normalize_semantic_scholar_publication(raw_paper, fetch_batch_id=fetch_batch_id)
        if pub is None:
            continue
        publications.append(pub)

    log.info("  Semantic Scholar -> %s (%s), %d publikasi", lec.semantic_scholar_id, lec.semantic_scholar_resolution_method, len(publications))
    return publications, metrics_dict


def run() -> int:
    """Return exit code: 0 sukses (termasuk sukses parsial per-dosen), 1 gagal total."""
    fetch_batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    log.info("Mulai batch %s", fetch_batch_id)

    EXPORTS_DIR.mkdir(exist_ok=True)

    try:
        lecturers = load_dosen_csv(DOSEN_CSV)
    except (FileNotFoundError, csv.Error, KeyError):
        log.exception("Gagal baca %s — pipeline dihentikan", DOSEN_CSV)
        return 1

    log.info("Loaded %d dosen dari %s", len(lecturers), DOSEN_CSV)
    if not lecturers:
        log.error("Tidak ada dosen ter-load dari %s — pipeline dihentikan", DOSEN_CSV)
        return 1

    all_publications = []
    lecturer_pub_links: list[dict] = []  # {lecturer_row_ref, publication_key}
    metrics_by_lecturer_and_source: dict[tuple[str, str], dict] = {}
    openalex_stats: dict[str, int] = {}
    gscholar_stats: dict[str, int] = {}
    semantic_scholar_stats: dict[str, int] = {}

    with create_openalex_client() as oa_client, create_semantic_scholar_client() as s2_client:
        for idx, lec in enumerate(lecturers, start=1):
            log.info("[%d/%d] Resolving %s", idx, len(lecturers), lec.full_name)

            oa_pubs, oa_metrics = _fetch_openalex_for_lecturer(oa_client, lec, fetch_batch_id)
            openalex_stats[lec.openalex_resolution_method] = openalex_stats.get(lec.openalex_resolution_method, 0) + 1
            if oa_metrics:
                metrics_by_lecturer_and_source[(lec.row_ref, "OPENALEX")] = oa_metrics
            for pub in oa_pubs:
                all_publications.append(pub)
                lecturer_pub_links.append({"lecturer_row_ref": lec.row_ref, "publication_key": id(pub)})

            gs_pubs, gs_metrics = _fetch_google_scholar_for_lecturer(lec, fetch_batch_id)
            gscholar_stats[lec.google_scholar_resolution_method] = gscholar_stats.get(lec.google_scholar_resolution_method, 0) + 1
            if gs_metrics:
                metrics_by_lecturer_and_source[(lec.row_ref, "GOOGLE_SCHOLAR")] = gs_metrics
            for pub in gs_pubs:
                all_publications.append(pub)
                lecturer_pub_links.append({"lecturer_row_ref": lec.row_ref, "publication_key": id(pub)})

            s2_pubs, s2_metrics = _fetch_semantic_scholar_for_lecturer(s2_client, lec, fetch_batch_id)
            semantic_scholar_stats[lec.semantic_scholar_resolution_method] = semantic_scholar_stats.get(lec.semantic_scholar_resolution_method, 0) + 1
            if s2_metrics:
                metrics_by_lecturer_and_source[(lec.row_ref, "SEMANTIC_SCHOLAR")] = s2_metrics
            for pub in s2_pubs:
                all_publications.append(pub)
                lecturer_pub_links.append({"lecturer_row_ref": lec.row_ref, "publication_key": id(pub)})

            # Jeda antar-dosen khusus untuk Google Scholar — hit 64 profil
            # berturut-turut tanpa jeda adalah pola bot yang jelas bagi Google
            # dan mempercepat block/captcha. Dilewati kalau memang tidak ada
            # google_scholar_id (tidak ada request yang perlu "didinginkan").
            if lec.google_scholar_id and idx < len(lecturers):
                time.sleep(GOOGLE_SCHOLAR_LECTURER_DELAY_SECONDS)

    log.info("--- Ringkasan resolusi per sumber ---")
    log.info("  OpenAlex        : %s", _format_stats(openalex_stats))
    log.info("  Google Scholar  : %s", _format_stats(gscholar_stats))
    log.info("  Semantic Scholar: %s", _format_stats(semantic_scholar_stats))
    log.info("Total publikasi mentah terkumpul (semua sumber): %d", len(all_publications))

    deduped, merged_pairs = dedup_publications(all_publications)
    log.info("Setelah dedup: %d publikasi (%d pasangan digabung)", len(deduped), len(merged_pairs))
    for a, b in merged_pairs:
        # Detail tiap pasangan bisa ratusan baris untuk 64 dosen — cukup di
        # file log (DEBUG), stdout cukup tahu jumlahnya (baris di atas).
        log.debug("  Merged: '%s' (%s) <- '%s' (%s)", a.title[:60], a.doi, b.title[:60], b.doi)

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
            "openalex_resolution_method": lec.openalex_resolution_method,
            "google_scholar_resolution_method": lec.google_scholar_resolution_method,
            "semantic_scholar_id": lec.semantic_scholar_id,
            "semantic_scholar_resolution_method": lec.semantic_scholar_resolution_method,
        }
        lecturers_export.append(record)

    # Satu baris metrik per dosen di CSV final (skema DB: lecturer_metrics PK
    # cuma lecturer_id). Prioritas: OpenAlex > Google Scholar > Semantic
    # Scholar — dipakai sebagai fallback berjenjang, bukan digabung/dirata-rata
    # dari beberapa sumber sekaligus.
    METRICS_SOURCE_PRIORITY = ("OPENALEX", "GOOGLE_SCHOLAR", "SEMANTIC_SCHOLAR")
    metrics_export = []
    lecturer_row_refs_with_metrics = {row_ref for row_ref, _source in metrics_by_lecturer_and_source}
    for row_ref in lecturer_row_refs_with_metrics:
        m = None
        for source in METRICS_SOURCE_PRIORITY:
            m = metrics_by_lecturer_and_source.get((row_ref, source))
            if m:
                break
        metrics_export.append({"lecturer_row_ref": row_ref, **m})

    _write_csv(lecturers_export, EXPORTS_DIR / "lecturers.csv")
    _write_publications_csv(pub_export, EXPORTS_DIR / "publications.csv")
    _write_csv(links_export, EXPORTS_DIR / "lecturer_publications.csv")
    _write_csv(metrics_export, EXPORTS_DIR / "lecturer_metrics.csv")

    log.info("=== Selesai. Output CSV di %s/ ===", EXPORTS_DIR)
    log.info("  lecturers: %d, publications: %d, links: %d, metrics: %d",
              len(lecturers_export), len(pub_export), len(links_export), len(metrics_export))

    errors_total = openalex_stats.get("error", 0) + gscholar_stats.get("error", 0) + semantic_scholar_stats.get("error", 0)
    if errors_total:
        log.warning(
            "  %d error terjadi selama run ini (OpenAlex=%d, Google Scholar=%d, Semantic Scholar=%d) "
            "— dosen yang gagal di satu sumber tetap dapat data dari sumber lain kalau berhasil; "
            "detail lengkap ada di pipeline.log",
            errors_total, openalex_stats.get("error", 0), gscholar_stats.get("error", 0), semantic_scholar_stats.get("error", 0),
        )
    return 0


def _format_stats(stats: dict[str, int]) -> str:
    """Format dict resolution stats jadi 'metode=jumlah' rapi, urut dari terbesar."""
    if not stats:
        return "(tidak ada data)"
    return ", ".join(f"{method}={count}" for method, count in sorted(stats.items(), key=lambda kv: -kv[1]))


def _write_csv(records: list[dict], path: Path) -> None:
    if not records:
        log.warning("Tidak ada baris untuk %s — file tidak ditulis", path.name)
        return
    fieldnames = list(records[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def _write_publications_csv(records: list[dict], path: Path) -> None:
    if not records:
        log.warning("Tidak ada baris untuk %s — file tidak ditulis", path.name)
        return
    import json as _json
    fieldnames = list(records[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = dict(r)
            # external_ids adalah dict (JSONB di DB) — di CSV disimpan sebagai
            # string JSON dalam satu sel, di-parse balik oleh db/load_staging.py.
            row["external_ids"] = _json.dumps(row.get("external_ids") or {}, ensure_ascii=False)
            writer.writerow(row)


if __name__ == "__main__":
    sys.exit(run())
