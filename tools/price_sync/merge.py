# -*- coding: utf-8 -*-
"""Сведение боевого каталога с новыми карточками — то, что поедет на сайт.

Читает результат `sync` (боевые позиции с пересчитанными ценами) и черновик
`new_cards` (товары, которых на витрине ещё нет), склеивает и ПРОВЕРЯЕТ результат.
Проверка здесь не формальность: битый products.json ломает приём заявок на сайте,
поэтому при любой ошибке файлы не пишутся вовсе.

    python -m tools.price_sync.merge        # -> out/catalog/products.js + products.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.price_sync.sync import DEFAULT_OUT, parse_products_js, render_products_js

#: Поля карточки каталога — ровно те, что читают витрина и валидатор заявок.
REQUIRED_FIELDS = ("id", "sku", "brandCode", "brand", "series", "model", "group", "type",
                   "factory", "color", "btu", "area", "price", "stock", "stockLabel",
                   "descShort", "cardBenef", "benefits", "compressor", "freon", "photo")


def load_new_cards(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def merge(catalog: list[dict], new_cards: list[dict]) -> tuple[list[dict], list[dict]]:
    """Добавить новые карточки к каталогу. Возвращает (итог, отложенные).

    Откладываем позиции без цены («уточняйте» в прайсе) и всё, что столкнулось по
    id или sku с уже существующим товаром.
    """
    taken_ids = {product["id"] for product in catalog}
    taken_skus = {product["sku"] for product in catalog}
    merged, skipped = list(catalog), []
    for card in new_cards:
        if not card.get("price"):
            skipped.append({"card": card, "reason": "нет цены в прайсе"})
            continue
        if card["id"] in taken_ids:
            skipped.append({"card": card, "reason": "id уже занят"})
            continue
        if card["sku"] in taken_skus:
            skipped.append({"card": card, "reason": "sku уже занят"})
            continue
        taken_ids.add(card["id"])
        taken_skus.add(card["sku"])
        merged.append(card)
    return merged, skipped


def validate(catalog: list[dict]) -> list[str]:
    """Список проблем каталога. Пустой список — можно публиковать."""
    problems = []
    ids = [product.get("id") for product in catalog]
    skus = [product.get("sku") for product in catalog]
    if len(set(ids)) != len(ids):
        problems.append("повторяются id: " + ", ".join(sorted(
            {str(i) for i in ids if ids.count(i) > 1})))
    if len(set(skus)) != len(skus):
        problems.append("повторяются sku: " + ", ".join(sorted(
            {str(s) for s in skus if skus.count(s) > 1})))
    for product in catalog:
        missing = [field for field in REQUIRED_FIELDS if field not in product]
        if missing:
            problems.append("%s: нет полей %s" % (product.get("model", "?"), ", ".join(missing)))
        if not isinstance(product.get("price"), int) or product.get("price", 0) <= 0:
            problems.append("%s: некорректная цена %r" % (product.get("model", "?"), product.get("price")))
        if not isinstance(product.get("benefits"), list):
            problems.append("%s: benefits должен быть списком" % product.get("model", "?"))
        if not product.get("model") or not product.get("brand"):
            problems.append("%s: пустой бренд или модель" % product.get("id", "?"))
    return problems


def missing_photos(catalog: list[dict], base: list[dict], assets: Path) -> list[str]:
    """Фотографии, которых ещё нет — их надо снять.

    Снимки боевых карточек лежат на сервере, а в репозитории их почти нет, поэтому
    «уже есть» — это те, на которые ссылается исходный каталог, плюс локальные файлы.
    """
    known = {product.get("photo") for product in base}
    return sorted({product["photo"] for product in catalog
                   if product.get("photo")
                   and product["photo"] not in known
                   and not (assets / product["photo"]).exists()})


def build(out_dir: Path, assets: Path):
    catalog = parse_products_js((out_dir / "products.js").read_text(encoding="utf-8"))
    new_cards = load_new_cards(out_dir / "new_cards_draft.json")
    merged, skipped = merge(catalog, new_cards)
    problems = validate(merged)
    if problems:
        return {"problems": problems, "merged": merged, "skipped": skipped, "written": False}

    target = out_dir / "catalog"
    target.mkdir(parents=True, exist_ok=True)
    (target / "products.js").write_text(render_products_js(merged), encoding="utf-8")
    (target / "products.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"problems": [], "merged": merged, "skipped": skipped, "written": True,
            "target": target, "photos": missing_photos(merged, catalog, assets),
            "was": len(catalog), "added": len(merged) - len(catalog)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Свести каталог с новыми карточками")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--assets", default=str(Path(__file__).resolve().parents[2] / "assets" / "img" / "products"))
    args = parser.parse_args(argv)

    result = build(Path(args.out), Path(args.assets))
    write = sys.stdout.buffer.write
    if result["problems"]:
        write("КАТАЛОГ НЕ СОБРАН — сначала нужно исправить:\n".encode("utf-8"))
        for problem in result["problems"][:20]:
            write(("  • " + problem + "\n").encode("utf-8"))
        return 1

    lines = [
        "Каталог собран: %d позиций (было %d, добавлено %d)" % (
            len(result["merged"]), result["was"], result["added"]),
        "Отложено: %d" % len(result["skipped"]),
        "Нет файлов фотографий: %d" % len(result["photos"]),
        "Файлы: " + str(result["target"]),
    ]
    for item in result["skipped"]:
        lines.append("  отложен %-34s — %s" % (item["card"]["model"][:34], item["reason"]))
    write(("\n".join(lines) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
