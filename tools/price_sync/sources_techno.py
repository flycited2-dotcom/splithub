# -*- coding: utf-8 -*-
"""Прайс поставщика ТЕХНОСИСТЕМС: бытовые сплиты, полупром, мультисплит.

Сайта у поставщика нет — прайс приходит сообщением в Telegram, поэтому он живёт
в `technosystems_price.csv` рядом. Пришёл новый прайс — правится этот файл.

Правило владельца: когда в прайсе две цены через слэш («15 500 / 14 300»),
за основу берётся **бо́льшая**.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

DEFAULT_PRICE_FILE = Path(__file__).resolve().parent / "technosystems_price.csv"

#: Наличие из прайса → (stock, stockLabel) каталога.
STOCK_MAP = {
    "есть": ("in_stock", "В наличии"),
    "под заказ": ("order_7", "Под заказ 7 дней"),
    "": ("order_7", "Под заказ 7 дней"),
}


def _number(text: str) -> float:
    cleaned = (text or "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def load(path: Path | str | None = None) -> list[dict]:
    source_file = Path(path or DEFAULT_PRICE_FILE)
    if not source_file.exists():
        return []
    rows = []
    with io.open(source_file, encoding="utf-8-sig", newline="") as handle:
        for entry in csv.DictReader(handle, delimiter=";"):
            model = (entry.get("модель") or "").strip()
            if not model:
                continue
            rows.append({
                "source": "techno",
                "brand": (entry.get("бренд") or "").strip(),
                "series": (entry.get("серия") or "").strip(),
                "model": model,
                "category": (entry.get("категория") or "").strip(),
                "price_1": _number(entry.get("цена_1")),
                "price_2": _number(entry.get("цена_2")),
                "availability": (entry.get("наличие") or "").strip().lower(),
                "note": (entry.get("примечание") or "").strip(),
            })
    return rows


def model_of(offer: dict) -> str:
    return offer["model"]


def cost_of(offer: dict) -> float:
    """Из двух цен прайса берём бо́льшую. Нет цены («уточняйте») — 0, позицию не трогаем."""
    return max(offer["price_1"], offer["price_2"])


def stock_of(offer: dict) -> tuple[str, str]:
    return STOCK_MAP.get(offer["availability"], ("order_7", "Под заказ 7 дней"))
