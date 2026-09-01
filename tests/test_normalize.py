from cleaners.normalize import (
    extract_google_scholar_author_id,
    extract_semantic_scholar_author_id,
    normalize_doi,
    normalize_google_scholar_metrics,
    normalize_google_scholar_publication,
    normalize_openalex_metrics,
    normalize_openalex_publication,
    normalize_semantic_scholar_metrics,
    normalize_semantic_scholar_publication,
)
from models.schemas import MetricsSource, PublicationSource, PublicationType


# ---- normalize_doi ----

def test_normalize_doi_strips_url_prefix_and_lowercases():
    assert normalize_doi("https://doi.org/10.1109/TPAMI.2023.1234567") == "10.1109/tpami.2023.1234567"


def test_normalize_doi_none_when_missing():
    assert normalize_doi(None) == None
    assert normalize_doi("") == None


def test_normalize_doi_none_when_not_starting_with_10():
    assert normalize_doi("some-garbage-not-a-doi") is None


# ---- normalize_openalex_publication ----

def test_normalize_openalex_publication_full_data():
    raw = {
        "id": "https://openalex.org/W123",
        "title": "A Study of Something",
        "publication_year": 2022,
        "publication_date": "2022-05-01",
        "doi": "https://doi.org/10.1109/abc.2022.123",
        "type": "journal-article",
        "cited_by_count": 5,
        "primary_location": {
            "landing_page_url": "https://example.com/paper",
            "source": {"display_name": "IEEE Transactions"},
        },
        "authorships": [
            {"author": {"display_name": "Budi Santoso"}},
            {"author": {"display_name": "Ani Wijaya"}},
        ],
        "abstract_inverted_index": {"Hello": [0], "world": [1]},
    }
    pub = normalize_openalex_publication(raw, fetch_batch_id="batch1")
    assert pub is not None
    assert pub.title == "A Study of Something"
    assert pub.doi == "10.1109/abc.2022.123"
    assert pub.year == 2022
    assert pub.publication_type == PublicationType.JOURNAL
    assert pub.authors_text == "Budi Santoso; Ani Wijaya"
    assert pub.venue == "IEEE Transactions"
    assert pub.citation_count == 5
    assert pub.abstract == "Hello world"
    assert pub.source == PublicationSource.OPENALEX
    assert pub.external_ids["openalex"] == "https://openalex.org/W123"
    assert pub.verified_status == "NEEDS_REVIEW"
    assert pub.fetch_batch_id == "batch1"


def test_normalize_openalex_publication_missing_fields_rejected_or_none():
    # No title at all -> reject (title is NOT NULL contract)
    raw_no_title = {
        "id": "https://openalex.org/W1",
        "title": None,
        "display_name": None,
        "authorships": [{"author": {"display_name": "Budi Santoso"}}],
    }
    assert normalize_openalex_publication(raw_no_title) is None

    # No authorships -> reject (authors_text is NOT NULL contract)
    raw_no_authors = {
        "id": "https://openalex.org/W2",
        "title": "Some Title",
        "authorships": [],
    }
    assert normalize_openalex_publication(raw_no_authors) is None

    # Missing optional fields -> None, not "" / 0 / "-"
    raw_minimal = {
        "id": "https://openalex.org/W3",
        "title": "Minimal Paper",
        "authorships": [{"author": {"display_name": "Budi Santoso"}}],
        "doi": None,
        "publication_year": None,
        "cited_by_count": None,
        "primary_location": {},
        "abstract_inverted_index": None,
    }
    pub = normalize_openalex_publication(raw_minimal)
    assert pub is not None
    assert pub.doi is None
    assert pub.year is None
    assert pub.citation_count is None
    assert pub.venue is None
    assert pub.abstract is None
    assert pub.publication_type == PublicationType.OTHER


def test_normalize_openalex_publication_weird_formats():
    # Year out of plausible range, malformed URL, unknown type -> defensive handling
    raw = {
        "id": "https://openalex.org/W4",
        "title": "  Weird <i>Formatting</i> Paper  ",
        "authorships": [{"author": {"display_name": "Someone"}}],
        "publication_year": 1850,  # too old -> rejected
        "type": "some-unknown-type",
        "primary_location": {"landing_page_url": "not-a-valid-url"},
        "doi": "DOI: 10.1000/ABC",
    }
    pub = normalize_openalex_publication(raw)
    assert pub is not None
    assert pub.title == "Weird Formatting Paper"
    assert pub.year is None
    assert pub.publication_type == PublicationType.OTHER
    assert pub.url is None
    assert pub.doi == "10.1000/abc"


# ---- normalize_openalex_metrics ----

def test_normalize_openalex_metrics_full():
    raw_author = {
        "cited_by_count": 100,
        "summary_stats": {"h_index": 12},
    }
    metrics = normalize_openalex_metrics(raw_author)
    assert metrics.h_index == 12
    assert metrics.total_citations == 100
    assert metrics.sinta_score is None


def test_normalize_openalex_metrics_missing_fields():
    metrics = normalize_openalex_metrics({"summary_stats": {}})
    assert metrics.h_index is None
    assert metrics.total_citations is None


def test_normalize_openalex_metrics_none_author():
    assert normalize_openalex_metrics(None) is None
    assert normalize_openalex_metrics({}) is None


# ---- normalize_google_scholar_publication ----

def test_normalize_google_scholar_publication_full_data():
    raw = {
        "author_pub_id": "AbCdEfGh:xyz123",
        "num_citations": 7,
        "pub_url": "https://example.com/paper-gs",
        "bib": {
            "title": "A GScholar Study of Something",
            "author": "Budi Santoso and Ani Wijaya",
            "pub_year": "2021",
            "venue": "Prosiding Seminar Nasional",
            "journal": "Jurnal Ilmu Komputer",
            "pub_type": "article",
            "abstract": "Ringkasan singkat penelitian ini.",
        },
    }
    pub = normalize_google_scholar_publication(raw, fetch_batch_id="batch1")
    assert pub is not None
    assert pub.title == "A GScholar Study of Something"
    assert pub.authors_text == "Budi Santoso; Ani Wijaya"
    assert pub.year == 2021
    assert pub.venue == "Prosiding Seminar Nasional"
    assert pub.publication_type == PublicationType.JOURNAL
    assert pub.citation_count == 7
    assert pub.abstract == "Ringkasan singkat penelitian ini."
    assert pub.doi is None
    assert pub.source == PublicationSource.GOOGLE_SCHOLAR
    assert pub.external_ids["google_scholar"] == "AbCdEfGh:xyz123"
    assert pub.fetch_batch_id == "batch1"


def test_normalize_google_scholar_publication_missing_fields_rejected_or_none():
    # No title -> reject
    assert normalize_google_scholar_publication({"bib": {"author": "Someone"}}) is None

    # No author -> reject
    assert normalize_google_scholar_publication({"bib": {"title": "Some Title"}}) is None

    # Minimal valid data -> optional fields None, not "" / 0
    raw_minimal = {
        "bib": {"title": "Minimal Paper", "author": "Someone"},
    }
    pub = normalize_google_scholar_publication(raw_minimal)
    assert pub is not None
    assert pub.doi is None
    assert pub.year is None
    assert pub.citation_count is None
    assert pub.venue is None
    assert pub.abstract is None
    assert pub.publication_type == PublicationType.OTHER


def test_normalize_google_scholar_publication_single_author_no_and_separator():
    raw = {"bib": {"title": "Solo Paper", "author": "Budi Santoso"}}
    pub = normalize_google_scholar_publication(raw)
    assert pub is not None
    assert pub.authors_text == "Budi Santoso"


# ---- normalize_google_scholar_metrics ----

def test_normalize_google_scholar_metrics_full():
    raw_author = {"hindex": 9, "citedby": 250}
    metrics = normalize_google_scholar_metrics(raw_author)
    assert metrics is not None
    assert metrics.h_index == 9
    assert metrics.total_citations == 250
    assert metrics.sinta_score is None
    assert metrics.source == MetricsSource.GOOGLE_SCHOLAR


def test_normalize_google_scholar_metrics_none_author():
    assert normalize_google_scholar_metrics(None) is None
    assert normalize_google_scholar_metrics({}) is None


# ---- extract_google_scholar_author_id ----

def test_extract_google_scholar_author_id():
    assert extract_google_scholar_author_id({"scholar_id": "AbCdEfGh"}) == "AbCdEfGh"
    assert extract_google_scholar_author_id(None) is None
    assert extract_google_scholar_author_id({}) is None


# ---- normalize_semantic_scholar_publication ----

def test_normalize_semantic_scholar_publication_full_data():
    raw = {
        "paperId": "649def34f8be52c8b66281af98ae884c09aef38",
        "title": "A Semantic Scholar Study of Something",
        "year": 2023,
        "publicationDate": "2023-04-01",
        "authors": [{"name": "Budi Santoso"}, {"name": "Ani Wijaya"}],
        "venue": "IEEE Access",
        "publicationTypes": ["JournalArticle"],
        "externalIds": {"DOI": "10.1109/ACCESS.2023.123456"},
        "abstract": "Ringkasan penelitian ini.",
        "citationCount": 4,
    }
    pub = normalize_semantic_scholar_publication(raw, fetch_batch_id="batch1")
    assert pub is not None
    assert pub.title == "A Semantic Scholar Study of Something"
    assert pub.authors_text == "Budi Santoso; Ani Wijaya"
    assert pub.year == 2023
    assert pub.publication_date.isoformat() == "2023-04-01"
    assert pub.venue == "IEEE Access"
    assert pub.publication_type == PublicationType.JOURNAL
    assert pub.doi == "10.1109/access.2023.123456"
    assert pub.citation_count == 4
    assert pub.abstract == "Ringkasan penelitian ini."
    assert pub.source == PublicationSource.SEMANTIC_SCHOLAR
    assert pub.external_ids["semantic_scholar"] == "649def34f8be52c8b66281af98ae884c09aef38"
    assert pub.external_ids["doi"] == "10.1109/access.2023.123456"
    assert pub.fetch_batch_id == "batch1"


def test_normalize_semantic_scholar_publication_missing_fields_rejected_or_none():
    # No title -> reject
    assert normalize_semantic_scholar_publication({"authors": [{"name": "Someone"}]}) is None

    # No authors -> reject
    assert normalize_semantic_scholar_publication({"title": "Some Title", "authors": []}) is None

    # Minimal valid data -> optional fields None, not "" / 0
    raw_minimal = {"title": "Minimal Paper", "authors": [{"name": "Someone"}]}
    pub = normalize_semantic_scholar_publication(raw_minimal)
    assert pub is not None
    assert pub.doi is None
    assert pub.year is None
    assert pub.citation_count is None
    assert pub.venue is None
    assert pub.abstract is None
    assert pub.publication_type == PublicationType.OTHER


def test_normalize_semantic_scholar_publication_unknown_type_maps_to_other():
    raw = {
        "title": "Some Paper",
        "authors": [{"name": "Someone"}],
        "publicationTypes": ["Editorial"],
    }
    pub = normalize_semantic_scholar_publication(raw)
    assert pub is not None
    assert pub.publication_type == PublicationType.OTHER


# ---- normalize_semantic_scholar_metrics ----

def test_normalize_semantic_scholar_metrics_full():
    raw_author = {"hIndex": 11, "citationCount": 300}
    metrics = normalize_semantic_scholar_metrics(raw_author)
    assert metrics is not None
    assert metrics.h_index == 11
    assert metrics.total_citations == 300
    assert metrics.sinta_score is None
    assert metrics.source == MetricsSource.SEMANTIC_SCHOLAR


def test_normalize_semantic_scholar_metrics_none_author():
    assert normalize_semantic_scholar_metrics(None) is None
    assert normalize_semantic_scholar_metrics({}) is None


# ---- extract_semantic_scholar_author_id ----

def test_extract_semantic_scholar_author_id():
    assert extract_semantic_scholar_author_id({"authorId": "1741101"}) == "1741101"
    assert extract_semantic_scholar_author_id(None) is None
    assert extract_semantic_scholar_author_id({}) is None
