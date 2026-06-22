"""Sessão HTTP compartilhada com retry simples e timeout padrão."""
from __future__ import annotations

import time

import requests

_session = requests.Session()
_session.headers.update(
    {"User-Agent": "lit-monitor-ombro-cotovelo/1.0 (+https://github.com/)"}
)

DEFAULT_TIMEOUT = 30


def get(url: str, params: dict | None = None, *, timeout: int = DEFAULT_TIMEOUT,
        retries: int = 3, backoff: float = 1.5):
    last_exc = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r
        except (requests.RequestException, requests.HTTPError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise last_exc  # type: ignore[misc]
