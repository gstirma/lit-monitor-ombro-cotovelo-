"""Modelo de dados comum a todas as fontes + utilidades de normalização/classificação."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Article:
    """Apenas a 'chamada' do artigo — metadados abertos, nunca texto integral."""

    title: str
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    pub_date: str = ""          # "YYYY-MM-DD" | "YYYY-MM" | "YYYY"
    abstract: str = ""
    doi: str | None = None
    url: str = ""
    source: str = ""            # "PubMed" | "SciELO" | "OpenAlex" | "Google Scholar"
    # Campos preenchidos no processamento:
    subtema: str = "Geral"      # "Ombro" | "Cotovelo" | "Ombro e Cotovelo" | "Geral"
    relevance: float = 0.0      # 0..1 (preenchido pelo enriquecimento opcional via IA)
    summary_pt: str = ""        # resumo de 1-2 frases em PT (opcional, via IA)
    added: str = ""             # data (YYYY-MM-DD) em que o artigo foi capturado

    @property
    def dedup_key(self) -> str:
        """Chave de deduplicação: DOI normalizado quando houver, senão o título."""
        if self.doi:
            return "doi:" + normalize_doi(self.doi)
        return "title:" + normalize_title(self.title)


# --------------------------------------------------------------------------- #
# Normalização
# --------------------------------------------------------------------------- #
def normalize_doi(doi: str) -> str:
    d = (doi or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = d.replace("doi:", "").strip()
    return d


def normalize_title(title: str) -> str:
    t = unicodedata.normalize("NFKD", title or "")
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


# --------------------------------------------------------------------------- #
# Datas
# --------------------------------------------------------------------------- #
def parse_date(s: str) -> date | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def within_window(pub_date: str, since: date) -> bool:
    """Filtro-rede de segurança no cliente. Permissivo quando a data é imprecisa,
    pois cada fonte já restringe a janela no servidor."""
    d = parse_date(pub_date)
    if d is None:
        return True
    return d >= since


# --------------------------------------------------------------------------- #
# Classificação por subtema (baseada em palavras-chave; a IA pode refinar)
# --------------------------------------------------------------------------- #
SHOULDER_KEYWORDS = [
    "shoulder", "rotator cuff", "glenohumeral", "glenoid", "acromioclavicular",
    "subacromial", "biceps", "slap lesion", "supraspinatus", "infraspinatus",
    "subscapularis", "scapula", "ombro", "manguito rotador",
]
ELBOW_KEYWORDS = [
    "elbow", "distal humerus", "olecranon", "epicondylitis", "epicondyle",
    "ulnar collateral ligament", "radial head", "coronoid", "tennis elbow",
    "golfer's elbow", "cotovelo", "epicondilite",
]


def classify_subtema(article: "Article") -> str:
    text = f"{article.title} {article.abstract}".lower()
    has_shoulder = any(k in text for k in SHOULDER_KEYWORDS)
    has_elbow = any(k in text for k in ELBOW_KEYWORDS)
    if has_shoulder and has_elbow:
        return "Ombro e Cotovelo"
    if has_shoulder:
        return "Ombro"
    if has_elbow:
        return "Cotovelo"
    return "Geral"
