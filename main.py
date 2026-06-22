"""Orquestrador: busca nas fontes, deduplica, enriquece, monta e envia o digest."""
from __future__ import annotations

import argparse
import os
from datetime import date, timedelta

from article import Article, classify_subtema, within_window
from config import load_config
from digest import build_html
from emailer import send_email
from enrich import enrich
from store import ArticleStore

import sources.openalex as openalex
import sources.pubmed as pubmed
import sources.scielo as scielo

SOURCE_FETCHERS = {
    "pubmed": pubmed.fetch,
    "scielo": scielo.fetch,
    "openalex": openalex.fetch,
}


def collect(since: date, cfg: dict) -> list[Article]:
    enabled = cfg.get("sources", {})
    found: list[Article] = []
    for name, fetcher in SOURCE_FETCHERS.items():
        if not enabled.get(name, True):
            print(f"[{name}] desativado no config — pulando.")
            continue
        try:
            arts = fetcher(since, cfg)
            print(f"[{name}] {len(arts)} artigo(s) retornado(s).")
            found.extend(arts)
        except Exception as exc:  # noqa: BLE001 — uma fonte não pode derrubar o run
            print(f"[{name}] ERRO: {exc}")
    return found


def dedupe(articles: list[Article], since: date, store: ArticleStore) -> list[Article]:
    seen_now: set[str] = set()
    out: list[Article] = []
    for a in articles:
        if not within_window(a.pub_date, since):
            continue
        key = a.dedup_key
        if key in seen_now or store.is_seen(key):
            continue
        seen_now.add(key)
        out.append(a)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Digest de literatura — ombro e cotovelo")
    parser.add_argument("--config", default=None)
    parser.add_argument("--days", type=int, default=None, help="sobrescreve window_days")
    parser.add_argument("--dry-run", action="store_true",
                        help="não envia e-mail nem marca artigos como vistos")
    parser.add_argument("--no-email", action="store_true", help="não envia e-mail")
    args = parser.parse_args()

    cfg = load_config(args.config)
    window = args.days or cfg.get("window_days", 3)
    since = date.today() - timedelta(days=window)
    print(f"Janela: últimos {window} dias (desde {since.isoformat()}).")

    dash = cfg.get("dashboard", {})
    store = ArticleStore(
        data_path=dash.get("data_path", "docs/data/articles.json"),
        meta_path=dash.get("meta_path", "docs/data/meta.json"),
    )

    articles = collect(since, cfg)
    print(f"Total bruto: {len(articles)}.")

    fresh = dedupe(articles, since, store)
    print(f"Novos após dedup/histórico: {len(fresh)}.")

    # Garante subtema para todos (a IA pode refinar em seguida)
    for a in fresh:
        if a.subtema == "Geral":
            a.subtema = classify_subtema(a)

    fresh = enrich(fresh, cfg)
    fresh.sort(key=lambda x: (x.relevance, x.pub_date), reverse=True)

    html = build_html(fresh, window)

    # Salva o HTML como artifact
    os.makedirs("output", exist_ok=True)
    out_path = f"output/digest-{date.today().isoformat()}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML salvo em {out_path}.")

    send_if_empty = cfg.get("email", {}).get("send_if_empty", False)
    should_email = (not args.dry_run and not args.no_email
                    and (fresh or send_if_empty))
    if should_email:
        subject = f"[Ombro & Cotovelo] {len(fresh)} novo(s) artigo(s) — {date.today().isoformat()}"
        send_email(html, subject)
    elif not fresh:
        print("Nenhum artigo novo — e-mail não enviado (send_if_empty=false).")

    if not args.dry_run:
        today = date.today().isoformat()
        for a in fresh:
            store.add(a, added=today)
        store.save(max_items=cfg.get("dashboard", {}).get("max_items", 5000))
        print(f"Histórico salvo: {len(store.records)} artigos em {store.data_path}.")


if __name__ == "__main__":
    main()
