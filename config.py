import os

from dotenv import load_dotenv

load_dotenv()

CRAWLER_EMAIL = os.getenv("CRAWLER_EMAIL", "nl.nightlogin@gmail.com")

OPENALEX_BASE_URL = "https://api.openalex.org"
OPENALEX_TIMEOUT = 30.0
OPENALEX_RATE_LIMIT_PER_SECOND = 9  # polite pool: 10 req/s, sisakan margin

SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"

CROSSREF_BASE_URL = "https://api.crossref.org"

DATABASE_URL = os.getenv("DATABASE_URL")

RAW_CACHE_DIR = "raw_cache"
EXPORTS_DIR = "exports"
