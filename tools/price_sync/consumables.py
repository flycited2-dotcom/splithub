# -*- coding: utf-8 -*-
"""Сопоставление расходников с прайсом трио.рус по СУТИ товара, а не по названию.

Бренд у расходника роли не играет: у нас «16 гибкий Ballu 30 м», у поставщика —
«Шланг гибкий гофрированный, 16мм, 30м». Сопоставляем по характеристикам: диаметр,
толщина стенки, длина бухты, размер кронштейна, марка фреона.

Крепёж поставщик считает поштучно, а наша карточка — упаковкой по 50 штук
(подтверждено владельцем 11.09.2026), поэтому цена за штуку умножается на PACK_SIZE.
Позиции, где фасовка по-прежнему неизвестна (изоляция, кабель, дюбели), сюда НЕ
попадают: их нельзя пересчитать вслепую, иначе болт за 230 ₽ превратится в 4 ₽.
Они уходят в список кандидатов на подтверждение.
"""
from __future__ import annotations

import re

#: Разделы прайса трио, где лежат расходники.
SECTION_COPPER = 49
SECTION_DRAINAGE = 54
SECTION_TAPE = 57
SECTION_FREON = 58
SECTION_BRACKETS = 48
SECTION_FASTENERS = 412

#: Толщины в пределах этого допуска считаем одним классом стенки.
WALL_TOLERANCE = 0.02

_COPPER = re.compile(r"(\d+/\d+)\s*\([\d,.]+мм\.?\),\s*([\d,.]+)мм,\s*(\d+)м")
_CARD_COPPER = re.compile(r"(\d+/\d+).*?(\d+)\s*м")
_BRACKET_TRIO = re.compile(r"(\d+)\s*[xх]\s*(\d+).*?S\s*=\s*([\d,.]+)")
_BRACKET_CARD = re.compile(r"(\d+)-(\d+)-([\d,.]+)")

#: Карточка (по модели) → строка прайса трио (по вхождению текста).
DIRECT = {
    "16 гибкий 30 м. бухта": (SECTION_DRAINAGE, "Шланг гибкий гофрированный, 16мм, 30м"),
    "16 гибкий Ruvinil 30 м. бухта": (SECTION_DRAINAGE, "Шланг гибкий гофрированный, 16мм, 30м RuVinil"),
    "16 гибкий Ballu 30 м. бухта": (SECTION_DRAINAGE, "Шланг гибкий гофрированный, 16мм, 30м RuVinil"),
    "75ммх50м AVIORA PROFFI": (SECTION_TAPE, "Лента для защиты термоизоляции AVIORA PROFFI 75мм*50м"),
    "Фреон R-410a": (SECTION_FREON, "R-410a"),
    "Фреон R-32": (SECTION_FREON, "R-32"),
    "Фреон R-134a": (SECTION_FREON, "R-134a"),
}


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def _copper_offers(rows):
    """Прайс меди → {(диаметр, длина): [(толщина, цена, строка)]}."""
    grouped = {}
    for row in rows:
        if row["section"] != SECTION_COPPER:
            continue
        found = _COPPER.search(row["model"])
        if not found:
            continue
        diameter, wall, length = found.group(1), _number(found.group(2)), int(found.group(3))
        grouped.setdefault((diameter, length), []).append((wall, row))
    return grouped


def _copper_pick(offers, thick: bool):
    """Толстая (ГОСТ) — самый толстый класс стенки, средняя — все остальные.

    Внутри класса берём самое дешёвое предложение: марка/завод владельцу не важны.
    """
    heaviest = max(wall for wall, _ in offers)
    if thick:
        tier = [row for wall, row in offers if wall >= heaviest - WALL_TOLERANCE]
    else:
        tier = [row for wall, row in offers if wall < heaviest - WALL_TOLERANCE]
    if not tier:
        return None
    return min(tier, key=lambda row: row["dealer"])


def _match_copper(product, rows):
    found = _CARD_COPPER.search(product["model"])
    if not found:
        return None
    key = (found.group(1), int(found.group(2)))
    offers = _copper_offers(rows).get(key)
    if not offers:
        return None
    thick = "ГОСТ" in (product.get("descShort") or "") or "олст" in (product.get("descShort") or "")
    return _copper_pick(offers, thick)


def _match_bracket(product, rows):
    """Кронштейн сопоставляем по размеру и толщине металла, серия не важна."""
    found = _BRACKET_CARD.search(product["model"])
    if not found:
        return None
    width, height, thickness = int(found.group(1)), int(found.group(2)), _number(found.group(3))
    best = None
    for row in rows:
        if row["section"] != SECTION_BRACKETS:
            continue
        trio = _BRACKET_TRIO.search(row["model"])
        if not trio:
            continue
        if {int(trio.group(1)), int(trio.group(2))} != {width, height}:
            continue
        if abs(_number(trio.group(3)) - thickness) > 0.01:
            continue
        if best is None or row["dealer"] < best["dealer"]:
            best = row
    return best


def _match_direct(product, rows):
    target = DIRECT.get(product["model"])
    if not target:
        return None
    section, needle = target
    for row in rows:
        if row["section"] == section and row["model"].startswith(needle):
            return row
    return None


#: В карточках крепежа у нас упаковка, у поставщика — штука.
PACK_SIZE = 50

#: Карточка крепежа → точное название позиции в разделе «Крепёж» прайса трио.
FASTENERS = {
    "Болт 8-25": "Болт 8х25 ОЦ",
    "Болт 8-30": "Болт 8х30 ОЦ",
    "Болт 8-35": "Болт 8х35 ОЦ",
    "Гайка М10": "Гайка М10 ОЦ.",
    "Гайка М8-пресшайба": "Гайка М8 с фланцем ОЦ.",
    "шайба м8 увеличенная": "Шайба увеличенная М8 ОЦ.",
    "Глухарь 8-100мм(50шт)": "8х100",
    "Глухарь 8-120мм(50шт)": "8х120",
    "Глухарь 8-140мм(50шт)": "8х140",
    "Глухарь 8-160мм(50шт)": "8х160",
    "Глухарь 8-180мм(50шт)": "8х180",
    "Глухарь 8-200мм(50шт)": "8х200",
    # У трио нет ни «KPO 12х80», ни безымянного «6х40»: берём ближайший ходовой
    # аналог той же серии Tchappai. Для 12х80 ближайший размер — 12x70.
    "Дюбель 6х40": "Дюбель Tchappai 6х40 (полипропилен)",
    "Дюбель распорн KPO 12х80(50шт)": "Дюбель Tchappai 12x70 (полипропилен)",
}


def _match_fastener(product, rows):
    """Цена за штуку × 50: наша карточка — упаковка, прайс поставщика — поштучно."""
    target = FASTENERS.get(product["model"])
    if not target:
        return None
    for row in rows:
        if row["section"] == SECTION_FASTENERS and row["model"].strip() == target:
            packed = dict(row)
            packed["dealer"] = row["dealer"] * PACK_SIZE
            packed["promo"] = row["promo"] * PACK_SIZE if row["promo"] else None
            packed["model"] = "%s x%d шт" % (row["model"], PACK_SIZE)
            return packed
    return None


def match(product: dict, trio_rows: list[dict]):
    """Найти строку прайса трио для карточки расходника. None — сопоставления нет."""
    if product.get("group") == "truba":
        return _match_copper(product, trio_rows)
    if product.get("brand") == "Кронштейны":
        return _match_bracket(product, trio_rows)
    return _match_fastener(product, trio_rows) or _match_direct(product, trio_rows)


#: Разделы прайса, в которых вообще имеет смысл искать расходник.
RASHOD_SECTIONS = (48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 407, 412)

_TOKEN = re.compile(r"[a-zа-я]{3,}|\d+(?:[,.]\d+)?", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {t.lower().replace(",", ".") for t in _TOKEN.findall(text or "")}


def candidates(product: dict, trio_rows: list[dict], limit: int = 3) -> list[tuple[float, dict]]:
    """Похожие строки прайса для позиции, которую не удалось сопоставить строго.

    Нужно там, где у нашей карточки неизвестна фасовка («Болт 8-25» за 230 ₽ против
    3,40 ₽ за штуку у поставщика): цену такой позиции считает человек, не скрипт.
    """
    mine = _tokens(product.get("model", "")) | _tokens(product.get("descShort", ""))
    scored = []
    for row in trio_rows:
        if row["section"] not in RASHOD_SECTIONS:
            continue
        theirs = _tokens(row["model"])
        if not theirs:
            continue
        common = mine & theirs
        if not common:
            continue
        scored.append((len(common) / len(mine | theirs), row))
    scored.sort(key=lambda pair: -pair[0])
    return scored[:limit]
