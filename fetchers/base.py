"""Shared HTTP client helpers: rate limiting, retry, raw response caching."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential


class RateLimiter:
    """Simple rate limiter: sleeps to keep to N requests/second."""

    def __init__(self, requests_per_second: float):
        self._min_interval = 1.0 / requests_per_second
        self._last_call: float = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        remaining = self._min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_call = time.monotonic()


def cache_path(source: str, key: str, cache_dir: str = "raw_cache") -> Path:
    safe_key = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return Path(cache_dir) / source / f"{safe_key}.json"


def read_cache(source: str, key: str, cache_dir: str = "raw_cache") -> Optional[Any]:
    path = cache_path(source, key, cache_dir)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def write_cache(source: str, key: str, data: Any, cache_dir: str = "raw_cache") -> None:
    path = cache_path(source, key, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class HttpClient:
    """Thin wrapper around httpx with retry + rate limiting for a single source.

    max_attempts dikonfigurasi per-instance (bukan hardcode) supaya sumber
    yang API-nya kurang stabil / rate-limit ketat (mis. Semantic Scholar
    tanpa API key) bisa diset gagal cepat per-request, tanpa memaksa OpenAlex
    (yang jauh lebih stabil) ikut kurang toleran terhadap error transient.
    """

    def __init__(
        self,
        base_url: str,
        requests_per_second: float,
        timeout: float = 30.0,
        headers: Optional[dict] = None,
        max_attempts: int = 4,
    ):
        self._client = httpx.Client(base_url=base_url, timeout=timeout, headers=headers or {})
        self._limiter = RateLimiter(requests_per_second)
        self._max_attempts = max_attempts

    def get(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        retrying = Retrying(
            reraise=True,
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=20),
            retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        )
        return retrying(self._get_once, path, params)

    def _get_once(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        self._limiter.wait()
        response = self._client.get(path, params=params)
        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()
        return response

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
