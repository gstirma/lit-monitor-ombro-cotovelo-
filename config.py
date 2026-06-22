"""Carregamento da configuração externa (config.yaml)."""
from __future__ import annotations

import os

import yaml


def load_config(path: str | None = None) -> dict:
    path = path or os.environ.get("LIT_CONFIG", "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    # defaults defensivos
    cfg.setdefault("window_days", 3)
    cfg.setdefault("search", {})
    cfg.setdefault("journals", [])
    cfg.setdefault("email", {})
    cfg.setdefault("pubmed", {})
    cfg.setdefault("scielo", {})
    cfg.setdefault("openalex", {})
    cfg.setdefault("google_scholar", {})
    cfg.setdefault("anthropic", {})
    cfg.setdefault("sources", {})
    return cfg
