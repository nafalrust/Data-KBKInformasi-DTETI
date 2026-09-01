# HANDOFF — Staging Data KBK TI (OpenAlex + Google Scholar + Semantic Scholar, Horizon A)

> **Status:** Handover, tiga sumber (OpenAlex + Google Scholar + Semantic Scholar).
> CrossRef dievaluasi tapi ditunda — perannya cuma pelengkap metadata DOI yang
> sudah ada, bukan sumber publikasi baru, jadi prioritasnya lebih rendah dari
> menambah cakupan lewat sumber lain. SINTA/Scopus/GARUDA/WoS menyusul di
> Horizon B — data di sini akan di-enrich/di-merge lagi, bukan final.
> **Tanggal:** lihat `fetch_batch_id` di `publications.csv` untuk kapan data ini di-crawl.
> **Format serahan:** semua data (baik hasil crawling maupun vocabulary/draft) dalam **CSV**.
> Tidak ada file `.sql`/dump database di paket ini — struktur tabel didokumentasikan di
> `sql/erd_kbk_data.md`, developer yang membuat DDL/migration di sisi mereka sendiri.

---

## 1. Apa yang Diserahkan

| File | Isi |
|---|---|
| `dosen_source.csv` | CSV mentah asal dari departemen — input pipeline, disertakan untuk audit trail |
| `sql/erd_kbk_data.md` | Dokumentasi struktur seluruh tabel (nama kolom, tipe, constraint, relasi) — **satu-satunya sumber definisi schema** di paket ini |
| `exports/lecturers.csv` | 64 baris dosen dari `dosen_source.csv`, hasil resolve ke OpenAlex Author + Google Scholar profile + Semantic Scholar Author |
| `exports/publications.csv` | Publikasi gabungan OpenAlex + Google Scholar + Semantic Scholar (setelah dedup lintas sumber) |
| `exports/lecturer_publications.csv` | Link dosen↔publikasi (many-to-many) |
| `exports/lecturer_metrics.csv` | h-index & total citations per dosen — 1 baris/dosen, prioritas OpenAlex > Google Scholar > Semantic Scholar (fallback berjenjang kalau sumber sebelumnya kosong untuk dosen tsb, lihat §3) |
| `exports/lecturer_research_tags_candidates.csv` | **Draft** kandidat tag riset (kolom `full_name, tag_slug`, maks. 6 tag/dosen), hasil keyword-matching judul+abstract publikasi — belum di-insert ke DB, wajib direview manusia dulu (lihat §3) |
| `exports/lecturer_research_clusters_candidates.csv` | **Draft** kandidat cluster utama (kolom `full_name, cluster_slug`, 1 cluster/dosen), diturunkan dari tag skor tertinggi milik tiap dosen — belum di-update ke DB, wajib direview manusia dulu (lihat §3) |
| `sql/seed_vocabulary.sql` | Controlled vocabulary awal: 5 `research_clusters`, 23 `research_tags` — **satu-satunya file `.sql`** di paket ini, dianggap konfigurasi/vocabulary tetap, bukan hasil crawling |
| `db/research_tag_keywords.py` | Kamus keyword per tag riset yang dipakai generator kandidat tag & cluster |
| `db/research_tag_cluster_map.py` | Peta tag_slug → cluster_slug, mengikuti `sql/seed_vocabulary.sql` |
| `db/generate_research_tag_candidates.py` | Script yang menghasilkan `lecturer_research_tags_candidates.csv` — bisa dijalankan ulang kalau kamus keyword diperbarui |
| `db/generate_research_cluster_candidates.py` | Script yang menghasilkan `lecturer_research_clusters_candidates.csv` |

**Perubahan nama file dari handoff sebelumnya:** `lecturers_openalex.csv` → `lecturers.csv`, `publications_openalex.csv` → `publications.csv`, dst — karena pipeline sekarang multi-source (bukan cuma OpenAlex), nama generik lebih akurat. Isi kolom lama tetap sama persis (kolom baru ditambah di akhir, tidak ada kolom lama yang dihapus/diganti nama). Semua varian `.json` (mis. `lecturers_openalex.json`) sudah **dihentikan** — pipeline sekarang hanya menulis CSV.

## 2. Cara Baca Data

Ikuti struktur tabel di `sql/erd_kbk_data.md`. Ringkas:

- `lecturers.csv` — profil dasar dosen + ID lintas platform (`openalex_author_id`, `google_scholar_id`, `semantic_scholar_id`, `orcid_id`, dst), plus kolom status resolusi tiap sumber (`openalex_resolution_method`, `google_scholar_resolution_method`, `semantic_scholar_resolution_method`)
- `publications.csv` — satu baris = satu publikasi, kolom `source` menandai asalnya (`OPENALEX`, `GOOGLE_SCHOLAR`, atau `SEMANTIC_SCHOLAR`); publikasi yang sama dari beberapa sumber sudah digabung lewat dedup lintas sumber (DOI exact match, atau title+year similarity untuk publikasi tanpa DOI — publikasi Google Scholar hampir selalu tanpa DOI)
- `lecturer_publications.csv` — tabel penghubung many-to-many, satu publikasi bisa terhubung ke beberapa dosen KBK (multi-author internal)
- `lecturer_metrics.csv` — snapshot h-index & total citations per dosen, **1 baris per dosen** (bukan riwayat, selalu snapshot terakhir). Kolom `source` menunjukkan sumber yang benar-benar dipakai untuk baris itu
- `research_clusters` / `research_tags` — vocabulary sudah di-seed (`sql/seed_vocabulary.sql`). Assignment ke dosen (`lecturer_research_tags`, dan kolom `lecturers.primary_research_cluster_id`) **masih kosong/NULL**, tapi sudah ada draft kandidat untuk keduanya (lihat §3)
- `lecturer_supervision_quota` / `supervised_students` / `teaching_assistants` — tabel baru di schema, **skema saja, belum ada data** apapun (lihat §3)

**Field yang WAJIB dibaca sebelum ditampilkan ke publik:**
- `verified_status` — semua baris `'NEEDS_REVIEW'`. Tidak ada satupun yang `VERIFIED` dari pipeline. Keputusan tampil/tidak ada di layer review kalian.
- `external_ids` — di CSV, kolom ini berupa **string JSON dalam satu sel** (mis. `{"openalex": "https://openalex.org/W...", "doi": "..."}`, `{"google_scholar": "..."}`, atau `{"semantic_scholar": "...", "doi": "..."}`), karena CSV tidak native menyimpan nested object. `json.loads()` kolom ini kalau perlu diakses terstruktur.

## 3. ⚠️ Known Gaps / Placeholder yang WAJIB Diketahui

| Gap | Detail | Yang Perlu Dilakukan |
|---|---|---|
| **`nip_or_staff_id` bukan NIP asli** | `dosen_source.csv` dari departemen **tidak punya kolom NIP**. Sebagai placeholder sementara, kolom ini diisi dengan **nilai `sinta_id`** — bukan NIP sungguhan. | Ganti begitu NIP asli didapat dari departemen. Jangan pakai kolom ini sebagai NIP resmi di production. |
| **1 dosen tidak ter-resolve ke OpenAlex** | "Rr. Eny Sukani Rahayu" — `openalex_author_id` kosong, tidak ada baris publikasi OpenAlex untuknya di batch ini. | Perlu dicari manual (mungkin author profile OpenAlex belum terbentuk / nama terlalu unik untuk fuzzy search). |
| **32 dari 64 dosen di-resolve OpenAlex lewat name-search, bukan ID** | ORCID hanya berhasil match 31 dosen. Sisanya dicocokkan lewat *search nama + filter afiliasi UGM* — kurang akurat dibanding matching by ID (lihat kolom `openalex_resolution_method` di `lecturers.csv`). | Sudah di-spot-check manual dan hasil cocok, tapi tetap disarankan random-check tambahan sebelum full percaya 100%. |
| **Google Scholar rawan gagal parsial per-run (terkonfirmasi, bukan cuma teori)** | Tidak ada API resmi Google Scholar — fetcher (`fetchers/google_scholar.py`) scraping via library `scholarly`, jauh lebih rawan rate-limit/captcha dibanding OpenAlex. Sudah terjadi di test run: setelah beberapa dosen awal berhasil (HTTP 200), Google mulai menyajikan halaman captcha (`.../sorry/index`, HTTP 429) dan **tanpa pembatas dari sisi kita, `scholarly` retry tanpa henti** — pipeline menggantung sampai dihentikan manual. Sudah diperbaiki: `scholarly.set_retries(SCHOLARLY_MAX_RETRIES)`/`set_timeout()` diset di `_fetch_live()` — **`SCHOLARLY_MAX_RETRIES = 1`: sekali gagal untuk satu dosen, langsung skip ke dosen berikutnya, tidak retry beruntun** (retry setelah kena block cuma memperpanjang block-nya, bukan menyelesaikannya). Jumlah publikasi yang di-`fill()` penuh per dosen juga diturunkan drastis (`FILL_TOP_N_PUBLICATIONS = 5`, dari sebelumnya 50) dengan jeda antar-fill (`FILL_DELAY_SECONDS = 3`), plus jeda antar-dosen (`GOOGLE_SCHOLAR_LECTURER_DELAY_SECONDS = 5` di `pipeline.py`). `google_scholar_resolution_method` di `lecturers.csv` tetap bisa bernilai `error` untuk sebagian dosen di batch tertentu meski `google_scholar_id`-nya valid — sekarang gagal cepat, bukan menggantung. | Kalau banyak `error` di satu batch, jalankan ulang pipeline nanti (jangan langsung retry beruntun — berisiko IP kena block lebih lama). Publikasi/metrik dari dosen yang gagal di satu batch akan terisi di batch berikutnya. Kalau block masih sering terjadi meski sudah dilambatkan, pertimbangkan turunkan `FILL_TOP_N_PUBLICATIONS` lebih jauh (bahkan ke 0) atau pakai proxy (`scholarly.use_proxy`). |
| **Publikasi Google Scholar minim metadata** | Tidak ada DOI, `venue`/`publication_type` kadang cuma tebakan heuristik dari field bebas (lihat `cleaners/normalize.py::normalize_google_scholar_publication`), `publication_date` selalu kosong (Google Scholar cuma kasih tahun). | Bukan bug — keterbatasan sumber data. Kalau OpenAlex sudah punya publikasi yang sama, dedup title+year akan menggabungkannya dan versi OpenAlex yang lebih lengkap akan dominan (lihat `cleaners/merge.py`). |
| **`lecturer_metrics.csv` cuma 1 baris/dosen meski 3 sumber dicoba** | Skema DB (`lecturer_metrics`) PK-nya `lecturer_id` saja — 1-to-1 per dosen, bukan per-(dosen,sumber). Pipeline memilih 1 sumber per dosen dengan prioritas berjenjang: OpenAlex > Google Scholar > Semantic Scholar (dipakai kalau semua sumber di atasnya kosong untuk dosen tsb). | Kalau ke depan ketiga sumber ingin disimpan terpisah, skema `lecturer_metrics` perlu diubah PK-nya jadi `(lecturer_id, source)` — didiskusikan dulu, belum dilakukan di batch ini. |
| **Semantic Scholar rate limit ketat tanpa API key** | API resmi (Graph API v1), tapi kuota tanpa key jauh lebih kecil dari OpenAlex (shared pool publik, rawan 429). Tim Data belum punya key — key gratis akan didaftarkan tim developer (https://www.semanticscholar.org/product/api). Kode sudah siap pakai key kapan saja: isi `SEMANTIC_SCHOLAR_API_KEY` di `.env`, fetcher otomatis kirim header `x-api-key` kalau terisi, tanpa perlu ubah kode. **Retry sengaja diminimalkan**: `HttpClient` untuk Semantic Scholar diset `max_attempts=1` (`SEMANTIC_SCHOLAR_MAX_ATTEMPTS` di `fetchers/semantic_scholar.py`) — sekali gagal untuk satu dosen, langsung skip, bukan retry bertingkat (429 dari rate limit ketat biasanya bukan error transien, retry berkali-kali cuma buang waktu). OpenAlex tetap pakai default `HttpClient` (retry 4x) karena jauh lebih stabil. | Daftarkan API key gratis lalu isi `.env` — mengurangi frekuensi 429 secara signifikan. Tanpa key pipeline tetap jalan, tapi banyak dosen kemungkinan gagal di tahap Semantic Scholar (bukan bug, memang keterbatasan rate limit tanpa key) — publikasi dari OpenAlex+Google Scholar tetap lengkap seperti biasa. |
| **840+ publikasi (OpenAlex) tidak punya DOI valid** | Publikasi lama/lokal (skripsi, prosiding kecil, dll) sering tidak terindeks DOI. `doi` kosong untuk baris-baris ini — bukan data hilang, memang sumbernya tidak menyediakan. | Dedup untuk baris tanpa DOI mengandalkan title+year similarity (lihat Contract §6.1). |
| **`research_tags` belum di-assign ke dosen (tabel DB masih kosong)** | Draft otomatis di `exports/lecturer_research_tags_candidates.csv` — hasil keyword-matching judul+abstract publikasi tiap dosen terhadap kamus keyword 23 tag (`db/research_tag_keywords.py`). Kolom hanya `full_name, tag_slug` (maks. 6 tag per dosen, urutan tidak menandakan prioritas). | **Wajib direview manusia sebelum insert** — keyword-matching bisa salah konteks. 2 dosen (Rr. Eny Sukani Rahayu, Nailil Husna) tidak dapat kandidat sama sekali — perlu ditentukan manual sepenuhnya. |
| **`lecturers.primary_research_cluster_id` masih NULL semua** | Draft kandidat di `exports/lecturer_research_clusters_candidates.csv` (kolom `full_name, cluster_slug`), diturunkan dari cluster induk milik tag dengan skor keyword-match tertinggi per dosen. **Distribusinya timpang** — banyak dosen jatuh ke cluster `intelligent-systems-data` karena kata kunci AI/ML paling sering nyerempet lintas bidang. | **Wajib direview manusia, jangan langsung dipakai apa adanya** — cek terutama dosen yang ter-assign ke `intelligent-systems-data` tapi keahlian utamanya sebenarnya bidang lain. |
| **3 tabel baru (`lecturer_supervision_quota`, `supervised_students`, `teaching_assistants`) masih skema kosong** | Ditambahkan atas permintaan tim developer untuk menampung data ketersediaan bimbingan (kuota), mahasiswa bimbingan aktif, dan asisten dosen. **Belum ada data sama sekali** — Tim Data belum punya sumber (CSV/SIA/input manual prodi) untuk field-field ini. | Developer/tim terkait perlu menentukan dan menyediakan sumber datanya. |

## 4. Cara Menjalankan Pipeline Sendiri (untuk Cron / Re-run)

`pipeline.py` adalah satu-satunya entry point crawling+cleaning. Tim Data **tidak** menyediakan service/scheduler-nya — itu tanggung jawab tim developer (mis. cron, systemd timer, Airflow); `pipeline.py` didesain agar mudah dipanggil dari orkestrator manapun:

```bash
pip install -r requirements.txt
python pipeline.py
```

- **Exit code:** `0` = sukses (termasuk sukses parsial per-dosen — beberapa dosen gagal resolve itu hal normal, dicatat sebagai warning di log, bukan kegagalan pipeline). `1` = gagal total (mis. `dosen_source.csv` tidak terbaca/kosong) — orkestrator sebaiknya alert kalau exit code ini muncul.
- **Log:** ditulis ke `pipeline.log` (working directory) dan stdout — file log ini **tidak** ikut ter-commit ke git, akan ditimpa/ditumpuk tiap run tergantung setup orkestrator.
- **Output:** `exports/lecturers.csv`, `exports/publications.csv`, `exports/lecturer_publications.csv`, `exports/lecturer_metrics.csv` — timpa file lama tiap run (tidak versioned per-batch secara otomatis; kalau perlu histori per-batch, orkestrator yang copy/rename setelah tiap run selesai, mis. pakai `fetch_batch_id` yang ada di `publications.csv` sebagai penanda).
- **Rekomendasi frekuensi:** mingguan, bukan harian — terutama karena fetcher Google Scholar scraping (lihat gap di §3), run yang terlalu sering meningkatkan risiko rate-limit/block.
- **Setelah pipeline selesai**, load ke Postgres staging (opsional, kalau developer mau data langsung masuk DB bukan cuma CSV): `python -m db.load_staging` — baca CSV dari `exports/`, upsert idempotent (aman dijalankan berkali-kali). Prasyarat: skema `research_clusters`/`research_tags`/dst sudah dibuat di sisi developer sesuai `sql/erd_kbk_data.md`, dan `.env` berisi `DATABASE_URL`.
