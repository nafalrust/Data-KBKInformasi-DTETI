# HANDOFF — Staging Data KBK TI (OpenAlex, Horizon A parsial)

> **Status:** Handover sementara, **satu sumber saja (OpenAlex)**. Semantic Scholar,
> CrossRef, Google Scholar, dan SINTA/Scopus/GARUDA menyusul. Data di sini akan
> di-enrich/di-merge lagi, bukan final.
> **Tanggal:** lihat `fetch_batch_id` di tabel `publications` untuk kapan data ini di-crawl.

---

## 1. Apa yang Diserahkan

| File | Isi |
|---|---|
| `sql/schema_staging.sql` | DDL lengkap staging DB (7 tabel + index) |
| `sql/seed_vocabulary.sql` | Controlled vocabulary awal: 5 `research_clusters`, 23 `research_tags` |
| `exports/kbk_staging_dump.sql` | `pg_dump --data-only --column-inserts` dari staging DB — cara tercepat import ulang (lihat §4) |
| `exports/lecturers_openalex.json` / `.csv` | 64 baris dosen dari `dosen_source.csv`, sudah dicoba resolve ke OpenAlex Author |
| `exports/publications_openalex.json` / `.csv` | 4165 publikasi (setelah dedup) hasil crawl OpenAlex |
| `exports/lecturer_publications_openalex.json` | 6452 link dosen↔publikasi (many-to-many) |
| `exports/lecturer_metrics_openalex.json` | h-index & total citations, 63 dosen |

## 2. Cara Baca Staging DB

Ikuti ERD di `sql/erd_kbk_data.md` (paste ke mermaid.live untuk lihat visual). Ringkas:

- `lecturers` — profil dasar dosen + ID lintas platform (`openalex_author_id`, `orcid_id`, dst)
- `publications` — satu baris = satu publikasi, `source='OPENALEX'` untuk semua baris di batch ini
- `lecturer_publications` — tabel penghubung many-to-many, satu publikasi bisa terhubung ke beberapa dosen KBK (multi-author internal)
- `lecturer_metrics` — snapshot h-index & total citations per dosen dari OpenAlex (bukan riwayat, selalu snapshot terakhir)
- `research_clusters` / `research_tags` — vocabulary sudah di-seed, **belum ada assignment** ke dosen (`lecturer_research_tags` masih kosong — itu proses manual terpisah, lihat Contract §5.5)

**Field yang WAJIB dibaca sebelum ditampilkan ke publik:**
- `verified_status` — semua baris `'NEEDS_REVIEW'`. Tidak ada satupun yang `VERIFIED` dari pipeline. Keputusan tampil/tidak ada di layer review kalian.
- `external_ids` (JSONB) — berisi ID OpenAlex (`{"openalex": "https://openalex.org/W...", "doi": "..."}`), berguna untuk audit/dedup lanjutan saat sumber lain ditambahkan.

## 3. ⚠️ Known Gaps / Placeholder yang WAJIB Diketahui

| Gap | Detail | Yang Perlu Dilakukan |
|---|---|---|
| **`nip_or_staff_id` bukan NIP asli** | `dosen_source.csv` dari departemen **tidak punya kolom NIP**. Sebagai placeholder sementara (supaya lolos constraint `NOT NULL`), kolom ini diisi dengan **nilai `sinta_id`** — bukan NIP sungguhan. | Ganti begitu NIP asli didapat dari departemen. Jangan pakai kolom ini sebagai NIP resmi di production. |
| **1 dosen tidak ter-resolve ke OpenAlex** | "Rr. Eny Sukani Rahayu" — `openalex_author_id IS NULL`, tidak ada baris publikasi untuknya di batch ini. | Perlu dicari manual (mungkin author profile OpenAlex belum terbentuk / nama terlalu unik untuk fuzzy search). |
| **32 dari 64 dosen di-resolve lewat name-search, bukan ID** | ORCID hanya berhasil match 31 dosen. Sisanya (32) dicocokkan lewat *search nama + filter afiliasi UGM* di OpenAlex — cara ini kurang akurat dibanding matching by ID (lihat kolom `openalex_resolution_method` di `lecturers_openalex.json`). | Sudah di-spot-check manual dan hasil cocok, tapi tetap disarankan random-check tambahan sebelum full percaya 100%. |
| **Scopus ID di CSV tidak match apapun di OpenAlex** | Field filter `scopus:<id>` OpenAlex selalu mengembalikan 0 hasil untuk semua Scopus ID di `dosen_source.csv` — kemungkinan OpenAlex belum sinkron data Scopus untuk author-author ini. | Bukan bug di pipeline kita — ini keterbatasan data OpenAlex. Scopus API asli (Horizon B) akan jadi sumber lebih pasti untuk field ini. |
| **840 dari 4165 publikasi tidak punya DOI valid** | Publikasi lama/lokal (skripsi, prosiding kecil, dll) sering tidak terindeks DOI di OpenAlex. `doi IS NULL` untuk baris-baris ini — bukan data hilang, tapi memang sumbernya tidak menyediakan. | Dedup untuk baris tanpa DOI mengandalkan title+year similarity (lihat Contract §6.1) — kalau nanti Semantic Scholar/CrossRef ditambahkan, publikasi ini punya kesempatan match ulang dan dapat DOI. |
| **`research_tags` belum di-assign ke dosen** | `lecturer_research_tags` kosong. Assignment tag itu proses manual berdasarkan bidang keahlian di CSV departemen (Contract §5.5), bukan hasil crawling — belum dikerjakan di batch ini. | Perlu staff mengisi manual sebelum tampil di listing/filter website. |

## 4. Cara Import Staging DB

**Opsi A — pakai dump (tercepat):**
```bash
createdb kbk_ti_staging   # atau nama lain sesuai kebutuhan
psql -d kbk_ti_staging -f sql/schema_staging.sql
psql -d kbk_ti_staging -f exports/kbk_staging_dump.sql
```

**Opsi B — dari file JSON/CSV mentah** (kalau mau proses ulang / audit trail lebih jelas):
```bash
psql -d kbk_ti_staging -f sql/schema_staging.sql
psql -d kbk_ti_staging -f sql/seed_vocabulary.sql
# isi .env dengan DATABASE_URL mengarah ke kbk_ti_staging, lalu:
python -m db.load_openalex_to_staging
```
