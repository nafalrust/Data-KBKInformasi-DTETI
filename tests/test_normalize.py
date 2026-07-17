from cleaners.normalize import (
    normalize_doi,
    normalize_openalex_metrics,
    normalize_openalex_publication,
)
from models.schemas import PublicationSource, PublicationType


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
