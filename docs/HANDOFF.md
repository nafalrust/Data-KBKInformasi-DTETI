# HANDOFF — Staging Data KBK TI (OpenAlex, Horizon A parsial)

> **Status:** Handover sementara, **satu sumber saja (OpenAlex)**. Semantic Scholar,
> CrossRef, Google Scholar, dan SINTA/Scopus/GARUDA menyusul. Data di sini akan
> di-enrich/di-merge lagi, bukan final.
> **Tanggal:** lihat `fetch_batch_id` di tabel `publications` untuk kapan data ini di-crawl.

---

## 1. Apa yang Diserahkan

| File | Isi |
|---|---|
| `sql/schema_staging.sql` | DDL lengkap staging DB (10 tabel + index) |
| `sql/seed_vocabulary.sql` | Controlled vocabulary awal: 5 `research_clusters`, 23 `research_tags` |
| `exports/kbk_staging_dump.sql` | `pg_dump --data-only --column-inserts` dari staging DB — cara tercepat import ulang (lihat §4). **Belum termasuk 3 tabel baru** (`lecturer_supervision_quota`, `supervised_students`, `teaching_assistants`) karena masih kosong — lihat §3 |
| `exports/lecturers_openalex.json` / `.csv` | 64 baris dosen dari `dosen_source.csv`, sudah dicoba resolve ke OpenAlex Author |
| `exports/publications_openalex.json` / `.csv` | 4165 publikasi (setelah dedup) hasil crawl OpenAlex |
| `exports/lecturer_publications_openalex.json` | 6452 link dosen↔publikasi (many-to-many) |
| `exports/lecturer_metrics_openalex.json` | h-index & total citations, 63 dosen |
| `exports/lecturer_research_tags_candidates.csv` | **Draft** 337 kandidat tag riset (kolom `full_name, tag_slug`, maks. 6 tag/dosen) untuk 62/64 dosen, hasil keyword-matching judul+abstract publikasi — belum di-insert ke DB, wajib direview manusia dulu (lihat §3) |
| `exports/lecturer_research_clusters_candidates.csv` | **Draft** 62 kandidat cluster utama (kolom `full_name, cluster_slug`, 1 cluster/dosen) untuk 62/64 dosen, diturunkan dari tag skor tertinggi milik tiap dosen — belum di-update ke DB, wajib direview manusia dulu (lihat §3) |
| `db/research_tag_keywords.py` | Kamus keyword per tag riset yang dipakai generator kandidat tag & cluster |
| `db/research_tag_cluster_map.py` | Peta tag_slug → cluster_slug, mengikuti `sql/seed_vocabulary.sql` |
| `db/generate_research_tag_candidates.py` | Script yang menghasilkan `lecturer_research_tags_candidates.csv` — bisa dijalankan ulang kalau kamus keyword diperbarui |
| `db/generate_research_cluster_candidates.py` | Script yang menghasilkan `lecturer_research_clusters_candidates.csv` |

## 2. Cara Baca Staging DB

Ikuti ERD di `sql/erd_kbk_data.md` (paste ke mermaid.live untuk lihat visual). Ringkas:

- `lecturers` — profil dasar dosen + ID lintas platform (`openalex_author_id`, `orcid_id`, dst)
- `publications` — satu baris = satu publikasi, `source='OPENALEX'` untuk semua baris di batch ini
- `lecturer_publications` — tabel penghubung many-to-many, satu publikasi bisa terhubung ke beberapa dosen KBK (multi-author internal)
- `lecturer_metrics` — snapshot h-index & total citations per dosen dari OpenAlex (bukan riwayat, selalu snapshot terakhir)
- `research_clusters` / `research_tags` — vocabulary sudah di-seed. Assignment ke dosen (`lecturer_research_tags`, dan kolom baru `lecturers.primary_research_cluster_id`) **masih kosong/NULL di DB**, tapi sudah ada draft kandidat untuk keduanya (lihat §3)
- `lecturer_supervision_quota` / `supervised_students` / `teaching_assistants` — tabel baru, **skema saja, belum ada data** apapun (lihat §3)

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
| **`research_tags` belum di-assign ke dosen (tabel DB masih kosong)** | `lecturer_research_tags` kosong di DB. Tapi sudah ada **draft otomatis** di `exports/lecturer_research_tags_candidates.csv` — hasil keyword-matching judul+abstract publikasi tiap dosen terhadap kamus keyword 23 tag (`db/research_tag_keywords.py`). 337 baris kandidat untuk 62/64 dosen, kolom hanya `full_name, tag_slug` (maks. 6 tag per dosen, urutan tidak menandakan prioritas). | **Wajib direview manusia sebelum insert** — keyword-matching bisa salah konteks (contoh: satu dosen bidang tenaga listrik ke-tag "immersive-technology" gara-gara 1 judul soal AI-pendidikan yang sebetulnya tidak relevan dengan keahlian utamanya). 2 dosen (Rr. Eny Sukani Rahayu, Nailil Husna) tidak dapat kandidat sama sekali — perlu ditentukan manual sepenuhnya. Setelah direview/dikoreksi, insert ke `lecturer_research_tags` (skrip load belum dibuat — bisa disesuaikan dari `db/load_openalex_to_staging.py` sebagai pola). |
| **`lecturers.primary_research_cluster_id` masih NULL semua (kolom baru)** | Kolom baru di `lecturers`, 1 cluster utama per dosen (many-to-one langsung, bukan tabel penghubung). Draft kandidat di `exports/lecturer_research_clusters_candidates.csv` (kolom `full_name, cluster_slug`), diturunkan dari cluster induk milik tag dengan skor keyword-match tertinggi per dosen (`db/generate_research_cluster_candidates.py`). 62/64 dosen dapat kandidat. **Distribusinya timpang**: 41/62 dosen jatuh ke cluster `intelligent-systems-data` — bukan berarti keliru, tapi kata kunci AI/ML memang paling sering muncul lintas bidang, jadi rawan bias. | **Wajib direview manusia, jangan langsung dipakai apa adanya** — cek terutama dosen yang ter-assign ke `intelligent-systems-data` tapi keahlian utamanya sebenarnya bidang lain. 2 dosen (Rr. Eny Sukani Rahayu, Nailil Husna) tidak dapat kandidat — perlu manual. Setelah direview, `UPDATE lecturers SET primary_research_cluster_id = ... WHERE id = ...`. |
| **3 tabel baru (`lecturer_supervision_quota`, `supervised_students`, `teaching_assistants`) masih skema kosong** | Ditambahkan atas permintaan tim developer untuk menampung data ketersediaan bimbingan (kuota), mahasiswa bimbingan aktif, dan asisten dosen. **Belum ada data sama sekali** — Tim Data belum punya sumber (CSV/SIA/input manual prodi) untuk field-field ini. | Developer/tim terkait perlu menentukan dan menyediakan sumber datanya. Skema dirancang generik (lihat `sql/erd_kbk_data.md` §3) supaya siap diisi begitu sumber data tersedia — tanpa perlu migrasi ulang. |

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
