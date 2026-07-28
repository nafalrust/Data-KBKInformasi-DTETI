# ERD — KBK Informsi

## 1. Daftar Tabel & Status Data

| Tabel | Status | Row count | Keterangan |
|---|---|---|---|
| `lecturers` | Terisi | 64 | Semua dosen dari `dosen_source.csv`; 63 berhasil ter-resolve ke OpenAlex Author, 1 belum |
| `publications` | Terisi | 4165 | Hasil crawl OpenAlex, sudah dedup (DOI exact match / title+year similarity) |
| `lecturer_publications` | Terisi | 6452 | Tabel penghubung many-to-many dosen ↔ publikasi |
| `lecturer_metrics` | Terisi | 63 | h-index & total citations dari OpenAlex, snapshot terakhir |
| `research_clusters` | Terisi | 5 | Seed vocabulary v1 |
| `research_tags` | Terisi | 23 | Seed vocabulary v1 |
| `lecturer_research_tags` | Draft tersedia | 337 (kandidat) | Kandidat hasil keyword-matching judul+abstract publikasi (lihat `exports/lecturer_research_tags_candidates.csv`) — **belum di-insert ke DB**, tunggu review manusia |
| `lecturers.primary_research_cluster_id` | Draft tersedia | 62 (kandidat) | Kolom baru — 1 cluster utama per dosen, diturunkan dari tag skor tertinggi (lihat `exports/lecturer_research_clusters_candidates.csv`) — **belum di-update ke DB**, tunggu review manusia |
| `lecturer_supervision_quota` | **Kosong (skema saja)** | 0 | Kuota bimbingan per dosen — belum ada sumber data |
| `supervised_students` | **Kosong (skema saja)** | 0 | Mahasiswa bimbingan aktif per dosen — belum ada sumber data |
| `teaching_assistants` | **Kosong (skema saja)** | 0 | Asisten dosen per mata kuliah — belum ada sumber data |

---

## 2. Dari Mana `id` (PK) Tiap Tabel Didapat

Semua tabel dengan `id UUID PRIMARY KEY` (`lecturers`, `publications`, `research_clusters`, `research_tags`) **tidak** diisi manual oleh kode Python. DDL mendefinisikan:

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid()
```

`gen_random_uuid()` adalah fungsi bawaan Postgres (dari extension `pgcrypto`, diaktifkan di baris pertama `schema_staging.sql`). Saat `INSERT` dijalankan tanpa menyebut kolom `id`, Postgres sendiri yang generate UUID acak. Nilainya diambil kembali lewat `RETURNING id` di `db/crud.py`, lalu dipakai untuk mengisi tabel penghubung (`lecturer_publications`, dst).

Dua tabel penghubung (`lecturer_publications`, `lecturer_research_tags`) **tidak punya kolom `id` sendiri** — PK-nya komposit dari dua foreign key (`PRIMARY KEY (lecturer_id, publication_id)` / `(lecturer_id, tag_id)`), bukan UUID baru.

**Kenapa UUID, bukan angka urut (`SERIAL`)?** Supaya aman kalau nanti data dari batch/sumber berbeda digabung — dua insert independen dengan `SERIAL` bisa sama-sama menghasilkan `id=1` dan bentrok, sedangkan UUID acak praktis tidak pernah tabrakan.

---

## 3. Penjelasan Tiap Tabel

### `lecturers`
Profil dasar dosen + ID lintas platform akademik.
- **PK:** `id` (UUID, auto)
- **Constraint penting:** `sinta_id` — `NOT NULL UNIQUE` (wajib sesuai PRD Website §11.1, dan jadi kunci upsert idempotent)
- **Field kerja Tim Data** (tidak ada di skema production awal, diusulkan ikut masuk): `openalex_author_id`, `semantic_scholar_id`
- **Field Post-MVP** (kolom sudah ada, masih `NULL` di Horizon A): `scopus_author_id`
- **`primary_research_cluster_id`** (FK → `research_clusters.id`): 1 dosen = 1 cluster utama, relasi many-to-one langsung (bukan lewat tabel penghubung, beda dengan tag yang many-to-many). Masih `NULL` semua di DB — draft kandidatnya ada di `exports/lecturer_research_clusters_candidates.csv`, diturunkan dari cluster induk milik tag skor tertinggi per dosen

### `publications`
Satu baris = satu publikasi.
- **PK:** `id` (UUID, auto)
- **Constraint penting:** `doi` — `UNIQUE`, jadi kunci dedup utama lintas sumber
- **`source`** selalu `'OPENALEX'` di batch ini
- **`verified_status`** selalu `'NEEDS_REVIEW'` — pipeline tidak pernah mengisi `VERIFIED`, itu keputusan manusia di layer review tim website
- **`external_ids`** (JSONB) menyimpan ID OpenAlex + DOI, berguna untuk audit/dedup saat sumber lain (Semantic Scholar, CrossRef) ditambahkan nanti

### `lecturer_publications`
Tabel penghubung many-to-many antara `lecturers` dan `publications` — satu dosen bisa menulis banyak publikasi, satu publikasi bisa multi-author dosen internal KBK.
- **PK komposit:** `(lecturer_id, publication_id)`, keduanya FK

### `lecturer_metrics`
Snapshot metrik akademik agregat per dosen (h-index, total citations), **bukan riwayat** — di-*upsert* ulang tiap sync, `fetched_at` menandai kapan terakhir diperbarui.
- **PK:** `lecturer_id` (sekaligus FK ke `lecturers`) — relasi 1-to-1, satu dosen maksimal satu baris metrik
- **`sinta_score`** masih `NULL` di Horizon A (kolom disiapkan untuk SINTA di Horizon B)

### `research_clusters`
5 klaster riset besar (Intelligent System and Data, Networks Security and Infrastructure, dst) — vocabulary terkontrol, diisi manual oleh Tim Data, bukan hasil crawling.
- **PK:** `id` (UUID, auto)
- **Constraint:** `slug` — `UNIQUE NOT NULL`
- **Dirujuk oleh:** `research_tags.cluster_id` (satu cluster menaungi banyak tag) dan `lecturers.primary_research_cluster_id` (satu cluster jadi cluster utama banyak dosen)

### `research_tags`
23 tag riset, masing-masing wajib punya satu `cluster_id` induk (relasi belongs-to, bukan many-to-many).
- **PK:** `id` (UUID, auto)
- **FK:** `cluster_id` → `research_clusters.id`

### `lecturer_research_tags`
Tabel penghubung many-to-many antara `lecturers` dan `research_tags` — satu dosen bisa punya beberapa tag, satu tag dipakai beberapa dosen.
- **PK komposit:** `(lecturer_id, tag_id)`, keduanya FK
- **`is_primary`** menandai tag paling representatif untuk dosen itu — maksimal satu `TRUE` per dosen
- **Status:** tabel di DB staging masih **kosong**. Draft kandidat sudah di-generate otomatis dari judul+abstract publikasi (`db/generate_research_tag_candidates.py` + kamus keyword di `db/research_tag_keywords.py`), hasilnya `exports/lecturer_research_tags_candidates.csv` — kolom `full_name, tag_slug` saja, maksimal 6 tag per dosen (337 baris kandidat untuk 62/64 dosen). **Ini draft untuk direview manusia, bukan langsung diinsert** — keyword-matching bisa salah konteks (mis. dosen bidang tenaga listrik ke-tag "immersive-technology" karena ada 1 judul soal AI-pendidikan yang tidak relevan ke keahlian utamanya).
- 2 dosen tidak dapat kandidat sama sekali (tidak ada keyword match di judul/abstract publikasinya): Rr. Eny Sukani Rahayu, Nailil Husna — perlu ditentukan manual sepenuhnya.

### `lecturer_supervision_quota`
Kuota bimbingan tugas akhir per dosen per periode akademik — pelengkap kolom `supervision_status` (kualitatif: OPEN/LIMITED/CLOSED/CONTACT_FIRST) yang sudah ada di `lecturers`, dengan angka konkret.
- **PK:** `lecturer_id` (sekaligus FK ke `lecturers`) — 1-to-1, satu baris per dosen per snapshot (di-*upsert* ulang tiap periode)
- **`current_students_count`** vs **`max_quota`**: dipakai UI untuk tampilkan "3/5 kuota terisi" misalnya
- **Status:** skema saja, **belum ada data** — sumber data belum ditentukan (kemungkinan input manual dosen/prodi, bukan hasil crawling)

### `supervised_students`
Daftar mahasiswa yang sedang/pernah dibimbing dosen (skripsi/tesis/disertasi).
- **PK:** `id` (UUID, auto)
- **FK:** `lecturer_id` → `lecturers.id`
- **`supervision_role`**: `MAIN_SUPERVISOR` / `CO_SUPERVISOR` — satu mahasiswa bisa punya lebih dari satu baris kalau dibimbing multi-dosen
- **`status`**: `ACTIVE` / `COMPLETED`; `end_date` terisi begitu status jadi `COMPLETED`
- **Status:** skema saja, **belum ada data**

### `teaching_assistants`
Daftar asisten dosen (mahasiswa) per mata kuliah per periode akademik.
- **PK:** `id` (UUID, auto)
- **FK:** `lecturer_id` → `lecturers.id` (dosen pengampu mata kuliah)
- **Status:** skema saja, **belum ada data**

---

## 4. Catatan Bacaan Relasi

- `lecturers` ↔ `publications` lewat `lecturer_publications`: relasi **many-to-many** — satu dosen bisa punya banyak publikasi, satu publikasi bisa ditulis beberapa dosen KBK sekaligus.
- `lecturers` ↔ `research_tags` lewat `lecturer_research_tags`: pola yang sama, many-to-many.
- `research_clusters` → `research_tags`: satu cluster menaungi banyak tag, tapi satu tag hanya boleh masuk satu cluster (relasi belongs-to biasa, bukan many-to-many).
- `research_clusters` → `lecturers` (lewat `primary_research_cluster_id`): satu cluster jadi cluster utama banyak dosen, tapi satu dosen hanya boleh punya satu cluster utama (belongs-to, mirip pola tag→cluster tapi terbalik arahnya: di sini dosen yang menunjuk cluster, bukan tag).
- `lecturers` ↔ `lecturer_metrics`: relasi **1-to-1 opsional** — satu dosen paling banyak satu baris metrik agregat.
- Field bertanda **"Post-MVP"** sengaja tetap ada di skema staging sejak awal (kolom boleh `NULL` dulu) supaya tidak perlu migrasi ulang saat SINTA/Scopus mulai dikerjakan di Horizon B.
- Field bertanda **"field kerja Tim Data"** adalah kolom yang tidak ada di skema PRD Website §11 — diusulkan ikut masuk production (lihat PRD §6.5), tapi minimal wajib ada di staging untuk kebutuhan resolusi ID dan debugging.

---

## 5. Catatan Tambahan: Batch OpenAlex-only

Detail lengkap ada di `docs/HANDOFF.md`. Ringkas:

- `nip_or_staff_id` **bukan NIP asli** di batch ini — `dosen_source.csv` dari departemen tidak punya kolom NIP, jadi sementara diisi dengan nilai `sinta_id` sebagai placeholder supaya lolos constraint `NOT NULL`. Wajib diganti begitu NIP asli didapat.
- 1 dosen ("Rr. Eny Sukani Rahayu") tidak berhasil di-*resolve* ke OpenAlex Author — `openalex_author_id IS NULL`, tidak ada baris `publications`/`lecturer_metrics` untuknya.
- 32 dari 64 baris `lecturers` di-*resolve* lewat *name-search* fallback (bukan match by ID) — kurang akurat dibanding ORCID, sudah di-spot-check manual.
- 840 dari 4165 baris `publications` punya `doi IS NULL` — bukan bug, sumber (OpenAlex) memang tidak menyediakan DOI untuk publikasi tersebut (umumnya publikasi lokal/lama).
