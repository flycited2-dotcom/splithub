#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Фотографии товаров с сайта производителя ALASKA Group.

ALASKA Group — владелец брендов Eurohoff, Denko, Dahatsu, Ynovik и Yuetu, то есть
почти всего, что мы добавили от Техносистемса. Их API отдаёт весь каталог с фото
1536×1024 — это чистые студийные снимки без чужих водяных знаков и баннеров,
в отличие от страниц дилеров, где в первый заход скачался баннер «Яндекс.Карты».

    python -m tools.price_sync.photos_alaska            # скачать и подставить
    python -m tools.price_sync.photos_alaska --dry-run  # только показать совпадения
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import requests
from PIL import Image

from tools.price_sync import matching
from tools.price_sync.sync import DEFAULT_OUT

API_URL = "https://api.alaska-air.ru/products/"
SITE_ROOT = Path(__file__).resolve().parents[2]
ASSETS = SITE_ROOT / "assets" / "img" / "products"
SITE_PHOTOS = "https://splithub.ru/assets/img/products/"

#: Бренды, которые выпускает ALASKA Group — только их и ищем в этом каталоге.
BRANDS = ("EUROHOFF", "DENKO", "DAHATSU", "YNOVIK", "YUETU")

MAX_SIDE = 1000


def load_api(cache: Path) -> list[dict]:
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    data = requests.get(API_URL, timeout=120).json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


_UNITS = re.compile(r"\s*IN\s*/\s*OUT\s*$", re.I)


def _without_units(model: str) -> str:
    return _UNITS.sub("", model).strip()


def match_photos(catalog: list[dict], api: list[dict], skip: set[str]) -> dict[str, dict]:
    """{имя файла каталога: товар из API} — по одному снимку на серию.

    Бренд обязан совпасть: у ALASKA один и тот же аппарат продаётся под разными
    марками, и мультисплит DENKO бодро находится как «Dahatsu DHMULT» — на карточке
    оказался бы чужой логотип.
    """
    index = matching.build_text_index([p for p in api if p.get("image")],
                                      lambda product: product.get("name", ""))
    chosen: dict[str, dict] = {}
    for product in catalog:
        if product["brand"] not in BRANDS:
            continue
        photo = product.get("photo")
        if not photo or photo in chosen or photo in skip:
            continue
        # «YNA-09IN/OUT» у нас против «YNA-09» у завода: хвост про внутренний
        # и наружный блок мешает совпадению, поэтому пробуем и без него.
        found = (matching.lookup_either(index, product["model"], product["brand"])
                 or matching.lookup_either(index, _without_units(product["model"]), product["brand"]))
        if found and found.get("name", "").strip().upper().startswith(product["brand"]):
            chosen[photo] = {"api": found, "model": product["model"],
                             "brand": product["brand"], "series": product["series"]}
    return chosen


def photos_on_site(names: set[str]) -> set[str]:
    """Снимки, которые уже стоят на сайте, — их не трогаем."""
    session = requests.Session()
    present = set()
    for name in names:
        try:
            if session.head(SITE_PHOTOS + name, timeout=15).status_code == 200:
                present.add(name)
        except Exception:
            pass
    return present


def save_webp(data: bytes, target: Path) -> None:
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        image.save(target, "WEBP", quality=88, method=6)


def run(dry_run: bool) -> int:
    catalog = json.loads((DEFAULT_OUT / "catalog" / "products.json").read_text(encoding="utf-8"))
    api = load_api(DEFAULT_OUT / "photos" / "alaska_api.json")
    on_site = photos_on_site({p.get("photo") for p in catalog if p.get("photo")})
    chosen = match_photos(catalog, api, on_site)

    write = sys.stdout.buffer.write
    write(("Товаров в каталоге ALASKA: %d, сопоставлено снимков: %d\n"
           % (len(api), len(chosen))).encode("utf-8"))
    for photo, info in sorted(chosen.items()):
        write(("  %-46s <- %s\n" % (photo[:46], info["api"]["name"])).encode("utf-8"))
    if dry_run:
        return 0

    ASSETS.mkdir(parents=True, exist_ok=True)
    saved = []
    for photo, info in sorted(chosen.items()):
        try:
            response = requests.get(info["api"]["image"], timeout=60)
            response.raise_for_status()
            save_webp(response.content, ASSETS / photo)
            saved.append(photo)
        except Exception as error:
            write(("  ошибка на %s: %s\n" % (photo, error)).encode("utf-8"))
    write(("\nСохранено: %d файлов в %s\n" % (len(saved), ASSETS)).encode("utf-8"))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Фото товаров от производителя ALASKA")
    parser.add_argument("--dry-run", action="store_true")
    return run(parser.parse_args(argv).dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
