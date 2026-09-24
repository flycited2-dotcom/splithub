# -*- coding: utf-8 -*-
"""Каталог SplitHome: поставщики Русклимат, Daichi, Бриз.

Данные не тянутся отсюда напрямую — база живёт внутри докера на VPS и наружу не
смотрит. Выгрузку делает `export_oasis.ps1` (запрос выполняется на сервере), здесь
только чтение готового `out/oasis_stock.csv`.

Опт-цена у поставщиков лежит в разных полях:
  * Daichi     — `price_wholesale`;
  * Русклимат  — `price_base` («Ваша цена» портала), в `price_wholesale` розница;
  * Бриз       — в БД РОЗНИЦА, настоящий опт отдаёт только API Бриза: его забирает
    `export_breez.ps1` в `out/breez_base.json` и подмешивает сюда по `nc_code`.
    Нет опт-цены — позицию не трогаем, иначе наценка ляжет на розницу.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

COLUMNS = ("source", "nc_code", "brand", "title", "series",
           "price_wholesale", "price_base", "warehouse", "quantity")

#: Как узнать поставщика по полю `source` выгрузки.
BREEZ_MARKERS = ("breez", "бриз")
RUSKLIMAT_MARKERS = ("rusklimat", "русклимат")

#: Склад, который для СплитХаба означает «в наличии здесь и сейчас».
CRIMEA = "Симферополь"


def _number(text: str) -> float:
    try:
        return float((text or "0").replace(",", "."))
    except ValueError:
        return 0.0


def load_breez_base(path: Path | str) -> dict[str, float]:
    """{nc_code: опт-цена} из ответа Бриза `/leftoversnew/` (см. export_breez.ps1).

    Живой формат — словарь «НС → запись», цена лежит в `price: [{base}, {ric}]`.
    """
    source_file = Path(path)
    if not source_file.exists():
        return {}
    data = json.loads(source_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    prices = {}
    for key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        nc = entry.get("nc") or entry.get("nc_code") or key
        for item in entry.get("price") or []:
            if isinstance(item, dict) and item.get("base") is not None:
                prices[str(nc)] = float(item["base"])
                break
    return prices


def load(path: Path | str, breez_base_path: Path | str | None = None) -> list[dict]:
    source_file = Path(path)
    if not source_file.exists():
        return []
    breez_base = load_breez_base(breez_base_path) if breez_base_path else {}
    rows = []
    with io.open(source_file, encoding="utf-8", newline="") as handle:
        for parts in csv.reader(handle, delimiter="|"):
            if len(parts) != len(COLUMNS):
                continue
            row = dict(zip(COLUMNS, parts))
            row["price_wholesale"] = _number(row["price_wholesale"])
            row["price_base"] = _number(row["price_base"])
            row["quantity"] = _number(row["quantity"])
            row["source"] = "oasis"
            row["supplier"] = parts[0]
            row["breez_base"] = breez_base.get(row["nc_code"], 0.0)
            rows.append(row)
    return _one_row_per_product(rows)


def _one_row_per_product(rows: list[dict]) -> list[dict]:
    """Схлопнуть строки по складам: одна позиция — одна запись.

    В выгрузке товар повторяется для каждого склада. Для витрины важен крымский
    остаток, поэтому предпочитаем строку по Симферополю, иначе — с наибольшим
    остатком (цена во всех строках одна).
    """
    def better(candidate: dict, current: dict) -> bool:
        rank = lambda row: (row["warehouse"] == CRIMEA and row["quantity"] > 0, row["quantity"])
        return rank(candidate) > rank(current)

    best: dict[str, dict] = {}
    for row in rows:
        key = row["nc_code"] or row["title"]
        if key not in best or better(row, best[key]):
            best[key] = row
    return list(best.values())


def model_of(offer: dict) -> str:
    return offer.get("title") or ""


def cost_of(offer: dict) -> float:
    """Опт-цена. 0 — значит цену брать неоткуда, позицию не трогаем."""
    supplier = (offer.get("supplier") or "").lower()
    if any(marker in supplier for marker in BREEZ_MARKERS):
        # В БД у Бриза розница; настоящий опт приходит из его API по nc_code.
        return offer.get("breez_base") or 0.0
    if any(marker in supplier for marker in RUSKLIMAT_MARKERS):
        return offer["price_base"] or offer["price_wholesale"]
    return offer["price_wholesale"] or offer["price_base"]


def _is_breez(offer: dict) -> bool:
    return any(marker in (offer.get("supplier") or "").lower() for marker in BREEZ_MARKERS)


def stock_of(offer: dict) -> tuple[str, str]:
    """Крым есть — в наличии; есть на других складах — 3–5 дней; нет — под заказ.

    У Бриза склады вне Крыма (Москва, Ростов) — «Под заказ 7 дней»: так велел
    владелец 24.09.2026, выкладывая эти модели.
    """
    if offer.get("warehouse") == CRIMEA and offer["quantity"] > 0:
        return "in_stock", "В наличии"
    if offer["quantity"] > 0 and not _is_breez(offer):
        return "days_3_5", "3–5 дней"
    return "order_7", "Под заказ 7 дней"


def stock_rank(offer: dict) -> int:
    """Уровень наличия для выбора поставщика (sync.find_offer), а не подпись на витрине.

    Товар Бриза на складе в Москве подписан «Под заказ 7 дней», но он реально есть —
    такой остаток по-прежнему сильнее «нет» и «под заказ» у других поставщиков.
    """
    if offer.get("warehouse") == CRIMEA and offer["quantity"] > 0:
        return 0
    return 2 if offer["quantity"] > 0 else 4


def breez_in_stock_first(offer: dict) -> int:
    """Выбор среди строк с одним и тем же кодом (matching.lookup_within, prefer).

    У Бриза одна модель бывает в двух сериях (Hisense HEAVY: «R32» без остатка и
    «Wi-Fi» на складе) — берём ту, что на складе. Строки других поставщиков порядок
    не меняют: у JAC в базе так лежат MDV с Wi-Fi и без, а их наличие и цены
    владелец велел не трогать.
    """
    return stock_rank(offer) if _is_breez(offer) else 0
