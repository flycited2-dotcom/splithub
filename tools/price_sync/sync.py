# -*- coding: utf-8 -*-
"""Пересчёт цен каталога СплитХаб по прайсам поставщиков.

Ничего никуда не заливает: читает БОЕВОЙ каталог, считает новые цены и наличие,
пишет результат в out/ и дифф-отчёт. Деплой — отдельным шагом, руками владельца.

    python -m tools.price_sync.sync                 # прод-каталог -> out/
    python -m tools.price_sync.sync --catalog products.js
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

from tools.price_sync import (consumables, matching, pricing, sources_jac,
                              sources_oasis, sources_techno, sources_trio)

PROD_CATALOG_URL = "https://splithub.ru/products.js"
SITE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = Path(__file__).resolve().parent / "out"

#: Бренды, которые владелец держит на витрине, но которых нет в боевом каталоге.
#: Карточки берём из products.js репозитория, цену и наличие — из JAC.
RESTORE_BRANDS = ("THAICON", "MITSUBISHI HEAVY IND")

#: Порядок опроса источников: первый, кто узнал модель, задаёт цену.
SOURCE_ORDER = ("techno", "trio", "jac", "oasis")


def parse_products_js(text: str) -> list[dict]:
    return json.loads(text[text.index("["):text.rindex("]") + 1])


def load_catalog(where: str) -> list[dict]:
    if where == "prod":
        response = requests.get(PROD_CATALOG_URL, timeout=40)
        response.raise_for_status()
        return parse_products_js(response.text)
    return parse_products_js(Path(where).read_text(encoding="utf-8"))


def render_products_js(products: list[dict]) -> str:
    lines = ["var PRODUCTS = ["]
    for index, product in enumerate(products):
        comma = "," if index < len(products) - 1 else ""
        lines.append("  " + json.dumps(product, ensure_ascii=False) + comma)
    lines.append("];")
    return "\n".join(lines) + "\n"


def build_sources(jac_path=None, oasis_path=None):
    """Индексы всех доступных прайсов: {источник: (индекс, модуль, строки)}.

    Выгрузки SplitHome может не быть — тогда источник просто пустой.
    """
    techno_rows = sources_techno.load()
    trio_rows = sources_trio.fetch()
    jac_rows = sources_jac.load(jac_path)
    oasis_rows = sources_oasis.load(oasis_path or DEFAULT_OUT / "oasis_stock.csv",
                                    DEFAULT_OUT / "breez_base.json")
    return {
        "techno": (matching.build_text_index(techno_rows, sources_techno.model_of), sources_techno, techno_rows),
        "trio": (matching.build_index(trio_rows, lambda o: o["model"]), sources_trio, trio_rows),
        "jac": (matching.build_index(jac_rows, sources_jac.model_of), sources_jac, jac_rows),
        "oasis": (matching.build_text_index(oasis_rows, sources_oasis.model_of), sources_oasis, oasis_rows),
    }


#: Группы каталога, которые считаются расходниками: у трио они идут с наценкой 10%.
RASHOD_GROUPS = ("rashod", "truba")


#: Мелочёвка с наценкой 100%. Владелец назвал поимённо: дюбели, болты и гайки
#: с прессшайбой. Кронштейны, глухари, шайбы и обычные гайки сюда НЕ входят —
#: они остаются на общих 10% для расходников.
HIGH_MARKUP_PARTS = ("дюбел", "болт", "пресшайб")


def is_high_markup(product: dict) -> bool:
    name = (product.get("brand", "") + " " + product.get("model", "")).lower()
    return any(part in name for part in HIGH_MARKUP_PARTS)


def price_source(name: str, product: dict, offer=None) -> str:
    """У трио техника идёт +5%, расходники +10%, а дюбели/болты/гайки-прессшайба — +100%."""
    if name == "trio" and product.get("group") in RASHOD_GROUPS:
        return "trio_krepezh" if is_high_markup(product) else "trio_rashod"
    return name


def _offer_in(sources, name, product):
    """Найти позицию у одного поставщика — способом, который подходит его прайсу."""
    index, _, _ = sources[name]
    if name == "oasis":
        # Названия описательные («…серии ELYSIUM Inverter ELB-I07PN») — ищем наш код в них.
        # Код бывает в двух строках (та же модель в двух сериях Бриза) — берём ту, что на складе.
        return matching.lookup_within(index, product["model"], product["brand"],
                                      prefer=sources_oasis.breez_in_stock_first)
    if name == "techno":
        # Коды бывают и длиннее наших («RK-07SCDG/E»), и короче («ICE20») — ищем в обе стороны.
        offer = matching.lookup_either(index, product["model"], product["brand"])
        return offer if offer is not None and same_kind(offer.get("series", ""), product) else None
    return matching.lookup(index, product["model"], product["brand"])


def same_kind(series: str, product: dict) -> bool:
    """Инвертор не подменяет on/off и наоборот.

    Короткий код Техносистемса «ICE20» — это инвертор ICE20AVQS1R-2, но он входит и
    в код on/off-модели ICE20AVQ1-1. Серия прайса («ICE (-15°C inverter)») говорит,
    что это за товар; группа карточки — что продаём мы. Полупром (pac_*) не проверяем:
    по группе там не понять, инвертор это или нет.
    """
    text = series.lower()
    offer_inverter = "inverter" in text or "инвертор" in text
    offer_onoff = "on/off" in text or "on-off" in text or "onoff" in text
    group = product.get("group")
    if group == "onoff" and offer_inverter:
        return False
    if group == "inv" and offer_onoff:
        return False
    return True


#: Реальный остаток у поставщика: чем быстрее привезём, тем выше. Всё, чего нет на
#: складе («под заказ», «ожидается», «нет»), — один последний уровень.
STOCK_RANK = {"in_stock": 0, "days_1_2": 1, "days_3_5": 2, "days_7": 3}
NO_STOCK_RANK = 4


def find_offer(sources, product):
    """Из всех поставщиков, у кого есть позиция, побеждает самая низкая цена витрины —
    среди тех, у кого она есть на складе.

    Правило владельца: «если дешевле у трио — берём трио, если у Техносистемса —
    берём его». Сравниваем итоговую цену, а не закупку: наценки у поставщиков разные.
    Но дешёвое «нет» или «под заказ» не перебивает «в наличии» у другого поставщика:
    иначе DAICHI ICE25 шла «Нет в наличии», хотя у Техносистемса была на складе.
    Если на складе нет ни у кого — побеждает просто самая низкая цена, и «под заказ»
    не перебивает «нет» у трио (владелец: у трио «нет» — ставим «нет»).
    """
    best = None
    for name in SOURCE_ORDER:
        offer = _offer_in(sources, name, product)
        if offer is None:
            continue
        module = sources[name][1]
        cost = module.cost_of(offer)
        if cost <= 0:
            continue
        source = price_source(name, product, offer)
        price = pricing.compute_price(cost, source)
        # Модуль может знать об остатке больше, чем говорит подпись на витрине
        # (Бриз: «Под заказ 7 дней», но товар лежит на складе в Москве).
        rank_of = getattr(module, "stock_rank", None)
        level = rank_of(offer) if rank_of else STOCK_RANK.get(module.stock_of(offer)[0], NO_STOCK_RANK)
        rank = (level, price)
        if best is None or rank < best[0]:
            best = (rank, source, module, offer)
    if best is not None:
        return best[1], best[2], best[3]
    # Расходники моделью не совпадают — ищем по характеристикам товара.
    offer = consumables.match(product, sources["trio"][2])
    if offer is not None:
        return price_source("trio", product, offer), sources_trio, offer
    return None, None, None


#: Модели, которые производитель сменил новой ревизией: {старый код карточки: новый}.
#: Старую не продаёт уже никто, а точное сравнение кодов цепляло её залежалую строку
#: у Daichi (0 шт., цена двухлетней давности). Карточка та же — меняется только код.
REVISIONS_FILE = Path(__file__).resolve().parent / "model_revisions.json"


def load_revisions(path: Path = REVISIONS_FILE) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {old: new for old, new in data.items() if not old.startswith("_")}


def apply_revisions(catalog: list[dict], revisions: dict[str, str] | None = None) -> list[dict]:
    """Перевести карточки со снятых моделей на новые. Повторный вызов ничего не меняет."""
    revisions = load_revisions() if revisions is None else revisions
    for product in catalog:
        new = revisions.get(product.get("model", ""))
        if new:
            product["model"] = new
    return catalog


def restore_missing(catalog: list[dict]) -> list[dict]:
    """Вернуть на витрину бренды из RESTORE_BRANDS, если их нет в боевом каталоге."""
    present = {p["id"] for p in catalog}
    repo_js = (SITE_ROOT / "products.js").read_text(encoding="utf-8")
    repo_catalog = parse_products_js(repo_js)
    return [p for p in repo_catalog if p["brand"] in RESTORE_BRANDS and p["id"] not in present]


def supplier_model(source: str, offer: dict) -> str:
    if source.startswith("trio") or source == "techno":
        return offer["model"]
    if source == "oasis":
        return sources_oasis.model_of(offer)
    return sources_jac.model_of(offer)


def sync(catalog_source: str, out_dir: Path, jac_path=None, restore: bool = True, oasis_path=None):
    catalog = apply_revisions(load_catalog(catalog_source))
    restored = restore_missing(catalog) if restore else []
    catalog = catalog + restored
    restored_ids = {p["id"] for p in restored}

    sources = build_sources(jac_path, oasis_path)
    updated, changes, untouched = [], [], []

    for product in catalog:
        fresh = dict(product)
        name, module, offer = find_offer(sources, product)
        cost = module.cost_of(offer) if offer is not None else 0
        if offer is None or cost <= 0:
            untouched.append(product)
            updated.append(fresh)
            continue
        fresh["price"] = pricing.compute_price(cost, name)
        fresh["stock"], fresh["stockLabel"] = module.stock_of(offer)
        updated.append(fresh)
        changes.append({
            "id": product["id"], "brand": product["brand"], "model": product["model"],
            "source": name, "supplier_model": supplier_model(name, offer),
            "cost": cost, "markup_pct": int(pricing.MARKUP[name] * 100),
            "old_price": product["price"], "new_price": fresh["price"],
            "delta": fresh["price"] - product["price"],
            "old_stock": product["stock"], "new_stock": fresh["stock"],
            "restored": product["id"] in restored_ids,
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "products.js").write_text(render_products_js(updated), encoding="utf-8")
    (out_dir / "products.json").write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_diff(out_dir / "price_diff.csv", changes, untouched)
    pending = [p for p in untouched if p.get("group") in RASHOD_GROUPS]
    write_candidates(out_dir / "rashod_candidates.csv", pending, sources["trio"][2])
    return {
        "pending_rashod": len(pending),
        "catalog": len(catalog), "restored": len(restored), "priced": len(changes),
        "untouched": len(untouched), "sources": {k: len(v[2]) for k, v in sources.items()},
        "changes": changes, "out_dir": out_dir,
    }


def write_diff(path: Path, changes: list[dict], untouched: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["id", "бренд", "модель", "источник", "модель поставщика", "закупка",
                         "наценка %", "цена было", "цена стало", "дельта", "наличие было",
                         "наличие стало", "возвращён на витрину"])
        for row in sorted(changes, key=lambda c: (c["brand"], c["model"])):
            writer.writerow([row["id"], row["brand"], row["model"], row["source"],
                             row["supplier_model"], row["cost"], row["markup_pct"],
                             row["old_price"], row["new_price"], row["delta"],
                             row["old_stock"], row["new_stock"],
                             "да" if row["restored"] else ""])
        writer.writerow([])
        writer.writerow(["--- НЕТ В ПРАЙСАХ ПОСТАВЩИКОВ, ЦЕНА НЕ ТРОНУТА ---"])
        writer.writerow(["id", "бренд", "модель", "", "", "", "", "цена"])
        for product in sorted(untouched, key=lambda p: (p["brand"], p["model"])):
            writer.writerow([product["id"], product["brand"], product["model"],
                             "", "", "", "", product["price"]])


def write_candidates(path: Path, pending: list[dict], trio_rows: list[dict]) -> None:
    """Расходники, которые сопоставились неоднозначно — на ручное подтверждение."""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["id", "наша карточка", "наша цена", "кандидат у трио",
                         "цена трио", "наличие трио", "похожесть",
                         "ВАША ЗАКУПКА (заполнить)", "комментарий"])
        for product in sorted(pending, key=lambda p: (p["brand"], p["model"])):
            found = consumables.candidates(product, trio_rows)
            if not found:
                writer.writerow([product["id"], product["model"], product["price"],
                                 "— нет похожих —", "", "", "", "", ""])
                continue
            for score, row in found:
                writer.writerow([product["id"], product["model"], product["price"],
                                 row["model"], row["dealer"], row["availability"],
                                 round(score, 2), "", ""])
            writer.writerow([])


def summary(result: dict) -> str:
    changes = result["changes"]
    moved = [c for c in changes if c["delta"]]
    up = sum(1 for c in moved if c["delta"] > 0)
    down = sum(1 for c in moved if c["delta"] < 0)
    lines = [
        "Сверка цен " + datetime.now().strftime("%d.%m.%Y %H:%M"),
        "Прайсы: Техносистемс %d, трио %d, JAC %d, SplitHome %d строк" % (
            result["sources"]["techno"], result["sources"]["trio"],
            result["sources"]["jac"], result["sources"]["oasis"]),
        "Каталог: %d позиций (возвращено на витрину: %d)" % (result["catalog"], result["restored"]),
        "Цена пересчитана: %d  |  без источника, не тронуты: %d" % (result["priced"], result["untouched"]),
        "Изменилось: %d (вверх %d, вниз %d)" % (len(moved), up, down),
        "Расходники на ручное подтверждение: %d (rashod_candidates.csv)" % result["pending_rashod"],
        "Результат: " + str(result["out_dir"]),
    ]
    biggest = sorted(moved, key=lambda c: -abs(c["delta"]))[:10]
    if biggest:
        lines.append("")
        lines.append("Крупнейшие изменения:")
        for row in biggest:
            lines.append("  %-9s %-34s %7d -> %7d  (%+d)" % (
                row["brand"][:9], row["model"][:34], row["old_price"], row["new_price"], row["delta"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Пересчёт цен каталога по прайсам поставщиков")
    parser.add_argument("--catalog", default="prod",
                        help="prod (скачать с splithub.ru) или путь к products.js")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="каталог результата")
    parser.add_argument("--jac", default=None, help="путь к jac_stock_latest.json")
    parser.add_argument("--oasis", default=None, help="путь к выгрузке oasis_stock.csv")
    parser.add_argument("--no-restore", action="store_true",
                        help="не возвращать на витрину THAICON и Mitsubishi Heavy")
    args = parser.parse_args(argv)
    result = sync(args.catalog, Path(args.out), args.jac,
                  restore=not args.no_restore, oasis_path=args.oasis)
    sys.stdout.buffer.write((summary(result) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
