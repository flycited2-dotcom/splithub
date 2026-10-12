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

Разделы, которые владелец прислал 25.09.2026 (медь, кронштейны, дренажные насосы,
лента, дренаж, фреон), ведутся реестром `rashod_map.json`: карточка по sku → точная
строка прайса и текст карточки. Реестр решает раньше угадывания по характеристикам.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from tools.price_sync import sources_trio

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


def _is_thick(row, wall: float, heaviest: float) -> bool:
    """Толстая (ГОСТ) или средняя стенка. Трио пишет класс в названии серии
    («труба медная ТОЛСТАЯ стенка. ОАЭ») — ему и верим: иначе, когда толстой на
    размер нет вовсе, самая толстая из средних ушла бы под видом ГОСТа. Серии нет —
    толстая та, что в самом толстом классе среди предложений на этот размер."""
    series = (row.get("series") or "").upper()
    if "ТОЛСТ" in series:
        return True
    if "СРЕДН" in series:
        return False
    return wall >= heaviest - WALL_TOLERANCE


#: Наличие важнее цены (владелец 24.09.2026): «есть» → «Мск» → всё остальное.
_COPPER_STOCK = {"есть": 0, "мск": 1}


def _copper_pick(offers, thick: bool):
    """Толстая (ГОСТ) или средняя стенка — из предложений всех заводов трио.

    Владелец 25.09.2026: «модель писать не обязательно» — завод (ОАЭ, Узбекистан,
    Россия) ему не важен. Внутри класса берём то, что есть на складе, из этого —
    самое дешёвое.
    """
    heaviest = max(wall for wall, _ in offers)
    tier = [row for wall, row in offers if _is_thick(row, wall, heaviest) == thick]
    if not tier:
        return None
    return min(tier, key=lambda row: (_COPPER_STOCK.get(row.get("availability"), 2), row["dealer"]))


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


REGISTRY_FILE = Path(__file__).resolve().parent / "rashod_map.json"


@lru_cache(maxsize=None)
def load_registry(path: Path = REGISTRY_FILE) -> dict[str, dict]:
    """Реестр расходников трио: {sku: запись}. Нет файла — пустой реестр."""
    if not path.exists():
        return {}
    items = json.loads(path.read_text(encoding="utf-8")).get("items", [])
    return {item["sku"]: item for item in items}


def registry(given: dict | None = None) -> dict[str, dict]:
    return load_registry() if given is None else given


def registry_entry(product: dict, given: dict | None = None):
    return registry(given).get(product.get("sku") or "")


def _plain(text: str) -> str:
    """Название без двойных и неразрывных пробелов — у трио они гуляют."""
    return " ".join((text or "").replace("\xa0", " ").split())


def _registry_offer(entry: dict, rows):
    """Строка прайса для записи реестра — по точному названию в своём разделе.

    `pack` — сколько единиц прайса в нашей карточке (металлопласт: 44 ₽ за метр,
    у нас бухта 100 м). `pack_promo` — в поле акции трио пишет цену всей фасовки
    («Акция 3800 за бухту 100м»), её не умножаем.
    """
    wanted = _plain(entry["trio"])
    row = next((row for row in rows
                if row["section"] == entry["section"] and _plain(row["model"]) == wanted), None)
    pack = entry.get("pack", 1)
    if row is None or pack == 1:
        return row
    packed = dict(row)
    packed["dealer"] = row["dealer"] * pack
    if row["promo"] and not entry.get("pack_promo"):
        packed["promo"] = row["promo"] * pack
    return packed


def delisted(product: dict, rows, given: dict | None = None) -> bool:
    """Позиция реестра, которой у трио больше нет или цена 0,00 — «Нет в наличии».

    Владелец: «какого нет — естественно пишешь нет в наличии». Но если раздел прайса
    не скачался целиком, это сбой разбора, а не снятие с продажи — ничего не гасим.
    """
    entry = registry_entry(product, given)
    if entry is None or not entry.get("trio"):
        return False
    if not any(row["section"] == entry["section"] for row in rows):
        return False
    offer = _registry_offer(entry, rows)
    return offer is None or sources_trio.cost_of(offer) <= 0


#: Текст карточки, который задаёт реестр. Цена, наличие, id и sku — не отсюда.
CARD_TEXT = ("brand", "brandCode", "series", "model", "descShort", "cardBenef", "benefits", "photo")


def apply_cards(catalog: list[dict], given: dict | None = None) -> int:
    """Текст уже выложенных карточек расходников — из реестра. Повторный вызов
    ничего не меняет. Возвращает число изменённых карточек."""
    entries = registry(given)
    changed = 0
    for product in catalog:
        card = (entries.get(product.get("sku") or "") or {}).get("card") or {}
        fresh = {field: card[field] for field in CARD_TEXT if field in card}
        if any(product.get(field) != value for field, value in fresh.items()):
            product.update({field: list(value) if isinstance(value, list) else value
                            for field, value in fresh.items()})
            changed += 1
    return changed


def match(product: dict, trio_rows: list[dict], given: dict | None = None):
    """Найти строку прайса трио для карточки расходника. None — сопоставления нет."""
    entry = registry_entry(product, given)
    if entry is not None:
        return _registry_offer(entry, trio_rows) if entry.get("trio") else None
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
