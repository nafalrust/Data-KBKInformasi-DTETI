"""Google Scholar fetcher — ambil profil dosen (h-index, citations) + daftar
publikasinya dari Google Scholar, berdasarkan google_scholar_id yang sudah
ada di dosen_source.csv (kolom `idscholar`).

TIDAK ADA API RESMI Google Scholar. Fetcher ini pakai library `scholarly`,
yang scraping halaman publik scholar.google.com. Implikasi:
  - Sangat rawan di-rate-limit/di-block (captcha "sorry/index", HTTP 429).
    Tanpa dibatasi dari sisi kita, `scholarly` retry TANPA HENTI saat kena
    429 — makanya set_retries()/set_timeout() WAJIB diset (lihat _fetch_live),
    supaya satu dosen yang macet tidak menggantung seluruh pipeline.
  - fill() publikasi (untuk dapat abstract/venue lengkap) itu request HTTP
    terpisah PER publikasi — inilah yang paling cepat memicu block kalau
    dieksekusi tanpa jeda dan tanpa batas jumlah. FILL_TOP_N_PUBLICATIONS
    dan FILL_DELAY_SECONDS di bawah sengaja kecil/lambat: throughput publikasi
    "lengkap" per dosen rendah, tapi jauh lebih kecil kemungkinan kena block
    di tengah crawl 64 dosen. Publikasi di luar batas ini tetap terekam dari
    data snippet (title, author, year, num_citations) — cuma abstract/venue
    detailnya tidak selengkap yang di-fill().
  - Publikasi dari profil GScholar sering minim metadata (tidak semua
    dapat DOI, venue kadang cuma string bebas) — itu sebabnya dedup di
    cleaners/merge.py punya fallback title+year selain DOI exact match.
  - Rekomendasi jalan: mingguan, bukan harian. Kalau masih sering ke-block,
    pertimbangkan proxy (`scholarly.use_proxy`, lihat dokumentasi scholarly)
    atau turunkan FILL_TOP_N_PUBLICATIONS lebih jauh / jadi 0.

Semua response mentah (Author + Publication penuh dari .fill()) di-cache ke
raw_cache/google_scholar/ untuk audit & supaya re-run tidak scrape ulang
dosen yang sudah berhasil di batch sebelumnya.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from fetchers.base import read_cache, write_cache

SOURCE = "google_scholar"

# Publikasi yang di-fill() penuh (dapat abstract/venue lengkap) per dosen.
# Sengaja kecil — tiap fill() = 1 request tambahan yang rawan memicu block.
FILL_TOP_N_PUBLICATIONS = 5
FILL_DELAY_SECONDS = 3.0

# scholarly secara default retry TANPA BATAS saat kena 429/error jaringan.
# Sekali gagal, ya sudah — skip ke dosen berikutnya, jangan buang waktu retry
# (kena 429 biasanya berarti sesi ini sedang di-block, retry beruntun cuma
# memperpanjang block-nya). Batas ini juga mencegah pipeline menggantung
# sampai di-Ctrl+C manual seperti sebelum diperbaiki.
SCHOLARLY_MAX_RETRIES = 1
SCHOLARLY_TIMEOUT_SECONDS = 15

log = logging.getLogger("fetchers.google_scholar")


def fetch_lecturer_google_scholar_data(google_scholar_id: Optional[str], use_cache: bool = True) -> dict[str, Any]:
    """Ambil profil + publikasi seorang dosen dari Google Scholar by scholar_id.

    Return dict: {"author": Author|None, "publications": list[Publication], "resolution_method": str}
    resolution_method: "scholar_id" (berhasil) / "not_found" / "no_id" / "error"
    """
    if not google_scholar_id:
        return {"author": None, "publications": [], "resolution_method": "no_id"}

    if use_cache:
        cached = read_cache(SOURCE, google_scholar_id)
        if cached is not None:
            return cached

    result = _fetch_live(google_scholar_id)

    if use_cache and result["resolution_method"] != "error":
        write_cache(SOURCE, google_scholar_id, result)

    return result


def _fetch_live(google_scholar_id: str) -> dict[str, Any]:
    # Import lokal: scholarly opsional untuk lingkungan yang tidak butuh
    # fetcher ini (mis. hanya menjalankan tahap OpenAlex/loader/tests).
    from scholarly import scholarly

    # WAJIB: tanpa ini, scholarly retry tanpa henti saat kena 429/captcha
    # (lihat docstring modul) — pipeline bisa macet berjam-jam per dosen.
    scholarly.set_retries(SCHOLARLY_MAX_RETRIES)
    scholarly.set_timeout(SCHOLARLY_TIMEOUT_SECONDS)

    try:
        author_stub = scholarly.search_author_id(google_scholar_id)
    except Exception:
        log.exception("Gagal search_author_id untuk scholar_id=%s", google_scholar_id)
        return {"author": None, "publications": [], "resolution_method": "error"}

    if not author_stub:
        return {"author": None, "publications": [], "resolution_method": "not_found"}

    try:
        author = scholarly.fill(author_stub, sections=["basics", "indices", "counts", "publications"])
    except Exception:
        log.exception("Gagal fill() author scholar_id=%s", google_scholar_id)
        return {"author": None, "publications": [], "resolution_method": "error"}

    publications = list(author.get("publications") or [])

    # fill() publication-level detail itu request terpisah per publikasi —
    # lihat FILL_TOP_N_PUBLICATIONS di docstring modul untuk alasan batas ini.
    # Delay antar-fill() untuk mengurangi risiko trigger rate-limit Google.
    for i, pub in enumerate(publications[:FILL_TOP_N_PUBLICATIONS]):
        if i > 0:
            time.sleep(FILL_DELAY_SECONDS)
        try:
            publications[i] = scholarly.fill(pub)
        except Exception:
            log.warning("Gagal fill() publikasi #%d milik scholar_id=%s, pakai data snippet", i, google_scholar_id)

    return {
        "author": author,
        "publications": publications,
        "resolution_method": "scholar_id",
    }
