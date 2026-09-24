# -*- coding: utf-8 -*-
"""Заготовки карточек для товаров, которых ещё нет на витрине.

Делает только то, что ЧЕСТНО выводится из прайса: артикул, бренд, серию, завод,
типоразмер, группу, цену и наличие. Содержательные поля (описание, преимущества,
компрессор, фреон) остаются пустыми — их наполняют из интернета или руками.
Ничего не выдумываем: пустое поле честнее правдоподобной ошибки.

    python -m tools.price_sync.new_cards            # -> out/new_cards_draft.json + .csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

from tools.price_sync import matching, pricing, sources_techno, sync
from tools.price_sync.sync import DEFAULT_OUT, load_catalog

#: Завод-изготовитель указан в прайсе в скобках: «TCL on/off», «ASTRID (Midea)».
FACTORIES = ("TCL", "Midea", "Gree", "AUX", "GMCC", "Changhong")

#: Типоразмер (BTU) по числу в артикуле. У полупрома в коде киловатты, не BTU.
_BTU = re.compile(r"(?<!\d)(07|09|12|18|20|24|30|36|48|60)(?!\d)")

#: Площадь помещения по типоразмеру — как в соседних карточках каталога.
AREA_BY_BTU = {"07": 20, "09": 25, "12": 35, "18": 50, "24": 70,
               "30": 85, "36": 100, "48": 130, "60": 160, "20": 20}

#: Категория прайса → группа каталога.
GROUP_BY_CATEGORY = {
    "настенный": "inv",
    "кассета": "pac_onoff",
    "канальный": "pac_onoff",
    "напольно-потолочный": "pac_onoff",
    "колонный": "pac_onoff",
    "мультисплит наружный": "pac_onoff",
    "мультисплит внутренний": "pac_onoff",
}

TRANSLIT = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
            "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
            "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
            "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e",
            "ю": "yu", "я": "ya"}


def slug(text: str) -> str:
    latin = "".join(TRANSLIT.get(char, char) for char in text.lower())
    return re.sub(r"[^a-z0-9]+", "-", latin).strip("-")


def is_inverter(offer: dict) -> bool:
    haystack = (offer["series"] + " " + offer["model"]).lower()
    return "inv" in haystack or haystack.rstrip().endswith("-i") or "-i " in haystack


def factory_of(offer: dict) -> str:
    for name in FACTORIES:
        if name.lower() in offer["series"].lower():
            return name
    return ""


def btu_of(offer: dict) -> str:
    found = _BTU.search(offer["model"])
    return found.group(1) if found else ""


def group_of(offer: dict) -> str:
    base = GROUP_BY_CATEGORY.get(offer["category"], "inv")
    if base == "inv" and not is_inverter(offer):
        return "onoff"
    return base


CONTENT_FILE = Path(__file__).resolve().parent / "card_content.json"


def load_content(path: Path | None = None) -> tuple[dict, dict]:
    """Наполнение карточек: {«Бренд|Серия»: поля} и точечные правки по моделям."""
    source = Path(path or CONTENT_FILE)
    if not source.exists():
        return {}, {}
    data = json.loads(source.read_text(encoding="utf-8"))
    by_model = {k: v for k, v in (data.get("_модели") or {}).items() if isinstance(v, dict)}
    by_series = {k: v for k, v in data.items()
                 if not k.startswith("_") and isinstance(v, dict)}
    return by_series, by_model


def enrich(card: dict, by_series: dict, by_model: dict) -> dict:
    """Дописать в карточку описание и преимущества. Нет данных — поля остаются пустыми."""
    filled = dict(card)
    content = dict(by_series.get(card["brand"] + "|" + card["series"], {}))
    content.update(by_model.get(card["model"], {}))
    if not content:
        return filled
    for field in ("cardBenef", "compressor", "freon", "area", "btu"):
        if content.get(field):
            filled[field] = content[field]
    if content.get("benefits"):
        filled["benefits"] = list(content["benefits"])
    template = content.get("descTemplate")
    if template:
        filled["descShort"] = template.format(btu=filled["btu"], area=filled["area"])
    return filled


#: Поля, которые новинка наследует от «родственника» — соседней мощности той же линейки.
INHERITED = ("cardBenef", "benefits", "compressor", "freon", "photo", "group", "series")

_DIGITS = re.compile(r"\d+")


def family_key(brand: str, model: str) -> str:
    """Линейка без типоразмера: «EM-07I» и «EM-09I inv» — одна семья, «DU-07» — нет.

    Опираемся на ту же нормализацию, что и сопоставление прайсов: она уже снимает
    хвосты «inv» и «on/off», из-за которых соседние мощности выглядели бы разными.
    """
    bare = matching.normalize(model)
    prefix = matching.normalize(brand)
    if prefix and bare.startswith(prefix):
        bare = bare[len(prefix):]
    return _DIGITS.sub("#", bare)


def find_sibling(card: dict, catalog: list[dict]):
    """Карточка той же линейки, уже стоящая на витрине. Она — лучший образец наполнения."""
    key = family_key(card["brand"], card["model"])
    for product in catalog:
        if product["brand"] != card["brand"]:
            continue
        if family_key(product["brand"], product["model"]) == key:
            return product
    return None


def inherit(card: dict, sibling: dict) -> dict:
    """Взять наполнение у родственной модели и подставить свой типоразмер.

    Описание соседа «Инвертор 09 BTU · до 25 м²» для 07 BTU превращается в
    «Инвертор 07 BTU · до 20 м²»: меняются только числа, стиль каталога сохраняется.
    """
    filled = dict(card)
    for field in INHERITED:
        if sibling.get(field):
            value = sibling[field]
            filled[field] = list(value) if isinstance(value, list) else value
    description = sibling.get("descShort") or ""
    if description and sibling.get("btu") and card["btu"]:
        description = description.replace(str(sibling["btu"]), card["btu"])
        if sibling.get("area") and card["area"]:
            description = description.replace(str(sibling["area"]), str(card["area"]))
        filled["descShort"] = description
    return filled


def brand_code_for(brand: str, catalog: list[dict]) -> str:
    """Код бренда для новой карточки.

    Витрина строит блоки каталога по `brandCode`: сколько разных кодов у бренда —
    столько блоков он и займёт. Поэтому для бренда, который уже есть на витрине,
    берём его код, а не выдумываем новый: иначе DAICHI покажется двумя блоками.
    """
    existing = [product["brandCode"] for product in catalog if product["brand"] == brand]
    if existing:
        return collections.Counter(existing).most_common(1)[0][0]
    return slug(brand)


def next_id(catalog: list[dict]) -> int:
    numeric = [int(p["id"]) for p in catalog if str(p["id"]).isdigit()]
    return max(numeric) + 1 if numeric else 2000


def build(offers: list[dict], catalog: list[dict]) -> list[dict]:
    """Карточки-заготовки для позиций прайса, которых нет в каталоге."""
    index = matching.build_text_index(catalog, lambda product: product["model"])
    by_series, by_model = load_content()
    identifier = next_id(catalog)
    cards = []
    for offer in offers:
        if matching.lookup_either(index, offer["model"]):
            continue
        cost = sources_techno.cost_of(offer)
        btu = btu_of(offer)
        stock, stock_label = sources_techno.stock_of(offer)
        card = {
            "id": str(identifier),
            "sku": slug(offer["brand"]) + "-" + slug(offer["model"]),
            "brandCode": brand_code_for(offer["brand"], catalog),
            "brand": offer["brand"],
            "series": offer["series"],
            "model": offer["brand"] + " " + offer["model"],
            "group": group_of(offer),
            "type": "split",
            "factory": factory_of(offer),
            "color": "white",
            "btu": btu,
            "area": AREA_BY_BTU.get(btu, 0),
            "price": pricing.compute_price(cost, "techno") if cost > 0 else 0,
            "stock": stock,
            "stockLabel": stock_label,
            "descShort": "",          # ← из интернета
            "cardBenef": "",          # ← из интернета
            "benefits": [],           # ← из интернета
            "compressor": "",         # ← из интернета
            "freon": "",              # ← из интернета
            "photo": slug(offer["brand"]) + "-" + slug(offer["series"]) + ".webp",
        }
        sibling = find_sibling(card, catalog)
        if sibling is not None:
            card = inherit(card, sibling)
        cards.append(enrich(card, by_series, by_model))
        identifier += 1
    return cards


# ── Новинки из прайсов трио и Бриза по реестру серий ───────────────────────────

SERIES_FILE = Path(__file__).resolve().parent / "series_map.json"

#: Склад Бриза, который для СплитХаба означает «в наличии».
CRIMEA = "Симферополь"

#: Типоразмер в киловаттах×10 (DAICHI DA20, FUNAI KD55) → BTU витрины.
KW_TO_BTU = {"20": "07", "22": "07", "25": "09", "26": "09", "28": "09", "30": "09",
             "35": "12", "40": "12", "45": "18", "50": "18", "53": "18", "55": "18",
             "60": "24", "65": "24", "70": "24", "75": "24"}
_BTU_CODE = re.compile(r"(?<![\d.])(07|09|12|18|24|28|30|36|48|60)(?!\d)")
_KW_CODE = re.compile(r"(?<=[A-Z])(\d{2})(?=[A-Z])")


def load_series_map(path: Path = SERIES_FILE) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("series", [])


def _title(text: str) -> str:
    """Название серии для сравнения: у трио двойные пробелы и «On\Off» через обратный слэш."""
    return re.sub(r"\s+", " ", (text or "").replace(chr(92), "/")).strip().lower()


def trio_code(model: str) -> str:
    """Код внутреннего блока из строки трио.

    «MSES1S-07FRN8G1/MOES1-07FRN8G1» → «MSES1S-07FRN8G1». У Roland «/N6» — часть кода,
    а блоки разделены хвостами «-IN»/«-OUT»: «FU-07HSS010/N6-IN FU-…» → «FU-07HSS010/N6».
    """
    text = re.sub(r"\s*/\s*", "/", model.strip())
    indoor = re.match(r"(.+?)-IN\b", text)
    if indoor:
        return indoor.group(1)
    return text.split("/")[0].strip()


def breez_code(title: str, series: str) -> str:
    """Код модели из названия Бриза: всё, что после названия серии, без «(комплект)».

    Регистр у Бриза гуляет («INVERTER» в названии, «Inverter» в серии) — ищем без него.
    """
    short = series.split("серии", 1)[-1].strip() if "серии" in series else series.strip()
    position = title.lower().find(short.lower())
    tail = title[position + len(short):] if position >= 0 else title
    return re.sub(r"\(комплект\)", "", tail, flags=re.I).strip()


def size_of(code: str, kind: str) -> str:
    """Типоразмер по коду: BTU (MSES1-07) или киловатты×10 (DA20, ICE60 = 6 кВт)."""
    upper = code.upper()
    if kind == "kw":
        found = _KW_CODE.search(upper)
        return KW_TO_BTU.get(found.group(1), "") if found else ""
    found = _BTU_CODE.search(upper)
    return found.group(1) if found else ""


def supplier_offers(trio_rows: list[dict], oasis_rows: list[dict], registry: list[dict]):
    """(серия реестра, код модели, строка прайса) — всё, что есть в наличии.

    Трио — только «есть». Бриз — только остаток на складе в Симферополе.
    """
    for entry in registry:
        match = _title(entry["match"])
        if entry["supplier"] == "trio":
            for row in trio_rows:
                if row.get("availability") != "есть":
                    continue
                if entry.get("section") and row.get("section") != entry["section"]:
                    continue
                if not _title(row.get("series")).startswith(match):
                    continue
                if entry.get("code") == "pair":
                    code = re.sub(r"\s*/\s*", "/", row["model"].strip())
                else:
                    code = trio_code(row["model"])
                yield entry, code, row
        elif entry["supplier"] == "breez":
            for row in oasis_rows:
                if (row.get("supplier") or "").lower() not in ("breeze", "breez", "бриз"):
                    continue
                if row.get("warehouse") != CRIMEA or row.get("quantity", 0) <= 0:
                    continue
                wanted = entry.get("brand_at_supplier")
                if wanted and (row.get("brand") or "").lower() != wanted.lower():
                    continue
                if _title(row.get("series")) != match:
                    continue
                yield entry, breez_code(row["title"], row["series"]), row


def _bare(model: str, brand: str) -> str:
    code = matching.normalize(model)
    prefix = matching.normalize(brand)
    return code[len(prefix):] if prefix and code.startswith(prefix) else code


def catalog_codes(catalog: list[dict]) -> list[str]:
    """Коды моделей каталога без бренда — для поиска дублей."""
    return [_bare(product["model"], product.get("brand", "")) for product in catalog]


def already_listed(codes: list[str], code: str, min_length: int = 5) -> bool:
    """Модель уже на витрине — совпадением или вхождением кода в любую сторону.

    На сайте «DAICHI SIB25» (короткий код Техносистемса), у трио «SIB25AVQS1R» — один товар.
    """
    mine = matching.normalize(code)
    if len(mine) < min_length:
        return False
    return any(len(other) >= min_length and (other == mine or other in mine or mine in other)
               for other in codes)


def supplier_card(entry: dict, code: str, catalog: list[dict], identifier: int) -> dict:
    """Заготовка карточки по серии реестра. Цена и наличие — потом, через find_offer."""
    brand = entry["brand"]
    btu = size_of(code, entry.get("size", "btu"))
    return {
        "id": str(identifier),
        "sku": slug(brand) + "-" + slug(code),
        "brandCode": brand_code_for(brand, catalog),
        "brand": brand,
        "series": entry["series"],
        "model": " ".join(part for part in (brand, code, entry.get("suffix", "")) if part),
        "group": entry["group"],
        "type": entry.get("type", "split"),
        "factory": entry.get("factory", ""),
        "color": entry.get("color", "white"),
        "btu": btu,
        "area": AREA_BY_BTU.get(btu, 0),
        "price": 0,
        "stock": "order_7",
        "stockLabel": "Под заказ от 7 дней",
        "descShort": "",
        "cardBenef": "",
        "benefits": [],
        "compressor": "",
        "freon": "",
        "photo": entry["photo"],
    }


def build_supplier_cards(sources: dict, catalog: list[dict], registry: list[dict],
                         start_id: int) -> list[dict]:
    """Карточки для моделей из реестра серий, которых нет на витрине.

    Цена и наличие считаются тем же find_offer, что и у всего каталога: сначала
    реальный остаток, потом самая низкая цена среди поставщиков.
    """
    by_series, by_model = load_content()
    codes = catalog_codes(catalog)
    identifier = start_id
    cards = []
    for entry, code, _row in supplier_offers(sources["trio"][2], sources["oasis"][2], registry):
        if not code or already_listed(codes, code):
            continue
        card = enrich(supplier_card(entry, code, catalog, identifier), by_series, by_model)
        source, module, offer = sync.find_offer(sources, card)
        if offer is not None:
            card["price"] = pricing.compute_price(module.cost_of(offer), source)
            card["stock"], card["stockLabel"] = module.stock_of(offer)
        codes.append(_bare(card["model"], card["brand"]))
        cards.append(card)
        identifier += 1
    return cards


def write_review_csv(path: Path, cards: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["id", "бренд", "серия", "модель", "завод", "группа", "BTU",
                         "площадь", "цена", "наличие", "фото", "описание", "преимущества"])
        for card in cards:
            writer.writerow([card["id"], card["brand"], card["series"], card["model"],
                             card["factory"], card["group"], card["btu"], card["area"],
                             card["price"] or "нет цены", card["stockLabel"], card["photo"],
                             card["descShort"] or "ПУСТО", card["cardBenef"] or "ПУСТО"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Заготовки карточек для новых товаров")
    parser.add_argument("--catalog", default="prod", help="prod или путь к products.js")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="каталог результата")
    args = parser.parse_args(argv)

    catalog = load_catalog(args.catalog)
    cards = build(sources_techno.load(), catalog)
    # Новинки трио и Бриза по реестру серий (series_map.json).
    cards += build_supplier_cards(sync.build_sources(), catalog + cards, load_series_map(),
                                  next_id(catalog + cards))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "new_cards_draft.json").write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_review_csv(out_dir / "new_cards_draft.csv", cards)

    without_price = sum(1 for card in cards if not card["price"])
    filled = sum(1 for card in cards if card["descShort"])
    photos = {card["photo"] for card in cards}
    report = [
        "Заготовок карточек: %d" % len(cards),
        "С описанием: %d  |  ждут наполнения: %d" % (filled, len(cards) - filled),
        "Без цены (в прайсе «уточняйте»): %d" % without_price,
        "Нужно фотографий (по одной на серию): %d" % len(photos),
        "Черновик: " + str(out_dir / "new_cards_draft.json"),
    ]
    sys.stdout.buffer.write(("\n".join(report) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
