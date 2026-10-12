# -*- coding: utf-8 -*-
"""Прайс поставщика JAC (b2b-jac.com) — бренды MDV, THAICON, Mitsubishi Heavy, EUROKLIMAT.

API у поставщика нет: остатки и «Вашу цену» собирает скрапер проекта
`osatakti_mdv_b2b` в `data/jac_stock_latest.json`. Здесь только чтение этого файла.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

#: На сервере сверки путь другой — его задаёт SPLITHUB_JAC_JSON (см. server/run_sync.sh).
DEFAULT_STOCK_JSON = Path(os.getenv(
    "SPLITHUB_JAC_JSON",
    r"C:\Users\TLT-1\Documents\GitHub\osatakti_mdv_b2b\data\jac_stock_latest.json"))

_DIGITS = re.compile(r"\d+")


def _qty(raw) -> int:
    """Остаток из текста склада: «12», «Больше 30» → число, пусто → 0."""
    if raw is None:
        return 0
    found = _DIGITS.search(str(raw).replace("\xa0", " "))
    return int(found.group(0)) if found else 0


def _crimea_qty(offer: dict) -> int:
    for name, value in (offer.get("attributes") or {}).items():
        if "Крым" in name and "Москва" not in name:
            return _qty(value)
    return 0


def load(path: Path | str | None = None) -> list[dict]:
    source = Path(path or DEFAULT_STOCK_JSON)
    if not source.exists():
        # Срез ещё не доехал с компьютера — позиции JAC просто остаются как были
        # (в отчёте сверки видно «JAC 0»), остальные поставщики считаются дальше.
        return []
    rows = json.loads(source.read_text(encoding="utf-8"))
    for row in rows:
        row["source"] = "jac"
    return rows


def model_of(offer: dict) -> str:
    return offer.get("article") or offer.get("name") or ""


def cost_of(offer: dict) -> float:
    return float(offer.get("price") or 0)


def stock_of(offer: dict) -> tuple[str, str]:
    """Крым → в наличии; иначе, в том числе склад Москвы, — под заказ 7 дней
    (владелец 11.10.2026: «3–5 дней» не бывает)."""
    if _crimea_qty(offer) > 0:
        return "in_stock", "В наличии"
    return "order_7", "Под заказ 7 дней"


def stock_rank(offer: dict) -> int:
    """Для выбора поставщика: склад Москвы — реальный остаток, сильнее «нет» у других."""
    if _crimea_qty(offer) > 0:
        return 0
    return 2 if float(offer.get("stock_qty") or 0) > 0 else 4
