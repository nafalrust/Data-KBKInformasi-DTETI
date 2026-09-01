# **Contract: Cleaning & Normalization**

## **KBK TI Data Layer: Pedoman Wajib untuk Semua Data yang Masuk Staging**

**Dokumen ini untuk:** Tim Data (Lead, Staff 1, Staff 2\) — dibaca sebelum menulis kode apapun di `cleaners/normalize.py` dan `cleaners/merge.py` **Sifat:** Kontrak kerja internal — bukan opsional, bukan gaya penulisan bebas. Semua normalizer per sumber (OpenAlex, Semantic Scholar, CrossRef, Google Scholar, dan nanti SINTA/Scopus/GARUDA) **wajib** menghasilkan output yang patuh pada aturan di sini, supaya hasil kerja 3 orang paralel tetap konsisten satu sama lain dan cocok masuk skema `sql/schema_staging.sql`. **Rujukan:** `PRD_Data_Engineering_KBK_TI.md` §6 (Data Model, ERD & Vocabulary) **Cakupan:** Profil Dosen (`lecturers`), Publikasi (`publications`), Metrik Akademik (`lecturer_metrics`), dan Controlled Vocabulary (`research_clusters`, `research_tags`)

---

## **Daftar Isi**

1. [Prinsip Umum](https://claude.ai/chat/82776e1e-e6c7-4bb5-9e4d-6f6c87c4d822#1-prinsip-umum)  
2. [Normalisasi Field — Publikasi](https://claude.ai/chat/82776e1e-e6c7-4bb5-9e4d-6f6c87c4d822#2-normalisasi-field--publikasi)  
3. [Normalisasi Field — Profil Dosen](https://claude.ai/chat/82776e1e-e6c7-4bb5-9e4d-6f6c87c4d822#3-normalisasi-field--profil-dosen)  
4. [Normalisasi Field — Metrik Akademik](https://claude.ai/chat/82776e1e-e6c7-4bb5-9e4d-6f6c87c4d822#4-normalisasi-field--metrik-akademik)  
5. [Normalisasi & Tata Kelola — Controlled Vocabulary](https://claude.ai/chat/82776e1e-e6c7-4bb5-9e4d-6f6c87c4d822#5-normalisasi--tata-kelola--controlled-vocabulary)  
6. [Aturan Dedup & Matching](https://claude.ai/chat/82776e1e-e6c7-4bb5-9e4d-6f6c87c4d822#6-aturan-dedup--matching)  
7. [Logging & Audit Trail Wajib](https://claude.ai/chat/82776e1e-e6c7-4bb5-9e4d-6f6c87c4d822#7-logging--audit-trail-wajib)  
8. [Yang Sengaja Tidak Diotomasi di Horizon A](https://claude.ai/chat/82776e1e-e6c7-4bb5-9e4d-6f6c87c4d822#8-yang-sengaja-tidak-diotomasi-di-horizon-a)  
9. [Checklist Sebelum Merge PR Normalizer Baru](https://claude.ai/chat/82776e1e-e6c7-4bb5-9e4d-6f6c87c4d822#9-checklist-sebelum-merge-pr-normalizer-baru)

---

## **1\. Prinsip Umum**

* **Normalisasi terjadi di level aplikasi, bukan di database.** Data mentah dari `raw_cache/` tidak pernah langsung masuk tabel staging — selalu lewat fungsi `normalize_<sumber>()` dulu.  
* **Setiap fungsi normalizer HARUS pure function** — input raw JSON/HTML hasil parsing, output objek Pydantic (`PublicationSchema`/`LecturerSchema`/dst), tidak ada side effect (tidak nulis ke file/DB di dalam fungsi normalizer itu sendiri).  
* **Kalau data mentah tidak lengkap/rusak, normalizer tidak boleh menebak.** Isi field yang tidak ada dengan `None`, bukan string kosong `""`, angka `0`, atau placeholder seperti `"-"`/`"N/A"` — beda makna antara "tidak ada datanya" vs "datanya memang kosong/nol".  
* **Setiap normalizer wajib punya unit test** dengan minimal 3 kasus: data lengkap normal, data dengan field hilang, data dengan format aneh (idealnya contoh nyata dari `raw_cache/`, bukan data karangan) — lihat `tests/test_normalize.py`.  
* **Konsistensi lintas sumber lebih penting daripada akurasi maksimal per sumber.** Kalau ada trade-off antara "OpenAlex bisa dapat data lebih detail dengan cara khusus" vs "semua sumber diperlakukan dengan pola yang sama", pilih konsistensi — supaya `cleaners/merge.py` bisa membandingkan apel dengan apel.

---

## **2\. Normalisasi Field — Publikasi**

### **2.1 Judul (`title`)**

* Trim whitespace di awal/akhir.  
* **Jangan** ubah kapitalisasi asli — judul paper punya kapitalisasi bermakna (akronim, nama spesies, dll), jangan di-title-case atau di-lowercase paksa.  
* Hapus tag HTML/markup kalau ada residu dari scraping (`<i>`, `<b>`, entity `&amp;`, dll) — ambil teksnya saja.  
* `title` adalah `NOT NULL` di skema — normalizer **wajib** skip/reject baris yang judulnya kosong setelah trim, jangan simpan string kosong.

### **2.2 DOI (`doi`) — Kunci Dedup Utama**

Field paling kritis karena jadi constraint `UNIQUE` di database. Urutan proses wajib:

1. Trim whitespace.  
2. Lowercase seluruhnya (`10.1109/abc.2024.123`, bukan campur besar-kecil).  
3. Hapus prefix apapun sebelum `10.` — termasuk `https://doi.org/`, `http://dx.doi.org/`, `doi:`, `DOI:`.  
4. Kalau setelah proses di atas string tidak diawali `10.`, anggap **bukan DOI valid** → set `None`, jangan simpan sebagai DOI meski ada isinya.  
5. Hasil akhir contoh: `10.1109/tpami.2023.1234567`.

```py
def normalize_doi(raw: str | None) -> str | None:
    if not raw:
        return None
    doi = raw.strip().lower()
    doi = re.sub(r'^(https?://)?(dx\.)?doi\.org/', '', doi)
    doi = re.sub(r'^doi:\s*', '', doi)
    return doi if doi.startswith('10.') else None
```

### **2.3 Tahun & Tanggal (`year`, `publication_date`)**

* `year` harus `int`, bukan string.  
* Kalau sumber cuma kasih tahun tanpa tanggal lengkap, `publication_date` boleh `None` — jangan menebak tanggal dengan `01-01` default, itu data palsu.  
* Kalau sumber kasih tahun di luar rentang wajar (`< 1900` atau `> tahun berjalan + 1`), treat sebagai data rusak → `None`, jangan dipaksa masuk. Catat di log warning (§7).

### **2.4 Nama Author Mentah (`authors_text`)**

* Simpan **apa adanya** dari sumber (setelah trim whitespace) — jangan coba resolve ke `lecturer_id` di tahap normalisasi. Resolusi author dilakukan terpisah di tahap merge/matching (§6.3), bukan di normalizer per-sumber.  
* Kalau sumber kasih list author sebagai array, join dengan `"; "` (titik-koma \+ spasi) sebagai separator standar seluruh pipeline — konsisten di semua sumber, jangan campur `,` di satu sumber dan `;` di sumber lain.  
* `authors_text` adalah `NOT NULL` — normalizer wajib reject baris tanpa data author sama sekali.

### **2.5 Tipe Publikasi (`publication_type`)**

Wajib dipetakan ke salah satu **enum tetap** ini — tidak boleh nilai bebas dari sumber lolos begitu saja:

```
JOURNAL | CONFERENCE | BOOK_CHAPTER | PREPRINT | OTHER
```

Tabel mapping (perluas di kode kalau ketemu istilah baru dari sumber — jangan biarkan istilah asing lolos tanpa masuk mapping ini):

| Istilah dari sumber | Map ke |
| ----- | ----- |
| `journal-article`, `article` | `JOURNAL` |
| `proceedings-article`, `conference-paper` | `CONFERENCE` |
| `book-chapter` | `BOOK_CHAPTER` |
| `posted-content`, `preprint` | `PREPRINT` |
| (tidak dikenali / kosong) | `OTHER` |

### **2.6 Abstract, Venue, URL**

* **`abstract`**: kalau sumber kasih HTML/markup, atau format khusus (OpenAlex memakai *inverted index* untuk abstract), harus direkonstruksi jadi plain text dulu sebelum disimpan — jangan simpan struktur mentahnya.  
* **`venue`**: nama jurnal/prosiding apa adanya, trim whitespace saja. **Jangan** disingkat/diseragamkan manual — standardisasi nama venue bukan scope Horizon A (lihat §8).  
* **`url`**: harus URL valid (diawali `http://`/`https://`) atau `None` — jangan simpan path relatif atau string yang bukan URL.

### **2.7 Citation Count (`citation_count`)**

* `int`, minimal `0`.  
* Kalau sumber tidak menyediakan field ini sama sekali → `None` (beda makna dari `0`, yang berarti "tercatat 0 sitasi").

### **2.8 Field Wajib yang Tidak Boleh Kosong (Kontrak dengan Tim Website)**

Penegasan ulang karena paling sering lupa saat buru-buru — **setiap baris `publications` yang masuk staging DB wajib punya:**

| Field | Aturan |
| ----- | ----- |
| `source` | Salah satu dari enum: `OPENALEX`, `SEMANTIC_SCHOLAR`, `CROSSREF`, `GOOGLE_SCHOLAR`, `SINTA`, `SCOPUS`, `CSV_IMPORT` — tidak boleh nilai lain |
| `external_ids` | Minimal berisi ID dari sumber asal baris itu (mis. `{"openalex": "W123..."}`). Boleh dict kosong `{}` kalau sumber benar-benar tidak kasih ID apapun (jarang), tapi **tidak boleh** `None`/`NULL` |
| `verified_status` | **Selalu** `'NEEDS_REVIEW'` dari normalizer manapun. Tidak ada satu baris pun yang boleh keluar dari pipeline dengan status `VERIFIED` — itu keputusan manusia lewat review layer tim website |

---

## **3\. Normalisasi Field — Profil Dosen**

### **3.1 Nama (`full_name`)**

Field paling rawan karena dipakai untuk matching ke OpenAlex/Semantic Scholar (yang sensitif terhadap variasi nama).

* Pisahkan **gelar** dari nama inti. Simpan nama inti di `full_name`, gelar depan/belakang di `academic_title` (field terpisah, jangan digabung jadi satu string).  
* Contoh: input CSV `"Dr. Budi Santoso, S.Kom., M.Kom."` → `full_name = "Budi Santoso"`, `academic_title = "Dr., S.Kom., M.Kom."`.  
* Kapitalisasi: title case standar (`Budi Santoso`, bukan `BUDI SANTOSO` atau `budi santoso`) — ini satu-satunya field teks yang **boleh** dipaksa title case, karena beda dari judul paper (§2.1), nama orang memang konvensinya begitu.  
* `full_name` adalah `NOT NULL` — baris tanpa nama valid tidak boleh masuk staging.

### **3.2 Daftar Gelar & Pola Regex**

Buat daftar eksplisit di kode (bukan hardcode sekali pakai, harus mudah diperluas) — minimal cover pola umum akademik Indonesia:

```
Dr., Prof., Ir., S.Kom., M.Kom., S.T., M.T., Ph.D., M.Sc., S.Si., M.Si., dst.
```

Kalau ketemu pola gelar yang belum ada di daftar saat memproses data asli, **tambahkan ke daftar** — jangan biarkan nempel di `full_name` sebagai jalan pintas.

### **3.3 NIP / Staff ID (`nip_or_staff_id`)**

* Hapus semua karakter non-digit kalau formatnya NIP standar (strip, spasi, titik) — simpan sebagai digit murni.  
* **Jangan** buang leading zero — NIP valid bisa diawali `0`.  
* `nip_or_staff_id` adalah `NOT NULL` — ini identitas dasar dari CSV departemen, wajib ada sebelum baris dosen bisa masuk staging.

### **3.4 Email**

* Lowercase seluruhnya.  
* Validasi format dasar (ada `@`, ada domain valid) — kalau tidak valid, set `None`, jangan simpan string sampah.  
* **Tidak** melakukan verifikasi domain institusi secara aktif di Horizon A (cukup validasi format dasar) — verifikasi lebih ketat bisa jadi item Horizon B kalau memang dibutuhkan.

### **3.5 ID Lintas Platform**

Berlaku untuk `sinta_id`, `scopus_author_id`, `google_scholar_id`, `orcid_id`, `openalex_author_id`, `semantic_scholar_id`:

* Trim whitespace, simpan apa adanya sesuai format resmi masing-masing platform — jangan diproses/diubah lebih lanjut selain trim, kecuali disebutkan khusus di bawah.  
* **`orcid_id`** — format wajib `0000-0000-0000-0000` (4 blok 4 digit dipisah strip). Kalau sumber kasih dalam bentuk URL (`https://orcid.org/0000-...`), ekstrak ID murninya saja, jangan simpan URL penuh.  
* **`google_scholar_id`** — sama, ekstrak dari URL profil (`https://scholar.google.com/citations?user=<ID>`) kalau sumbernya berupa URL; `google_scholar_url` menyimpan URL lengkapnya secara terpisah.  
* **`sinta_id`** — `NOT NULL` di skema (field Wajib sesuai PRD Website). Kalau tidak ditemukan otomatis di CSV departemen, wajib dicari manual sebelum baris dosen dianggap "siap" masuk staging (lihat PRD §4.1).  
* Field yang belum terisi → `None`, **bukan** string `"-"`, `"N/A"`, atau `""`.

---

## **4\. Normalisasi Field — Metrik Akademik**

Tabel `lecturer_metrics` (h-index, total citations, SINTA score) punya karakter beda dari `publications`/`lecturers` — ini **angka agregat yang berubah tiap sync**, bukan data statis. Aturan khusus:

### **4.1 Sifat Data**

* Setiap baris `lecturer_metrics` mewakili **snapshot terakhir**, bukan riwayat historis. Update berarti **replace nilai lama**, bukan insert baris baru (`fetched_at` cukup untuk tahu kapan terakhir update — tidak perlu tabel riwayat terpisah di Horizon A).  
* `lecturer_id` adalah **primary key sekaligus foreign key** — satu dosen maksimal satu baris metrik.

### **4.2 Aturan per Field**

| Field | Aturan Normalisasi |
| ----- | ----- |
| `h_index` | `int`, minimal `0`. Kalau sumber tidak menyediakan → `None`, bukan `0` |
| `total_citations` | `int`, minimal `0`. Sama seperti `citation_count` di publikasi — `None` kalau tidak tersedia, bukan `0` |
| `sinta_score` | `numeric`, tetap `None` di Horizon A (belum ada fetcher SINTA) — kolom sudah disiapkan supaya tidak perlu migrasi ulang saat Horizon B |
| `source` | Wajib diisi salah satu: `OPENALEX`, `SINTA` — konsisten dengan enum `source` di `publications`, tambah entri baru kalau sumber metrik baru ditambahkan |
| `fetched_at` | Selalu di-update ke waktu fetch terbaru setiap kali sync jalan, meskipun angkanya kebetulan tidak berubah dari sync sebelumnya |

### **4.3 Konsistensi dengan Publikasi**

* `total_citations` di `lecturer_metrics` **tidak wajib** sama persis dengan hasil `SUM(citation_count)` dari tabel `publications` milik dosen itu — angka metrik agregat dari OpenAlex/SINTA dihitung dari basis data mereka sendiri (yang mungkin mencakup publikasi yang belum ter-crawl ke `publications` kita, atau sebaliknya). **Jangan** mencoba "mengoreksi" salah satu angka supaya cocok dengan angka lainnya — keduanya sah berdiri sendiri, dan pengguna website nantinya membaca `lecturer_metrics` sebagai metrik resmi, bukan hasil kalkulasi dari daftar publikasi yang ditampilkan.

---

## **5\. Normalisasi & Tata Kelola — Controlled Vocabulary**

Berbeda dari §2–4, `research_clusters` dan `research_tags` **bukan** hasil crawling — ini data yang disusun manual oleh tim Data (lihat PRD §6.4). Tapi tetap butuh aturan normalisasi supaya konsisten, terutama karena field ini yang menghubungkan profil dosen ke sistem pencarian/filter di website.

### **5.1 Penamaan (`name`)**

* Title case standar, tanpa singkatan yang tidak umum (`Machine Learning`, bukan `ML` atau `machine learning`).  
* Konsisten Bahasa Inggris **atau** Bahasa Indonesia — pilih satu, jangan campur dalam satu daftar (rekomendasi: Bahasa Inggris untuk istilah teknis yang memang lazim dipakai begitu di bidang CS/informatika, kecuali PIC KBK menyatakan preferensi lain — ini salah satu poin yang perlu dikonfirmasi bareng validasi vocabulary di PRD §11).

### **5.2 Slug (`slug`)**

* Diturunkan otomatis dari `name`: lowercase, spasi jadi strip (`-`), buang karakter selain huruf/angka/strip.  
* Contoh: `"Natural Language Processing"` → `natural-language-processing`.  
* `slug` adalah `UNIQUE NOT NULL` di kedua tabel (`research_clusters`, `research_tags`) — proses pembuatan slug **wajib** cek collision (kalau ada slug yang sudah dipakai, tambahkan suffix, jangan biarkan gagal insert diam-diam).

### **5.3 Relasi Tag ↔ Cluster**

* Setiap `research_tags` **wajib** punya `cluster_id` terisi — tidak ada tag "mengambang" tanpa cluster induk (`cluster_id` sebaiknya di-treat sebagai wajib di level aplikasi meski skema DDL saat ini belum eksplisit `NOT NULL`; ini salah satu hal yang perlu diperkuat saat Lead review ulang `schema_staging.sql`).  
* Satu tag hanya boleh masuk **satu** cluster (relasi belongs-to, bukan many-to-many) — kalau ada kebutuhan satu topik masuk dua cluster sekaligus, itu tanda cluster-nya perlu didefinisikan ulang, bukan alasan melonggarkan aturan ini.

### **5.4 Proses Penambahan Tag Baru (Selama Cleaning Berjalan)**

Karena vocabulary diisi bertahap saat cleaning CSV departemen (PRD §4.1/§6.4), berlaku aturan tambahan:

* Tag baru yang muncul dari observasi bidang keahlian dosen **dicatat dulu di draft** (misal spreadsheet terpisah atau todo list di PR), **bukan** langsung di-`INSERT` ke `sql/seed_vocabulary.sql` tanpa review Lead — mencegah proliferasi tag yang terlalu spesifik/tumpang tindih (`Cybersecurity` dan `Keamanan Siber` sebagai dua tag beda, misalnya).  
* Sebelum `seed_vocabulary.sql` dikunci sebagai "v1" untuk diserahkan ke tim website, wajib ada satu putaran review: cek tidak ada tag duplikat secara makna (beda ejaan/istilah tapi maksud sama), cek semua tag punya cluster yang masuk akal.

### **5.5 Assignment Tag ke Dosen (`lecturer_research_tags`)**

* `is_primary` (boolean) menandai tag yang paling representatif untuk dosen itu — **maksimal satu tag primary per dosen**, sisanya `is_primary = false`. Ini dipakai nanti untuk tampilan ringkas di listing dosen (tidak menampilkan semua tag sekaligus).  
* Penentuan tag mana yang `is_primary` dilakukan manual oleh Staff yang mengerjakan cleaning berdasarkan bidang keahlian utama yang tertulis di CSV departemen — bukan tebakan otomatis dari hasil crawling publikasi (crawling publikasi belum tentu representasi akurat dari bidang keahlian utama, terutama untuk dosen dengan publikasi lintas topik).

---

## **6\. Aturan Dedup & Matching**

### **6.1 Dedup Publikasi (Level: dalam satu dosen, lintas sumber)**

Urutan pengecekan, berhenti di langkah pertama yang match:

1. **DOI ternormalisasi sama persis** (hasil dari §2.2) → dianggap publikasi yang sama, **gabung jadi satu baris**, jangan insert baru.  
2. **Tidak ada DOI di salah satu/kedua sisi** → fallback ke title similarity:  
   * Normalisasi title dulu: lowercase, hapus tanda baca, hapus spasi ganda.  
   * Threshold yang dipakai: **≥ 90% kemiripan** (Levenshtein ratio / `rapidfuzz.token_sort_ratio`) **DAN** tahun publikasi sama (atau selisih maksimal 1 tahun, untuk kasus tahun preprint vs versi terbit resmi beda 1 tahun).  
   * Kalau kedua syarat terpenuhi → anggap sama, gabung.  
   * Kalau title mirip tapi tahun beda jauh, atau similarity di bawah threshold → **anggap publikasi berbeda**, jangan digabung paksa (lebih aman ada duplikat masuk `NEEDS_REVIEW` untuk direview manusia, daripada dua publikasi berbeda malah tergabung jadi satu dan kehilangan salah satunya).

### **6.2 Proses Penggabungan (Merge) Saat Dedup Ketemu**

Kalau dua baris dari sumber berbeda dianggap publikasi yang sama:

| Field | Aturan Penggabungan |
| ----- | ----- |
| `external_ids` | Union dari keduanya — gabung semua ID, bukan pilih salah satu |
| `title`, `venue`, `year` | Pakai dari sumber dengan prioritas: **OpenAlex \> Semantic Scholar \> CrossRef \> Google Scholar** (ini "system of record" pipeline kita) |
| `abstract` | Pakai yang **paling panjang/lengkap** dari sumber manapun — tidak ikut aturan prioritas sumber, karena sumber prioritas rendah kadang justru punya abstract lebih lengkap |
| `citation_count` | Pakai angka **tertinggi** di antara sumber yang tersedia — masing-masing platform hitung sitasi dari basis datanya sendiri, jadi wajar beda, ambil yang paling representatif |
| `source` | Tetap catat sumber utama (pemenang prioritas di atas) di kolom `source`, tapi semua sumber yang berkontribusi tercatat lengkap di `external_ids` |

### **6.3 Matching Author ke Dosen (`authors_text` → `lecturer_id`)**

Proses terpisah dari dedup publikasi, dilakukan **setelah** publikasi ternormalisasi:

* **Prioritas 1 — Matching by ID**: kalau dosen punya `openalex_author_id`/`semantic_scholar_id` di profilnya, utamakan matching lewat ID itu, bukan nama — jauh lebih akurat, dan ini alasan utama kenapa kedua field itu penting ada di skema staging (lihat PRD §6.5).  
* **Prioritas 2 — Exact name match**: kalau ID tidak tersedia, cocokkan nama di `authors_text` terhadap `full_name` di tabel `lecturers` (setelah normalisasi kapitalisasi keduanya). Match persis → langsung link via `lecturer_publications`.  
* **Tidak exact match tapi mirip** (typo, urutan nama beda, singkatan nama depan) → **jangan auto-link**. Catat di tabel/log `unmatched_authors` untuk direview manual. Matching otomatis yang agresif untuk nama adalah sumber kesalahan paling umum di data seperti ini — nama umum Indonesia bisa merujuk ke banyak orang berbeda, salah link lebih berbahaya daripada tidak link sama sekali.

### **6.4 Dedup Controlled Vocabulary (Tag & Cluster)**

* Sebelum menambah tag baru ke `research_tags`, **wajib cek dulu** apakah sudah ada tag dengan makna sama (beda ejaan/istilah) — proses ini manual oleh Staff yang mengerjakan cleaning, dibantu pencarian sederhana (`ILIKE` di database, bukan fuzzy matching otomatis — vocabulary ini kecil, cek manual lebih aman daripada risiko duplikat lolos algoritma).  
* Tidak ada auto-merge untuk tag yang mirip — beda dari dedup publikasi, kesalahan gabung tag punya dampak lebih luas (mempengaruhi semua dosen yang sudah pakai tag itu), jadi keputusan gabung/tidak selalu manual dan disetujui Lead.

---

## **7\. Logging & Audit Trail Wajib**

Setiap kali normalizer atau merge logic **membuang/menolak** data (bukan cuma transform), wajib tercatat, tidak boleh silent:

* Baris publikasi yang di-skip karena DOI tidak valid setelah normalisasi.  
* Baris publikasi dengan tahun di luar rentang wajar.  
* Kandidat dedup publikasi yang title-nya mirip tapi tidak lolos threshold (untuk audit — siapa tahu threshold §6.1 perlu disesuaikan di kemudian hari).  
* Author yang gagal di-match ke dosen manapun (§6.3).  
* Baris dosen yang direject karena `full_name`/`nip_or_staff_id` kosong setelah cleaning.  
* Tag baru yang diusulkan tapi belum di-approve masuk `seed_vocabulary.sql` (§5.4).

**Format minimal:** append ke file log per batch (`fetch_batch_id` sebagai acuan), bukan print ke terminal saja — supaya bisa direview belakangan tanpa perlu re-run pipeline dari nol.

---

## **8\. Yang Sengaja Tidak Diotomasi di Horizon A**

Supaya jelas batasnya, dan tidak ada yang mencoba "menyempurnakan" hal ini di tengah jalan padahal belum waktunya:

* **Tidak ada disambiguation otomatis untuk nama dosen yang mirip/sama** (dua "Ahmad Fauzi" berbeda orang) — kalau kejadian, masuk `unmatched_authors` untuk direview manual, bukan ditebak sistem.  
* **Tidak ada normalisasi nama venue/jurnal** ke bentuk standar (menyatukan `"IEEE Trans. PAMI"` dengan `"IEEE Transactions on Pattern Analysis and Machine Intelligence"`) — disimpan apa adanya dari sumber.  
* **Tidak ada scoring kualitas/relevansi publikasi** — semua publikasi yang lolos dedup masuk apa adanya dengan status `NEEDS_REVIEW`; keputusan relevan/tidak relevan ada di reviewer manusia lewat review layer tim website.  
* **Tidak ada auto-tagging dosen berbasis hasil crawling publikasi** — assignment tag (§5.5) tetap manual berdasar data CSV departemen, bukan disimpulkan otomatis dari topik publikasi yang ter-crawl.  
* **Tidak ada validasi/verifikasi domain email institusi secara aktif** — cukup validasi format (§3.4).

---

## **9\. Checklist Sebelum Merge PR Normalizer Baru**

Dipakai Lead saat review PR fetcher/normalizer baru dari Staff — semua poin harus centang sebelum merge ke `main`:

* \[ \] Fungsi normalizer pure function — tidak ada I/O (file/DB) di dalamnya  
* \[ \] Semua field kosong diisi `None`, bukan `""`/`0`/`"-"`/`"N/A"`  
* \[ \] `doi` melalui proses normalisasi lengkap sesuai §2.2 (lowercase, strip prefix, validasi awalan `10.`)  
* \[ \] `publication_type` dipetakan ke salah satu dari 5 enum tetap, tidak ada nilai bebas lolos  
* \[ \] `source`, `external_ids`, `verified_status` selalu terisi sesuai §2.8, `verified_status` selalu `NEEDS_REVIEW`  
* \[ \] Ada minimal 3 unit test (data lengkap, data field hilang, data format aneh) di `tests/test_normalize.py`  
* \[ \] Baris yang direject/diskip tercatat di log (§7), tidak silang begitu saja  
* \[ \] Kalau menyentuh matching/dedup: perubahan logic didiskusikan dulu dengan Lead sebelum PR (dedup adalah shared logic, bukan milik satu sumber)

---

