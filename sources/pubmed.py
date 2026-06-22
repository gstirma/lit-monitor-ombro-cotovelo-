"""Fonte PubMed via E-utilities (esearch + efetch).

Restringe pela janela recente (datetype=pdat & reldate) e, opcionalmente, à lista
de periódicos no campo [Journal]. Captura apenas metadados (a 'chamada').
"""
from __future__ import annotations

import os
import time
from datetime import date
from xml.etree import ElementTree as ET

from article import Article
from . import _http

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _eutils_common(cfg: dict) -> dict:
    email = cfg.get("email", {}).get("to") or cfg.get("openalex", {}).get("mailto", "")
    common = {"tool": "lit-monitor-ombro-cotovelo", "email": email}
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        common["api_key"] = api_key
    return common


def _build_query(cfg: dict) -> str:
    search = cfg.get("search", {})
    parts: list[str] = []
    for term in search.get("shoulder", []) + search.get("elbow", []):
        parts.append(f'"{term}"[Title/Abstract]')
    for mesh in search.get("mesh", []):
        parts.append(mesh)  # já vem com [Mesh]
    term_q = "(" + " OR ".join(parts) + ")"

    if cfg.get("pubmed", {}).get("restrict_to_journals"):
        journals = [j["name"] for j in cfg.get("journals", []) if j.get("name")]
        if journals:
            jq = "(" + " OR ".join(f'"{j}"[Journal]' for j in journals) + ")"
            return f"{term_q} AND {jq}"
    return term_q


def _text(el) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def _parse_date(article_el) -> str:
    # Preferir ArticleDate (data eletrônica), senão PubDate.
    for ad in article_el.findall(".//ArticleDate"):
        y = ad.findtext("Year")
        m = ad.findtext("Month")
        d = ad.findtext("Day")
        if y:
            return f"{int(y):04d}-{int(m or 1):02d}-{int(d or 1):02d}"
    pd = article_el.find(".//Journal/JournalIssue/PubDate")
    if pd is not None:
        y = pd.findtext("Year")
        m = pd.findtext("Month")
        d = pd.findtext("Day")
        if y:
            mm = 1
            if m:
                mm = _MONTHS.get(m[:3].lower(), 0) or (int(m) if m.isdigit() else 1)
            dd = int(d) if d and d.isdigit() else 1
            return f"{int(y):04d}-{mm:02d}-{dd:02d}"
    return ""


def _parse_article(pa) -> Article | None:
    art = pa.find(".//Article")
    if art is None:
        return None

    title = _text(art.find("ArticleTitle"))

    # Abstract (pode ter seções rotuladas)
    chunks = []
    for ab in art.findall(".//Abstract/AbstractText"):
        label = ab.get("Label")
        txt = _text(ab)
        chunks.append(f"{label}: {txt}" if label else txt)
    abstract = "\n".join(c for c in chunks if c).strip()

    authors = []
    for a in art.findall(".//AuthorList/Author"):
        last = a.findtext("LastName")
        fore = a.findtext("ForeName") or a.findtext("Initials")
        coll = a.findtext("CollectiveName")
        if last:
            authors.append(f"{fore} {last}".strip() if fore else last)
        elif coll:
            authors.append(coll)

    journal = _text(art.find(".//Journal/Title")) or _text(art.find(".//Journal/ISOAbbreviation"))

    doi = None
    pmid = pa.findtext(".//MedlineCitation/PMID") or pa.findtext(".//PMID")
    for aid in pa.findall(".//ArticleIdList/ArticleId"):
        if aid.get("IdType") == "doi":
            doi = _text(aid)
    if not doi:
        for el in art.findall(".//ELocationID"):
            if el.get("EIdType") == "doi":
                doi = _text(el)

    url = f"https://doi.org/{doi}" if doi else (
        f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")

    if not title:
        return None
    return Article(
        title=title, authors=authors, journal=journal,
        pub_date=_parse_date(pa), abstract=abstract, doi=doi, url=url,
        source="PubMed",
    )


def fetch(since_date: date, cfg: dict) -> list[Article]:
    common = _eutils_common(cfg)
    window = cfg.get("window_days", 3)
    retmax = cfg.get("pubmed", {}).get("retmax", 200)

    params = {
        "db": "pubmed", "term": _build_query(cfg), "retmode": "json",
        "retmax": retmax, "datetype": "pdat", "reldate": window, **common,
    }
    r = _http.get(ESEARCH, params=params)
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    articles: list[Article] = []
    sleep = 0.12 if common.get("api_key") else 0.34  # respeita o rate limit do NCBI
    for i in range(0, len(ids), 200):
        batch = ids[i:i + 200]
        fr = _http.get(EFETCH, params={
            "db": "pubmed", "id": ",".join(batch),
            "rettype": "abstract", "retmode": "xml", **common,
        })
        root = ET.fromstring(fr.content)
        for pa in root.findall(".//PubmedArticle"):
            a = _parse_article(pa)
            if a:
                articles.append(a)
        time.sleep(sleep)
    return articles
