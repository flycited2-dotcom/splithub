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
from urllib.parse import quote

import requests

from tools.price_sync import consumables
from tools.price_sync.new_cards import load_series_map, rename_registry_series
from tools.price_sync.sync import DEFAULT_OUT, parse_products_js, render_products_js

#: Поля карточки каталога — ровно те, что читают витрина и валидатор заявок.
REQUIRED_FIELDS = ("id", "sku", "brandCode", "brand", "series", "model", "group", "type",
                   "factory", "color", "btu", "area", "price", "stock", "stockLabel",
                   "descShort", "cardBenef", "benefits", "compressor", "freon", "photo")


def load_new_cards(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def merge(catalog: list[dict], new_cards: list[dict],
          photos: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """Добавить новые карточки к каталогу. Возвращает (итог, отложенные).

    Откладываем позиции без цены («уточняйте» в прайсе), без наполнения, без фото
    (если передан список имеющихся фото) и всё, что столкнулось по id или sku с уже
    существующим товаром.
    """
    taken_ids = {product["id"] for product in catalog}
    taken_skus = {product["sku"] for product in catalog}
    merged, skipped = list(catalog), []
    for card in new_cards:
        if not card.get("price"):
            skipped.append({"card": card, "reason": "нет цены в прайсе"})
            continue
        if not card.get("cardBenef"):
            skipped.append({"card": card, "reason": "нет наполнения"})
            continue
        if photos is not None and card.get("photo") not in photos:
            skipped.append({"card": card, "reason": "нет фото"})
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


def site_photos(names: set[str], base_url: str) -> set[str]:
    """Какие из снимков уже лежат на сайте.

    На сервере сверки папки assets нет, и проверять нужно ровно то, что увидит
    покупатель: нет файла на splithub.ru — карточку не публикуем (битое фото хуже,
    чем карточка на день позже). Сайт не ответил — тоже считаем, что снимка нет.
    """
    found = set()
    for name in names:
        try:
            response = requests.head(base_url.rstrip("/") + "/" + quote(name),
                                     timeout=20, allow_redirects=True)
        except requests.RequestException:
            continue
        if response.status_code == 200:
            found.add(name)
    return found


def build(out_dir: Path, assets: Path | str, registry: dict | None = None):
    catalog = parse_products_js((out_dir / "products.js").read_text(encoding="utf-8"))
    renamed = rename_registry_series(catalog, load_series_map())
    # Текст выложенных расходников трио — из их реестра (rashod_map.json).
    rashod_text = consumables.apply_cards(catalog, registry)
    new_cards = load_new_cards(out_dir / "new_cards_draft.json")
    # Фото «есть», если оно уже висит на боевой карточке или лежит в assets репозитория
    # (оттуда его заливают на сайт вместе с каталогом). На сервере вместо папки —
    # адрес папки снимков на сайте.
    photos = {product.get("photo") for product in catalog}
    on_site = str(assets).startswith(("http://", "https://"))
    wanted = {card.get("photo") for card in new_cards if card.get("photo")} - photos
    if on_site:
        photos |= site_photos(wanted, str(assets))
    elif Path(assets).exists():
        photos |= {path.name for path in Path(assets).iterdir()}
    merged, skipped = merge(catalog, new_cards, photos)
    problems = validate(merged)
    if problems:
        return {"problems": problems, "merged": merged, "skipped": skipped, "written": False}

    target = out_dir / "catalog"
    target.mkdir(parents=True, exist_ok=True)
    (target / "products.js").write_text(render_products_js(merged), encoding="utf-8")
    (target / "products.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing = sorted(wanted - photos) if on_site else missing_photos(merged, catalog, Path(assets))
    return {"problems": [], "merged": merged, "skipped": skipped, "written": True,
            "target": target, "photos": missing,
            "was": len(catalog), "added": len(merged) - len(catalog), "renamed": renamed,
            "rashod_text": rashod_text}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Свести каталог с новыми карточками")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--assets", default=str(Path(__file__).resolve().parents[2] / "assets" / "img" / "products"))
    args = parser.parse_args(argv)

    # Адрес сайта оставляем строкой: Path() схлопнул бы «https://» в «https:/».
    on_site = args.assets.startswith(("http://", "https://"))
    result = build(Path(args.out), args.assets if on_site else Path(args.assets))
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
        "Серия переименована под витрину у карточек: %d" % result["renamed"],
        "Текст расходников обновлён из реестра у карточек: %d" % result["rashod_text"],
        "Нет файлов фотографий: %d" % len(result["photos"]),
        "Файлы: " + str(result["target"]),
    ]
    for item in result["skipped"]:
        lines.append("  отложен %-34s — %s" % (item["card"]["model"][:34], item["reason"]))
    write(("\n".join(lines) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
