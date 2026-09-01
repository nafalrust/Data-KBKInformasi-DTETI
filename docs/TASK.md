# TASK.md — Inisiasi Workspace `kbk-data-pipeline`

> **Tujuan file ini:** checklist konkret untuk membangun struktur folder/file pertama kali, sebelum kerja crawling sesungguhnya dimulai. Sekali struktur ini berdiri dan masuk git, file ini bisa dipindah ke `docs/` atau dihapus — fungsinya cuma buat hari pertama.
> **Rujukan:** `PRD_Data_Engineering_KBK_TI.md` §5 (Isi Repository), §6 (Data Model), §7 (Tech Stack), §8 (Pembagian Kerja)
> **PIC hari ini:** Lead (setup repo adalah tanggung jawab Lead sesuai §8)
> **Target:** selesai di Hari 1–2 Horizon A (3–4 Juli)

---

## 0. Sebelum Mulai

- [ ] Pastikan Python 3.11+ terpasang (`python3 --version`)
- [ ] Pastikan akses ke repo git kosong (GitHub org KBK TI atau equivalent) sudah dibuat, nama: **`kbk-data-pipeline`**
- [ ] Pastikan Docker terpasang jika mau jalankan PostgreSQL lokal via container (opsional tapi disarankan — lihat Langkah 5)

---

## 1. Inisialisasi Repo

```bash
mkdir kbk-data-pipeline && cd kbk-data-pipeline
git init
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

- [ ] Repo git ter-init
- [ ] Virtual environment aktif

---

## 2. Buat Struktur Folder & File Kosong

Semua folder yang bisa jadi kosong saat commit pertama (`raw_cache/*`, `exports/`) **wajib** diisi `.gitkeep` supaya struktur foldernya ikut ter-*track* git (git tidak men-track folder kosong).

Jalankan sekaligus (bisa copy-paste langsung ke terminal):

```bash
# File top-level
touch .env.example requirements.txt config.py README.md .gitignore
touch dosen.json dosen_source.csv

# fetchers/
mkdir -p fetchers
touch fetchers/__init__.py fetchers/base.py fetchers/openalex.py \
      fetchers/semantic_scholar.py fetchers/crossref.py \
      fetchers/sinta.py fetchers/google_scholar.py fetchers/scopus.py

# cleaners/
mkdir -p cleaners
touch cleaners/__init__.py cleaners/normalize.py cleaners/merge.py

# models/
mkdir -p models
touch models/__init__.py models/schemas.py models/db_models.py

# db/
mkdir -p db
touch db/__init__.py db/connection.py db/crud.py

# sql/ — kontrak database, lihat PRD §6
mkdir -p sql
touch sql/schema_staging.sql sql/seed_vocabulary.sql sql/staging_to_production_notes.sql sql/erd_kbk_data.md

# raw_cache/ — arsip mentah, JANGAN commit isinya (lihat .gitignore Langkah 3)
mkdir -p raw_cache/openalex raw_cache/semantic_scholar raw_cache/crossref raw_cache/google_scholar
touch raw_cache/openalex/.gitkeep raw_cache/semantic_scholar/.gitkeep \
      raw_cache/crossref/.gitkeep raw_cache/google_scholar/.gitkeep

# exports/ — output final handoff
mkdir -p exports
touch exports/.gitkeep

# tests/
mkdir -p tests
touch tests/__init__.py tests/test_normalize.py tests/test_merge.py

# entry point & scheduling
touch pipeline.py scheduler.py
mkdir -p .github/workflows
touch .github/workflows/weekly-sync.yml

# docs/
mkdir -p docs
touch docs/HANDOFF.md docs/EDGE_CASES.md
```

**Catatan folder yang sengaja TIDAK dibuat sekarang:**
- `raw_cache/sinta/` dan fetcher SINTA/Scopus isinya sudah ada filenya (`fetchers/sinta.py`, `fetchers/scopus.py`) tapi **jangan diisi logika dulu** — keduanya Horizon B (lihat PRD §4.0). File-nya dibuat sekarang cuma supaya strukturnya lengkap dan tidak perlu restrukturisasi nanti.
- `raw_cache/scopus/` sengaja belum dibuat — baru dibuat saat API key Scopus benar-benar ada (Horizon B).

- [ ] Semua folder & file di atas berhasil dibuat (`find . -type f | sort` untuk verifikasi)

---

## 3. Isi File yang Wajib Ada Isi dari Hari 1 (Bukan Kosong)

Beberapa file **tidak boleh** dibiarkan kosong sejak commit pertama karena langsung dipakai langkah berikutnya:

- [ ] **`.gitignore`** — isi minimal:
  ```
  .env
  raw_cache/**
  !raw_cache/**/.gitkeep
  __pycache__/
  *.pyc
  .venv/
  ```
- [ ] **`.env.example`** — template kosong tanpa isi rahasia (lihat pipeline guide referensi `data_pipeline_guide_kbk_ti.md` §0.2 untuk field yang dibutuhkan: `DATABASE_URL`, `CRAWLER_EMAIL`, `SEMANTIC_SCHOLAR_API_KEY`, dst)
- [ ] **`requirements.txt`** — isi awal:
  ```
  httpx[http2]
  beautifulsoup4
  lxml
  scholarly
  pydantic>=2
  asyncpg
  sqlalchemy[asyncio]>=2
  python-dotenv
  apscheduler
  tenacity
  ```
- [ ] **`sql/erd_kbk_data.md`** — copy dari ERD Mermaid yang sudah dibuat (lihat file terpisah `erd_kbk_data.md` yang sudah jadi) — **jangan mulai dari kosong**, sudah ada draftnya.
- [ ] **`README.md`** — minimal isi: nama proyek, cara install (`pip install -r requirements.txt`), cara jalankan (`python pipeline.py`), link ke PRD lengkap.

Sisanya (`config.py`, `fetchers/*.py`, `cleaners/*.py`, dst) **boleh kosong** di commit pertama — itu memang kerja Hari 3 dan seterusnya sesuai timeline PRD §4.

---

## 4. Jalankan `pip install`

```bash
pip install -r requirements.txt
```

- [ ] Semua dependency terpasang tanpa error

---

## 5. Setup PostgreSQL Staging Lokal

Disarankan pakai Docker supaya tidak install PostgreSQL langsung ke OS:

```bash
docker run --name kbk-staging-db \
  -e POSTGRES_PASSWORD=pass \
  -e POSTGRES_DB=kbk_ti_staging \
  -p 5432:5432 \
  -d postgres:16
```

- [ ] Container jalan (`docker ps` menunjukkan `kbk-staging-db`)
- [ ] `.env` (bukan `.env.example`) sudah dibuat dari template, isi `DATABASE_URL` mengarah ke container ini
- [ ] Bisa connect via `psql` atau client GUI (TablePlus/DBeaver/pgAdmin) untuk verifikasi koneksi

---

## 6. Commit Pertama

```bash
git add .
git commit -m "chore: inisiasi struktur workspace kbk-data-pipeline"
git branch -M main
git remote add origin <URL_REPO_GITHUB>
git push -u origin main
```

- [ ] Commit pertama berhasil push ke remote
- [ ] Struktur folder terlihat lengkap di GitHub (termasuk folder kosong via `.gitkeep`)

---

## 7. Checklist Akhir Sebelum Lanjut ke Kerja Sesungguhnya

- [ ] Repo sudah bisa di-`git clone` oleh Staff 1 dan Staff 2, masing-masing bisa `pip install -r requirements.txt` tanpa error
- [ ] `sql/erd_kbk_data.md` sudah bisa dirender (test paste ke mermaid.live)
- [ ] Database staging lokal hidup dan bisa diakses semua anggota tim (atau masing-masing punya instance lokal sendiri — didiskusikan bareng, lihat catatan di bawah)
- [ ] Semua anggota tim sudah baca `PRD_Data_Engineering_KBK_TI.md` §5–§8 minimal sekali

**Setelah checklist ini selesai → lanjut ke PRD §4.1 (Cleaning CSV Departemen), yang jadi prioritas Hari 3–6.**

---

## Catatan Tambahan

- **Soal database staging lokal vs bersama:** dokumen ini mengasumsikan tiap anggota tim jalankan PostgreSQL lokal sendiri (via Docker) untuk development, lalu Lead yang menjalankan `schema_staging.sql` final di satu instance "kanonis" untuk keperluan export/handoff di akhir Horizon A. Kalau tim mau langsung pakai satu database bersama (misal di cloud/Supabase) dari awal, sesuaikan Langkah 5 — didiskusikan dulu di sync pertama tim.
- File `dosen.json` dan `dosen_source.csv` sengaja dibuat kosong di commit pertama — isinya baru datang begitu CSV mentah dari departemen diterima (lihat PRD §11 poin 3, salah satu open question yang masih perlu dikonfirmasi).
