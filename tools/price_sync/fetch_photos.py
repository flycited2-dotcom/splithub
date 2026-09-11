#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скачивание исходных фотографий товаров со страниц дилеров.

Для каждой серии, у которой на витрине нет снимка, берём страницы из `_источники`
в `card_content.json` — те же, откуда взяты характеристики, — и вытаскиваем оттуда
фото товара. Ничего не публикует: складывает оригиналы в out/photos/originals/
и пишет отчёт, где видно, что нашлось, а что нет.

    python -m tools.price_sync.fetch_photos
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from tools.price_sync.sync import DEFAULT_OUT

CONTENT_FILE = Path(__file__).resolve().parent / "card_content.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (SplitHub photo fetch)"}
TIMEOUT = 30

#: Слишком маленькое изображение — это иконка или логотип, а не товар.
MIN_SIDE = 300

#: Мусор в имени файла: логотипы, иконки, баннеры, кнопки соцсетей.
JUNK = re.compile(
    r"logo|icon|sprite|banner|placeholder|favicon|social|payment|watermark|"
    r"yandex|karty|rating|reyting|otzyv|review|market|dostavka|garant|sertif|oplata|"
    r"montazh|ustanovka|schema|shema|arrow|button|stars?",
    re.I)


PHOTO_URL = "https://splithub.ru/assets/img/products/"


def photo_exists(name: str, session: requests.Session) -> bool:
    """Есть ли файл на сервере. Ground truth: локальная папка неполная, а каталог
    ссылается и на снимки, которые лежат только на проде."""
    try:
        return session.head(PHOTO_URL + name, headers=HEADERS, timeout=15).status_code == 200
    except Exception:
        return False


_CODE = re.compile(r"[A-Z0-9]{2,}(?:[-/][A-Z0-9]+)*", re.I)


def model_codes(model: str, brand: str) -> set[str]:
    """Куски артикула, по которым фото товара узнаётся в имени файла: «DU-09» → du09, du-09."""
    bare = model.upper().replace(brand.upper(), "").strip()
    codes = set()
    for chunk in _CODE.findall(bare):
        flat = re.sub(r"[^A-Z0-9]", "", chunk)
        if len(flat) >= 4:
            codes.add(flat.lower())
            codes.add(chunk.lower())
    return codes


def needed_photos(catalog: list[dict], session: requests.Session) -> dict[str, dict]:
    """{имя файла: {бренд, серии, модели, сколько позиций}} — чего не хватает витрине."""
    known = {name for name in {p.get("photo") for p in catalog} if name and photo_exists(name, session)}
    need: dict[str, dict] = {}
    for product in catalog:
        photo = product.get("photo")
        if not photo or photo in known:
            continue
        entry = need.setdefault(photo, {"brand": product["brand"], "series": set(),
                                        "codes": set(), "count": 0})
        entry["series"].add(product["series"])
        entry["codes"] |= model_codes(product["model"], product["brand"])
        entry["count"] += 1
    return need


def sources_for(brand: str, series: set[str], content: dict) -> list[str]:
    links: list[str] = []
    for name in series:
        for link in content.get(brand + "|" + name, {}).get("_источники", []):
            if link.startswith("http") and link not in links:
                links.append(link)
    return links


def _size_hint(tag) -> int:
    """Площадь картинки по атрибутам, если они есть. 0 — размер неизвестен."""
    try:
        return int(tag.get("width", 0)) * int(tag.get("height", 0))
    except (TypeError, ValueError):
        return 0


def image_candidates(page_url: str, html: str, codes: set[str], brand: str) -> list[str]:
    """Ссылки на фото товара, самые вероятные — первыми.

    Размер картинки плохой признак: самым большим на странице дилера запросто
    окажется баннер «Яндекс.Карты — отличный магазин». Поэтому сначала смотрим,
    упоминается ли в имени файла или alt артикул товара, потом бренд, и только
    потом размер.
    """
    soup = BeautifulSoup(html, "lxml")
    scored: list[tuple[int, str]] = []

    def score(url: str, alt: str) -> int:
        haystack = (url + " " + alt).lower()
        if JUNK.search(haystack):
            return -1
        points = _size_hint_from_url(url)
        if any(code in haystack for code in codes):
            points += 1000
        if brand.lower() in haystack:
            points += 200
        return points

    meta = soup.find("meta", property="og:image")
    if meta and meta.get("content"):
        url = urljoin(page_url, meta["content"])
        value = score(url, "og:image")
        if value >= 0:
            scored.append((value + 300, url))       # og:image почти всегда товар

    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src") or tag.get("data-original")
        if not src or src.startswith("data:"):
            continue
        url = urljoin(page_url, src)
        value = score(url, tag.get("alt", ""))
        if value >= 0:
            scored.append((value + _size_hint(tag) // 1000, url))

    scored.sort(key=lambda pair: -pair[0])
    ordered: list[str] = []
    for _, url in scored:
        if url not in ordered:
            ordered.append(url)
    return ordered


def _size_hint_from_url(url: str) -> int:
    """Иногда размер зашит в путь: /600x600/, _1200.jpg."""
    found = re.search(r"(\d{3,4})[xX](\d{3,4})", url)
    return (int(found.group(1)) * int(found.group(2))) // 1000 if found else 0


def download(url: str, session: requests.Session) -> bytes | None:
    """Скачать картинку, если она достаточно большая и это вообще картинка."""
    try:
        response = session.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
    except Exception:
        return None
    if "image" not in response.headers.get("Content-Type", ""):
        return None
    data = response.content
    if len(data) < 15000:          # мельче — заведомо иконка
        return None
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            if min(img.size) < MIN_SIDE:
                return None
    except ImportError:
        pass                        # без Pillow довольствуемся проверкой по размеру файла
    except Exception:
        return None
    return data


def run(out_dir: Path) -> dict:
    content = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    catalog = json.loads((out_dir / "catalog" / "products.json").read_text(encoding="utf-8"))
    session = requests.Session()
    need = needed_photos(catalog, session)

    target = out_dir / "photos" / "originals"
    target.mkdir(parents=True, exist_ok=True)
    report = []

    for photo, info in sorted(need.items()):
        links = sources_for(info["brand"], info["series"], content)
        saved, source = None, ""
        for page in links:
            try:
                page_html = session.get(page, headers=HEADERS, timeout=TIMEOUT).text
            except Exception:
                continue
            for candidate in image_candidates(page, page_html, info["codes"], info["brand"])[:6]:
                data = download(candidate, session)
                if data:
                    saved, source = data, candidate
                    break
            if saved:
                break
        status = "скачано"
        if saved:
            suffix = Path(source.split("?")[0]).suffix.lower() or ".jpg"
            if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
                suffix = ".jpg"
            (target / (Path(photo).stem + suffix)).write_bytes(saved)
        else:
            status = "НЕ НАЙДЕНО" if links else "нет страницы-источника"
        report.append({"photo": photo, "brand": info["brand"], "count": info["count"],
                       "series": " / ".join(sorted(info["series"])), "status": status,
                       "source": source, "pages": " ".join(links[:2])})

    with (out_dir / "photos" / "report.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter=";",
                                fieldnames=["photo", "brand", "series", "count", "status", "source", "pages"])
        writer.writeheader()
        writer.writerows(report)
    return {"need": len(need), "ok": sum(1 for r in report if r["status"] == "скачано"),
            "report": report, "dir": target}


if __name__ == "__main__":
    result = run(DEFAULT_OUT)
    write = sys.stdout.buffer.write
    write(("Нужно фото: %d, скачано: %d\n" % (result["need"], result["ok"])).encode("utf-8"))
    for row in result["report"]:
        write(("  %-46s %-10s %s\n" % (row["photo"][:46], row["status"], row["brand"])).encode("utf-8"))
    write(("Папка: %s\n" % result["dir"]).encode("utf-8"))
