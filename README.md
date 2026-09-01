# kbk-data-pipeline

Pipeline crawling + cleaning data dosen, publikasi, dan metrik akademik KBK TI
DTETI UGM, dari OpenAlex, Google Scholar, dan Semantic Scholar. Dikerjakan oleh
Tim Data — service penjadwalan (cron/systemd/orchestrator) dibuat dan dikelola
oleh tim developer.

## Instalasi

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Salin `.env.example` ke `.env`, isi minimal `CRAWLER_EMAIL` (dipakai OpenAlex
polite pool). `SEMANTIC_SCHOLAR_API_KEY` opsional (kosong = tetap jalan, lebih
lambat — lihat bagian Sumber Data). `DATABASE_URL` hanya dibutuhkan kalau mau
load hasil ke Postgres staging (lihat bagian Database).

## Menjalankan Pipeline

```bash
python pipeline.py
```

Baca `dosen_source.csv` di root repo, resolve tiap dosen ke OpenAlex Author,
Google Scholar profile, dan Semantic Scholar Author, fetch publikasi + metrik
dari ketiganya, normalize, dedup lintas sumber, lalu tulis CSV siap-pakai ke
`exports/`:

- `exports/lecturers.csv`
- `exports/publications.csv`
- `exports/lecturer_publications.csv`
- `exports/lecturer_metrics.csv`

File lama di `exports/` (nama yang sama) ditimpa tiap run — kalau perlu histori
per-batch, simpan salinan setelah tiap run pakai `fetch_batch_id` (ada di kolom
`publications.csv`) sebagai penanda.

**Exit code:** `0` = sukses (termasuk sukses parsial per-dosen — sebagian dosen
gagal resolve itu wajar, dicatat sebagai warning di log). `1` = pipeline gagal
total (mis. `dosen_source.csv` tidak terbaca). Cocok dipakai orkestrator apapun
untuk deteksi failure.

**Log:** `pipeline.log` (working directory) + stdout. Tidak ter-commit ke git.

**Frekuensi jalan yang disarankan:** mingguan, bukan harian — fetcher Google
Scholar scraping tanpa API resmi (lihat catatan di bawah), run yang terlalu
sering meningkatkan risiko rate-limit/block.

### Untuk Cron / Service Developer

`pipeline.py` didesain sebagai skrip yang dipanggil langsung, tanpa proses
in-process scheduler apapun — tim developer yang membungkusnya jadi cron job,
systemd timer, atau orchestrator lain. Contoh entry crontab mingguan:

```
0 2 * * 1 cd /path/to/kbk-data-pipeline && /path/to/.venv/bin/python pipeline.py >> /var/log/kbk-pipeline-cron.log 2>&1
```

## Database (Opsional)

Kalau ingin data langsung masuk Postgres staging (bukan cuma CSV):

```bash
psql -d <db> -f sql/schema_staging.sql
psql -d <db> -f sql/seed_vocabulary.sql
python -m db.load_staging
```

`db/load_staging.py` baca CSV dari `exports/` dan upsert idempotent (aman
dijalankan berkali-kali, tidak duplikat).

## Struktur Repo

```
pipeline.py              entry point utama (fetch -> normalize -> dedup -> tulis CSV)
fetchers/                satu modul per sumber data (openalex.py, google_scholar.py, semantic_scholar.py)
cleaners/                normalize.py (raw dict -> Pydantic schema), merge.py (dedup)
models/                  Pydantic schemas, WAJIB selaras dengan sql/schema_staging.sql
db/                      koneksi DB, upsert helpers, loader CSV->Postgres
sql/                     schema DDL, seed vocabulary, dokumentasi ERD
exports/                 output pipeline (CSV) + draft kandidat tag/cluster riset
docs/                    dokumentasi handoff & edge case
tests/                   unit test untuk cleaners/
```

## Sumber Data

Prioritas metrik (h-index, citations) saat beberapa sumber punya data untuk
dosen yang sama: **OpenAlex > Google Scholar > Semantic Scholar** — hanya 1
baris metrik disimpan per dosen (lihat `docs/HANDOFF.md` §3 untuk alasannya).
Publikasi dari semua sumber tetap disimpan (setelah dedup lintas sumber).

- **OpenAlex** — API resmi, gratis, tanpa API key (pakai `CRAWLER_EMAIL` untuk
  polite pool). Sumber utama untuk publikasi + metrik.
- **Google Scholar** — tidak ada API resmi. Fetcher (`fetchers/google_scholar.py`)
  scraping via library `scholarly`, rawan rate-limit/captcha (lihat gap yang
  sudah terkonfirmasi terjadi di `docs/HANDOFF.md` §3). Melengkapi publikasi
  yang tidak terindeks OpenAlex, dan fallback metrik.
- **Semantic Scholar** — API resmi (Graph API v1), gratis. Rate limit ketat
  tanpa API key (~1 req/detik dengan key, jauh lebih rendah tanpa). Isi
  `SEMANTIC_SCHOLAR_API_KEY` di `.env` kalau sudah ada key (daftar gratis:
  https://www.semanticscholar.org/product/api) — fetcher otomatis pakai kalau
  terisi, tetap jalan (lebih lambat) kalau kosong.
- **CrossRef** — dievaluasi, ditunda. Perannya cuma pelengkap metadata DOI
  yang sudah ada (venue, tanggal presisi), bukan sumber publikasi baru —
  prioritas lebih rendah dari menambah cakupan sumber lain.
- Sumber lain (SINTA, Scopus, GARUDA, WoS) belum dikerjakan — rencana Horizon
  B, lihat `DataSpecs-WebKBKProject.md`.

## Dokumentasi Lengkap

- `docs/HANDOFF.md` — status data, known gaps, cara import ke DB
- `sql/erd_kbk_data.md` — struktur seluruh tabel (kolom, tipe, constraint, relasi)
- `docs/CLEANING_NORMALIZATION_CONTRACT.md` — aturan normalisasi & dedup detail
- `docs/EDGE_CASES.md` — kasus tepi yang sudah ditangani/diketahui
