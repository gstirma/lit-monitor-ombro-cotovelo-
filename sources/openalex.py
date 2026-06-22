"""Fonte OpenAlex via API REST (https://api.openalex.org/works).

Filtra from_publication_date e busca os termos de ombro/cotovelo. Sem chave;
inclui mailto para o 'polite pool'. Reconstrói o abstract a partir do
abstract_inverted_index. Serve para varrer o que escapa de PubMed/SciELO.
"""
from __future__ import annotations

from datetime import date

from article import Article
from . import _http

WORKS = "https://api.openalex.org/works"


def _invert_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def _to_article(work: dict) -> Article | None:
    title = work.get("title") or work.get("display_name") or ""
    if not title:
        return None

    authors = [
        a.get("author", {}).get("display_name", "")
        for a in work.get("authorships", [])
        if a.get("author", {}).get("display_name")
    ]

    src = (work.get("primary_location") or {}).get("source") or {}
    journal = src.get("display_name", "") or ""

    doi = work.get("doi")
    if doi:
        doi = doi.replace("https://doi.org/", "")
    url = (work.get("primary_location") or {}).get("landing_page_url") or \
        (f"https://doi.org/{doi}" if doi else work.get("id", ""))

    return Article(
        title=title,
        authors=authors,
        journal=journal,
        pub_date=work.get("publication_date", "") or "",
        abstract=_invert_abstract(work.get("abstract_inverted_index")),
        doi=doi,
        url=url,
        source="OpenAlex",
    )


def _search_term(term: str, since: date, mailto: str, max_pages: int) -> list[Article]:
    out: list[Article] = []
    cursor = "*"
    params_base = {
        "filter": f"from_publication_date:{since.isoformat()},"
                  f"title_and_abstract.search:{term}",
        "per-page": 200,
        "sort": "publication_date:desc",
    }
    if mailto:
        params_base["mailto"] = mailto

    for _ in range(max_pages):
        params = dict(params_base, cursor=cursor)
        try:
            r = _http.get(WORKS, params=params)
        except Exception as exc:  # noqa: BLE001
            print(f"[OpenAlex] termo='{term}': erro de rede ({exc})")
            break
        data = r.json()
        for work in data.get("results", []):
            a = _to_article(work)
            if a:
                out.append(a)
        cursor = (data.get("meta") or {}).get("next_cursor")
        if not cursor:
            break
    return out


def fetch(since_date: date, cfg: dict) -> list[Article]:
    oa = cfg.get("openalex", {})
    mailto = oa.get("mailto", "") or cfg.get("email", {}).get("to", "")
    max_pages = oa.get("max_pages", 5)

    # Por padrão usa âncoras amplas; cada termo vira uma busca independente.
    terms = oa.get("search_terms") or ["shoulder", "elbow"]

    by_key: dict[str, Article] = {}
    for term in terms:
        for a in _search_term(term, since_date, mailto, max_pages):
            by_key.setdefault(a.dedup_key, a)  # dedup local entre termos
    return list(by_key.values())
