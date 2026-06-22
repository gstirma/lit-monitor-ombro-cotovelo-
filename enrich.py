"""Enriquecimento opcional via API da Anthropic.

Para cada artigo, a partir SOMENTE do abstract:
  - estima relevância (0..1) para ortopedia de ombro/cotovelo;
  - classifica o subtema;
  - gera um resumo de 1-2 frases em português.
Nunca inventa dados além do que está no abstract. Se a chave/SDK não estiverem
disponíveis, os artigos seguem sem alteração (degrada com elegância).
"""
from __future__ import annotations

import json
import os
import re

from article import Article

_SYSTEM = (
    "Você é assistente de um ortopedista especialista em ombro e cotovelo. "
    "Resuma e classifique artigos SOMENTE a partir do abstract fornecido. "
    "NUNCA invente dados, números ou conclusões que não estejam no texto. "
    "Responda exclusivamente em JSON válido."
)

_VALID_SUBTEMAS = {"Ombro", "Cotovelo", "Ombro e Cotovelo", "Geral"}


def _prompt(a: Article) -> str:
    return (
        "Analise o artigo abaixo e devolva um JSON com as chaves exatas:\n"
        '  "relevancia": número de 0 a 1 (quão relevante é para a prática de '
        "ombro/cotovelo em ortopedia),\n"
        '  "subtema": um de "Ombro", "Cotovelo", "Ombro e Cotovelo", "Geral",\n'
        '  "resumo_pt": 1 a 2 frases em português, baseadas apenas no abstract.\n\n'
        f"TÍTULO: {a.title}\n"
        f"PERIÓDICO: {a.journal}\n"
        f"ABSTRACT: {a.abstract[:4000] or '(sem abstract disponível)'}\n"
    )


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def enrich(articles: list[Article], cfg: dict) -> list[Article]:
    an = cfg.get("anthropic", {})
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not an.get("enabled") or not key:
        if an.get("enabled") and not key:
            print("[enrich] ANTHROPIC_API_KEY ausente — pulando enriquecimento por IA.")
        return articles

    try:
        import anthropic  # import tardio: dependência opcional
    except ImportError:
        print("[enrich] pacote 'anthropic' não instalado — pulando enriquecimento.")
        return articles

    client = anthropic.Anthropic(api_key=key)
    model = an.get("model", "claude-haiku-4-5-20251001")
    max_items = an.get("max_items", 80)

    for a in articles[:max_items]:
        if not a.abstract:
            continue
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=400,
                system=_SYSTEM,
                messages=[{"role": "user", "content": _prompt(a)}],
            )
            text = "".join(
                block.text for block in msg.content if getattr(block, "type", "") == "text"
            )
            data = _parse_json(text)
            if "relevancia" in data:
                try:
                    a.relevance = max(0.0, min(1.0, float(data["relevancia"])))
                except (TypeError, ValueError):
                    pass
            sub = data.get("subtema")
            if sub in _VALID_SUBTEMAS:
                a.subtema = sub
            if data.get("resumo_pt"):
                a.summary_pt = str(data["resumo_pt"]).strip()
        except Exception as exc:  # noqa: BLE001
            print(f"[enrich] falha ao enriquecer '{a.title[:60]}...': {exc}")
    return articles
