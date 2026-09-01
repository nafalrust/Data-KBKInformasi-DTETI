-- ============================================================
-- KBK TI — Staging Database Schema (v1 skeleton)
-- Dimiliki oleh: Tim Data
-- Tujuan: tempat kerja crawling/cleaning SEBELUM data masuk ke
--         database production milik tim website.
-- Sumber: DataSpecs-WebKBKProject.md §3.2
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE research_clusters (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    description TEXT,
    sort_order  INTEGER
);

CREATE TABLE lecturers (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name                 TEXT NOT NULL,
    academic_title            TEXT,
    slug                      TEXT UNIQUE,              -- diisi saat handoff, boleh NULL di staging
    nip_or_staff_id           TEXT NOT NULL,
    email                     TEXT,
    sinta_id                  TEXT NOT NULL UNIQUE,      -- Wajib sesuai PRD Website §11.1
    scopus_author_id          TEXT,                      -- Post-MVP, NULL dulu di Horizon A
    google_scholar_url        TEXT,
    google_scholar_id         TEXT,                      -- ekstrak dari URL, dipakai internal fetcher
    orcid_id                  TEXT,
    openalex_author_id        TEXT,                      -- ★ field kerja tim Data, lihat §11.1
    semantic_scholar_id       TEXT,                       -- ★ field kerja tim Data
    primary_research_cluster_id UUID REFERENCES research_clusters(id),  -- 1 dosen = 1 cluster utama (bukan many-to-many)
    supervision_status        TEXT,                       -- OPEN / LIMITED / CLOSED / CONTACT_FIRST
    is_active                 BOOLEAN DEFAULT TRUE,
    source_csv_row_ref        TEXT,                        -- jejak baris asal di CSV departemen, untuk audit cleaning
    created_at                TIMESTAMPTZ DEFAULT now(),
    updated_at                TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE research_tags (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    cluster_id  UUID REFERENCES research_clusters(id),
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE lecturer_research_tags (
    lecturer_id UUID REFERENCES lecturers(id) ON DELETE CASCADE,
    tag_id      UUID REFERENCES research_tags(id) ON DELETE CASCADE,
    is_primary  BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (lecturer_id, tag_id)
);

CREATE TABLE publications (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title            TEXT NOT NULL,
    slug             TEXT,                          -- diisi saat handoff
    year             INTEGER,
    publication_date DATE,
    authors_text     TEXT NOT NULL,                  -- nama author mentah, belum di-resolve ke lecturer_id
    venue            TEXT,
    publication_type TEXT,                            -- JOURNAL / CONFERENCE / BOOK_CHAPTER / PREPRINT / OTHER
    doi              TEXT,                              -- dinormalisasi (lowercase, tanpa prefix url) — lihat §6.3
    url              TEXT,
    abstract         TEXT,
    citation_count   INTEGER,
    source           TEXT NOT NULL,                       -- OPENALEX / SEMANTIC_SCHOLAR / CROSSREF / GOOGLE_SCHOLAR / SINTA / SCOPUS / CSV_IMPORT
    external_ids     JSONB,                                -- {"openalex": "...", "semantic_scholar": "...", "doi": "..."}
    verified_status  TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',  -- pipeline TIDAK PERNAH isi VERIFIED
    fetch_batch_id   TEXT,                                    -- ★ jejak batch crawl mana yang menghasilkan baris ini (debug)
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (doi)                                              -- constraint dedup utama; publikasi tanpa DOI ditangani di §6.3
);

CREATE TABLE lecturer_publications (
    lecturer_id    UUID REFERENCES lecturers(id) ON DELETE CASCADE,
    publication_id UUID REFERENCES publications(id) ON DELETE CASCADE,
    author_order   INTEGER,
    PRIMARY KEY (lecturer_id, publication_id)
);

CREATE TABLE lecturer_metrics (
    lecturer_id     UUID REFERENCES lecturers(id) ON DELETE CASCADE PRIMARY KEY,
    h_index         INTEGER,
    total_citations INTEGER,
    sinta_score     NUMERIC,                          -- Post-MVP, NULL dulu di Horizon A
    source          TEXT,                              -- OPENALEX / SINTA / GOOGLE_SCHOLAR / SEMANTIC_SCHOLAR
    fetched_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Tabel tambahan v2: kuota bimbingan, mahasiswa bimbingan aktif,
-- dan asisten dosen (teaching assistant).
-- Status saat ditambahkan: SKEMA SAJA, belum ada data (lihat HANDOFF.md).
-- ============================================================

CREATE TABLE lecturer_supervision_quota (
    lecturer_id             UUID REFERENCES lecturers(id) ON DELETE CASCADE PRIMARY KEY,
    max_quota               INTEGER,                          -- kapasitas maksimal bimbingan aktif dosen ini
    current_students_count  INTEGER DEFAULT 0,                -- jumlah bimbingan aktif saat ini (skripsi+tesis+disertasi)
    academic_period         TEXT,                              -- mis. '2026/2027 Ganjil' — kuota bisa berubah tiap periode
    source                  TEXT,                              -- SIA_MANUAL / DEPT_INPUT / dll, belum ditentukan sumbernya
    updated_at              TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE supervised_students (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lecturer_id       UUID REFERENCES lecturers(id) ON DELETE CASCADE,
    student_name      TEXT NOT NULL,
    student_id_number TEXT,                                    -- NIM, boleh NULL dulu kalau sumber data belum menyediakan
    program_level     TEXT,                                     -- S1 / S2 / S3
    thesis_title       TEXT,
    supervision_role  TEXT,                                     -- MAIN_SUPERVISOR / CO_SUPERVISOR
    status            TEXT,                                     -- ACTIVE / COMPLETED
    start_date        DATE,
    end_date          DATE,                                     -- NULL kalau masih aktif
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE teaching_assistants (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lecturer_id       UUID REFERENCES lecturers(id) ON DELETE CASCADE,  -- dosen pengampu mata kuliah
    student_name      TEXT NOT NULL,
    student_id_number TEXT,
    course_name       TEXT,
    academic_period   TEXT,                                     -- mis. '2026/2027 Ganjil'
    status            TEXT,                                     -- ACTIVE / COMPLETED
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now()
);

-- Index dasar yang dibutuhkan untuk cek dedup & pencarian cepat saat cleaning
CREATE INDEX idx_publications_doi ON publications (doi);
CREATE INDEX idx_publications_source ON publications (source);
CREATE INDEX idx_lecturers_sinta_id ON lecturers (sinta_id);
CREATE INDEX idx_supervised_students_lecturer_id ON supervised_students (lecturer_id);
CREATE INDEX idx_teaching_assistants_lecturer_id ON teaching_assistants (lecturer_id);
