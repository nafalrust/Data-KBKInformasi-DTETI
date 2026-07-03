# ERD — KBK TI Data Layer (Staging Database)

> Sumber: `sql/schema_staging.sql`
> Cakupan: hanya entitas yang jadi tanggung jawab **Tim Data** (dosen, publikasi, tag/cluster riset, metrik akademik).
> **Tidak termasuk** entitas milik penuh Tim Website yang tidak disentuh crawling/cleaning: `Project`, `News`, `Event`, `StaticPage` (lihat PRD Website §11.7–11.10) — entitas-entitas itu diisi manual oleh admin, bukan hasil pipeline data, jadi sengaja tidak digambar di sini.
> Render: paste ke https://mermaid.live, atau ekstensi Mermaid di VS Code / editor mana pun.

```mermaid
erDiagram
    LECTURERS ||--o{ LECTURER_RESEARCH_TAGS : "punya"
    RESEARCH_TAGS ||--o{ LECTURER_RESEARCH_TAGS : "dipakai oleh"
    RESEARCH_CLUSTERS ||--o{ RESEARCH_TAGS : "menaungi"

    LECTURERS ||--o{ LECTURER_PUBLICATIONS : "menulis"
    PUBLICATIONS ||--o{ LECTURER_PUBLICATIONS : "ditulis oleh"

    LECTURERS ||--o| LECTURER_METRICS : "punya metrik"

    LECTURERS {
        uuid id PK
        text full_name
        text academic_title
        text slug UK "nullable di staging"
        text nip_or_staff_id
        text email
        text sinta_id "WAJIB"
        text scopus_author_id "Post-MVP, NULL di Horizon A"
        text google_scholar_url
        text google_scholar_id
        text orcid_id
        text openalex_author_id "field kerja tim Data"
        text semantic_scholar_id "field kerja tim Data"
        text supervision_status "OPEN/LIMITED/CLOSED/CONTACT_FIRST"
        boolean is_active
        text source_csv_row_ref "audit jejak cleaning"
        timestamptz created_at
        timestamptz updated_at
    }

    RESEARCH_CLUSTERS {
        uuid id PK
        text name
        text slug UK
        text description
        integer sort_order
    }

    RESEARCH_TAGS {
        uuid id PK
        text name
        text slug UK
        uuid cluster_id FK
        text description
        boolean is_active
    }

    LECTURER_RESEARCH_TAGS {
        uuid lecturer_id PK_FK
        uuid tag_id PK_FK
        boolean is_primary
    }

    PUBLICATIONS {
        uuid id PK
        text title
        text slug "diisi saat handoff"
        integer year
        date publication_date
        text authors_text "nama mentah, belum resolve ke lecturer_id"
        text venue
        text publication_type "JOURNAL/CONFERENCE/BOOK_CHAPTER/PREPRINT/OTHER"
        text doi UK "dinormalisasi, kunci dedup utama"
        text url
        text abstract
        integer citation_count
        text source "OPENALEX/SEMANTIC_SCHOLAR/CROSSREF/GOOGLE_SCHOLAR/SINTA/SCOPUS/CSV_IMPORT"
        jsonb external_ids "id lintas platform"
        text verified_status "selalu NEEDS_REVIEW dari pipeline"
        text fetch_batch_id "jejak debug batch crawl"
        timestamptz created_at
        timestamptz updated_at
    }

    LECTURER_PUBLICATIONS {
        uuid lecturer_id PK_FK
        uuid publication_id PK_FK
        integer author_order
    }

    LECTURER_METRICS {
        uuid lecturer_id PK_FK
        integer h_index
        integer total_citations
        numeric sinta_score "Post-MVP, NULL di Horizon A"
        text source "OPENALEX/SINTA"
        timestamptz fetched_at
    }
```

## Catatan Baca Diagram

- `LECTURERS ||--o{ LECTURER_PUBLICATIONS` dan `PUBLICATIONS ||--o{ LECTURER_PUBLICATIONS`: bersama-sama ini merepresentasikan **many-to-many** dosen ↔ publikasi lewat tabel penghubung `LECTURER_PUBLICATIONS` — satu dosen bisa punya banyak publikasi, satu publikasi bisa multi-author dosen internal KBK.
- Pola yang sama berlaku untuk `LECTURERS` ↔ `RESEARCH_TAGS` lewat `LECTURER_RESEARCH_TAGS`.
- `RESEARCH_CLUSTERS ||--o{ RESEARCH_TAGS`: satu cluster menaungi banyak tag, tapi satu tag hanya boleh masuk satu cluster (relasi belongs-to biasa, bukan many-to-many).
- `LECTURERS ||--o| LECTURER_METRICS`: relasi **1-to-1** (opsional) — satu dosen paling banyak satu baris metrik agregat, yang di-*upsert* ulang tiap sync.
- Field bertanda **"Post-MVP"** sengaja tetap ada di skema staging sejak awal (kolom boleh `NULL` dulu) supaya tidak perlu migrasi ulang saat SINTA/Scopus mulai dikerjakan di Horizon B.
- Field bertanda **"field kerja tim Data"** adalah kolom yang tidak ada di skema PRD Website §11 — diusulkan ikut masuk production (lihat PRD §6.5), tapi minimal wajib ada di staging untuk kebutuhan resolusi ID dan debugging.
