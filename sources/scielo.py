"""Fonte SciELO via OAI-PMH (ListRecords, Dublin Core).

Usa from/until para a janela recente e set=<ISSN> para filtrar cada periódico.
Importante para cobertura nacional (ex.: Revista Brasileira de Ortopedia).
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from xml.etree import ElementTree as ET

from article import Article, classify_subtema
from . import _http

DEFAULT_ENDPOINT = "https://oai.scielo.org/request"

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

_DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)


def _dc_list(rec, tag: str) -> list[str]:
    return [(_e.text or "").strip()
            for _e in rec.findall(f".//dc:{tag}", NS) if (_e.text or "").strip()]


def _first(rec, tag: str) -> str:
    vals = _dc_list(rec, tag)
    return vals[0] if vals else ""


def _extract_doi_url(identifiers: list[str]) -> tuple[str | None, str]:
    doi = None
    url = ""
    for ident in identifiers:
        if not url and ident.startswith("http"):
            url = ident
        m = _DOI_RE.search(ident)
        if m and not doi:
            doi = m.group(0).rstrip(".")
    return doi, url


def _parse_record(rec) -> Article | None:
    # Cabeçalho deletado?
    header = rec.find("oai:header", NS)
    if header is not None and header.get("status") == "deleted":
        return None
    md = rec.find(".//oai_dc:dc", NS)
    if md is None:
        return None

    title = _first(md, "title")
    if not title:
        return None
    authors = _dc_list(md, "creator")
    journal = _first(md, "source") or _first(md, "publisher")
    pub_date = _first(md, "date")[:10]
    abstract = " ".join(_dc_list(md, "description"))
    doi, url = _extract_doi_url(_dc_list(md, "identifier"))
    if doi and not url:
        url = f"https://doi.org/{doi}"

    a = Article(
        title=title, authors=authors, journal=journal, pub_date=pub_date,
        abstract=abstract, doi=doi, url=url, source="SciELO",
    )
    a.subtema = classify_subtema(a)
    return a


def _list_records_for_set(endpoint: str, set_spec: str, dfrom: str, dto: str) -> list[Article]:
    articles: list[Article] = []
    params = {
        "verb": "ListRecords", "metadataPrefix": "oai_dc",
        "from": dfrom, "until": dto, "set": set_spec,
    }
    for _ in range(50):  # trava de segurança contra paginação infinita
        try:
            r = _http.get(endpoint, params=params)
        except Exception as exc:  # noqa: BLE001
            print(f"[SciELO] set={set_spec}: erro de rede ({exc})")
            break
        root = ET.fromstring(r.content)

        err = root.find("oai:error", NS)
        if err is not None:
            code = err.get("code")
            if code != "noRecordsMatch":
                print(f"[SciELO] set={set_spec}: {code} — {(err.text or '').strip()}")
            break

        for rec in root.findall(".//oai:ListRecords/oai:record", NS):
            a = _parse_record(rec)
            if a:
                articles.append(a)

        token_el = root.find(".//oai:resumptionToken", NS)
        token = (token_el.text or "").strip() if token_el is not None else ""
        if not token:
            break
        # Com resumptionToken, os demais parâmetros não são reenviados.
        params = {"verb": "ListRecords", "resumptionToken": token}
    return articles


def fetch(since_date: date, cfg: dict) -> list[Article]:
    sc = cfg.get("scielo", {})
    endpoint = sc.get("endpoint", DEFAULT_ENDPOINT)
    dfrom = since_date.isoformat()
    dto = (date.today() + timedelta(days=1)).isoformat()

    sets: list[str] = []
    for j in cfg.get("journals", []):
        spec = j.get("scielo_set") or j.get("scielo_issn")
        if spec:
            sets.append(str(spec))
    sets += [str(s) for s in sc.get("extra_sets", [])]

    out: list[Article] = []
    for set_spec in dict.fromkeys(sets):  # remove duplicatas preservando ordem
        out.extend(_list_records_for_set(endpoint, set_spec, dfrom, dto))
    return out
