"""Montagem do digest em HTML limpo, agrupado por subtema e por fonte."""
from __future__ import annotations

from datetime import date
from html import escape

from article import Article

SUBTEMA_ORDER = ["Ombro", "Cotovelo", "Ombro e Cotovelo", "Geral"]
SOURCE_ORDER = ["PubMed", "SciELO", "OpenAlex"]


def _authors_str(authors: list[str], limit: int = 10) -> str:
    if not authors:
        return "—"
    if len(authors) <= limit:
        return ", ".join(authors)
    return ", ".join(authors[:limit]) + f" <em>et al.</em> (+{len(authors) - limit})"


def _abstract_html(text: str, limit: int = 700) -> str:
    if not text:
        return '<span style="color:#888">(sem abstract disponível)</span>'
    clipped = text.strip()
    if len(clipped) > limit:
        clipped = clipped[:limit].rsplit(" ", 1)[0] + " […]"
    return escape(clipped).replace("\n", "<br>")


def _article_card(a: Article) -> str:
    title_html = escape(a.title)
    if a.url:
        title_html = f'<a href="{escape(a.url)}" style="color:#0b5394;text-decoration:none">{title_html}</a>'

    meta_bits = [escape(a.journal or "—")]
    if a.pub_date:
        meta_bits.append(escape(a.pub_date))
    meta_bits.append(escape(a.source))
    if a.relevance:
        meta_bits.append(f"relevância {a.relevance:.0%}")
    meta = " &nbsp;·&nbsp; ".join(meta_bits)

    summary_block = ""
    if a.summary_pt:
        summary_block = (
            f'<div style="margin:8px 0;padding:8px 10px;background:#eef6ff;'
            f'border-left:3px solid #0b5394;border-radius:3px;font-size:14px">'
            f'<strong>Resumo (IA):</strong> {escape(a.summary_pt)}</div>'
        )

    doi_block = ""
    if a.doi:
        doi_block = (
            f'<div style="font-size:12px;color:#666;margin-top:6px">DOI: '
            f'<a href="https://doi.org/{escape(a.doi)}" style="color:#666">{escape(a.doi)}</a></div>'
        )

    return (
        '<div style="margin:0 0 18px;padding:14px 16px;border:1px solid #e3e3e3;'
        'border-radius:8px;background:#fff">'
        f'<div style="font-size:16px;font-weight:600;line-height:1.35">{title_html}</div>'
        f'<div style="font-size:13px;color:#555;margin:5px 0 2px">{_authors_str(a.authors)}</div>'
        f'<div style="font-size:12px;color:#888;margin-bottom:6px">{meta}</div>'
        f'{summary_block}'
        f'<div style="font-size:13px;color:#333;line-height:1.5">{_abstract_html(a.abstract)}</div>'
        f'{doi_block}'
        '</div>'
    )


def build_html(articles: list[Article], window_days: int) -> str:
    today = date.today().isoformat()
    total = len(articles)

    # Agrupa por subtema -> fonte
    grouped: dict[str, dict[str, list[Article]]] = {}
    for a in articles:
        grouped.setdefault(a.subtema, {}).setdefault(a.source, []).append(a)

    body_parts: list[str] = []
    subtemas = [s for s in SUBTEMA_ORDER if s in grouped] + \
        [s for s in grouped if s not in SUBTEMA_ORDER]

    for subtema in subtemas:
        sub_count = sum(len(v) for v in grouped[subtema].values())
        body_parts.append(
            f'<h2 style="font-size:20px;color:#0b5394;border-bottom:2px solid #0b5394;'
            f'padding-bottom:4px;margin:28px 0 14px">{escape(subtema)} '
            f'<span style="font-size:14px;color:#888;font-weight:400">({sub_count})</span></h2>'
        )
        sources = [s for s in SOURCE_ORDER if s in grouped[subtema]] + \
            [s for s in grouped[subtema] if s not in SOURCE_ORDER]
        for source in sources:
            arts = sorted(grouped[subtema][source],
                          key=lambda x: (x.relevance, x.pub_date), reverse=True)
            body_parts.append(
                f'<h3 style="font-size:15px;color:#444;margin:16px 0 10px">'
                f'{escape(source)} <span style="color:#aaa">· {len(arts)}</span></h3>'
            )
            body_parts.extend(_article_card(a) for a in arts)

    if total == 0:
        body_parts.append(
            '<p style="color:#666">Nenhum artigo novo na janela analisada. '
            'Tudo certo — você está em dia. 🙂</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#f4f5f7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
<div style="max-width:760px;margin:0 auto;padding:24px 18px">
  <div style="background:#0b5394;color:#fff;padding:20px 24px;border-radius:10px 10px 0 0">
    <div style="font-size:22px;font-weight:700">Vigilância de Literatura — Ombro e Cotovelo</div>
    <div style="font-size:13px;opacity:.9;margin-top:4px">
      {today} · últimos {window_days} dias · {total} artigo(s) novo(s)
    </div>
  </div>
  <div style="background:#fbfbfb;padding:18px 22px;border:1px solid #e3e3e3;border-top:none;border-radius:0 0 10px 10px">
    {''.join(body_parts)}
    <p style="font-size:11px;color:#aaa;margin-top:28px;border-top:1px solid #eee;padding-top:12px">
      Apenas metadados abertos (título, autores, periódico, data, abstract, DOI/URL).
      Fontes: PubMed (E-utilities), SciELO (OAI-PMH), OpenAlex (REST).
      Gerado automaticamente por lit-monitor-ombro-cotovelo.
    </p>
  </div>
</div></body></html>"""
