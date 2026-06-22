"""Persistência unificada: histórico de artigos (alimenta o dashboard) e
deduplicação entre execuções. É o `docs/data/articles.json` versionado no repo,
servido pelo GitHub Pages."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, datetime

from article import Article


class ArticleStore:
    def __init__(self, data_path: str = "docs/data/articles.json",
                 meta_path: str = "docs/data/meta.json"):
        self.data_path = data_path
        self.meta_path = meta_path
        self.records: list[dict] = []
        self._keys: set[str] = set()
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    self.records = json.load(f) or []
                self._keys = {r.get("dedup_key", "") for r in self.records}
            except (json.JSONDecodeError, OSError):
                self.records, self._keys = [], set()

    def is_seen(self, key: str) -> bool:
        return key in self._keys

    def add(self, article: Article, added: str) -> None:
        d = asdict(article)
        d["added"] = added
        d["dedup_key"] = article.dedup_key
        self.records.append(d)
        self._keys.add(article.dedup_key)

    def save(self, max_items: int = 5000) -> None:
        # Mais recentes primeiro (por data de captura, depois publicação).
        self.records.sort(
            key=lambda r: (r.get("added", ""), r.get("pub_date", "")),
            reverse=True,
        )
        if max_items and len(self.records) > max_items:
            self.records = self.records[:max_items]

        os.makedirs(os.path.dirname(self.data_path) or ".", exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=1)

        self._write_meta()

    def _write_meta(self) -> None:
        by_sub: dict[str, int] = {}
        by_src: dict[str, int] = {}
        for r in self.records:
            by_sub[r.get("subtema", "Geral")] = by_sub.get(r.get("subtema", "Geral"), 0) + 1
            by_src[r.get("source", "?")] = by_src.get(r.get("source", "?"), 0) + 1
        meta = {
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "generated_date": date.today().isoformat(),
            "total": len(self.records),
            "by_subtema": by_sub,
            "by_source": by_src,
        }
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
