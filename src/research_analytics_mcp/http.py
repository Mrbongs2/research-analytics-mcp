"""Small HTTP helper shared by every connector: one client, retries on 429/5xx, clear errors."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from . import __version__

USER_AGENT = os.getenv(
    "RA_MCP_USER_AGENT",
    f"research-analytics-mcp/{__version__} (+https://github.com/topics/mcp-server)",
)
TIMEOUT = float(os.getenv("RA_MCP_TIMEOUT", "30"))

logging.getLogger("httpx").setLevel(logging.WARNING)  # keep stderr quiet in MCP clients

_client: httpx.Client | None = None


class UpstreamError(RuntimeError):
    """Raised when an upstream API keeps failing or returns an error status."""


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
    return _client


def request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json: Any = None,
    files: Any = None,
    retries: int = 2,
    backoff: float = 2.0,
) -> httpx.Response:
    params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = client().request(method, url, params=params, headers=headers, json=json, files=files)
        except httpx.HTTPError as e:  # network problem
            last = e
        else:
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = float(r.headers.get("Retry-After", backoff * (attempt + 1)))
                time.sleep(min(wait, 20))
                continue
            if r.status_code >= 400:
                raise UpstreamError(f"{method} {url} -> HTTP {r.status_code}: {r.text[:300]}")
            return r
        time.sleep(backoff * (attempt + 1))
    raise UpstreamError(f"{method} {url} failed after {retries + 1} attempts: {last}")


def get_json(url: str, **kw: Any) -> Any:
    return request("GET", url, **kw).json()


def get_text(url: str, **kw: Any) -> str:
    return request("GET", url, **kw).text
