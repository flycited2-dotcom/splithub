#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Фото серии в стиле витрины СплитХаба из ОРИГИНАЛЬНЫХ снимков производителя.

Стиль витрины: квадрат 1024×1024, графитово-серый фон со светлым центром, сверху
внутренний блок, снизу слева пульт, справа наружный блок. Здесь ничего не рисуется
заново: товар берётся с фото производителя как есть, меняется только фон — так
модель на карточке гарантированно та самая, без «додуманных» нейросетью деталей.

Исходники бывают двух видов:
  * отдельные PNG с прозрачным фоном (Бриз: блоки и пульт по отдельности) —
    раскладываем их по схеме витрины;
  * готовый «комплект» на белом фоне (Daichi: блоки и пульт уже расставлены) —
    вырезаем белый фон и ставим комплект на наш.

    python -m tools.price_sync.compose_photos            # все серии из photo_sources.json
    python -m tools.price_sync.compose_photos --only funai-kadzoku-inv.webp
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from tools.price_sync.sync import DEFAULT_OUT

SIZE = 1024
#: Цвета фона сняты с карточек витрины (kentatsu-haruki, midea-breezeless).
CENTER = (150, 150, 154)
EDGE = (38, 38, 42)
HEADERS = {"User-Agent": "Mozilla/5.0 (SplitHub photo composer)"}

SOURCES_FILE = Path(__file__).resolve().parent / "photo_sources.json"
TARGET = DEFAULT_OUT / "photos" / "composed"


def background() -> Image.Image:
    """Радиальный градиент: светлый центр чуть выше середины, тёмные края."""
    small = 256
    grad = Image.new("RGB", (small, small))
    pixels = grad.load()
    cx, cy = small * 0.5, small * 0.44
    radius = (cx ** 2 + cy ** 2) ** 0.5
    for y in range(small):
        for x in range(small):
            t = min(1.0, (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / radius) ** 1.35
            pixels[x, y] = tuple(round(c + (e - c) * t) for c, e in zip(CENTER, EDGE))
    return grad.resize((SIZE, SIZE), Image.BICUBIC).convert("RGBA")


def load(url: str, attempts: int = 3) -> Image.Image:
    """Скачать кадр. Сервер фото Бриза иногда отвечает с задержкой — пробуем ещё раз."""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=40)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert("RGBA")
        except requests.RequestException:
            if attempt == attempts:
                raise


def load_part(url: str) -> Image.Image:
    """Отдельный кадр блока или пульта. Бывает и PNG с прозрачностью, и JPG на белом —
    белый фон вырезаем, иначе на сером фоне останется белый прямоугольник."""
    image = load(url)
    return trim(image if is_transparent(image) else cut_white(image))


def is_transparent(image: Image.Image) -> bool:
    alpha = image.getchannel("A")
    corners = [alpha.getpixel((x, y)) for x, y in ((0, 0), (image.width - 1, 0),
                                                   (0, image.height - 1),
                                                   (image.width - 1, image.height - 1))]
    return max(corners) < 16


def cut_white(image: Image.Image, threshold: int = 246) -> Image.Image:
    """Убрать белый фон, связанный с краем кадра. Белый корпус блока не трогаем:
    он отделён от фона контуром и тенью, заливка от края до него не доходит."""
    rgb = image.convert("RGB")
    gray = rgb.convert("L")
    near_white = gray.point(lambda v: 255 if v >= threshold else 0)
    # Контуры — преграда для заливки: у белого корпуса на белом фоне край виден только
    # как тонкая линия, и без этой преграды заливка «съедает» кусок блока.
    edges = gray.filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 18 else 0)
    edges = edges.filter(ImageFilter.MaxFilter(3))
    # Фильтр контуров рисует линию и по рамке кадра — её убираем, иначе заливке неоткуда стартовать.
    frame = Image.new("L", edges.size, 0)
    frame.paste(255, (4, 4, edges.width - 4, edges.height - 4))
    edges = ImageChops.multiply(edges, frame)
    near_white = ImageChops.subtract(near_white, edges)
    # Заливаем от краёв: фон — это белое, связанное с рамкой кадра.
    fill = near_white.copy()
    marker = 128
    width, height = fill.size
    for x in range(0, width, 8):
        for y in (0, height - 1):
            if fill.getpixel((x, y)) == 255:
                ImageDraw.floodfill(fill, (x, y), marker)
    for y in range(0, height, 8):
        for x in (0, width - 1):
            if fill.getpixel((x, y)) == 255:
                ImageDraw.floodfill(fill, (x, y), marker)
    background_mask = fill.point(lambda v: 255 if v == marker else 0)
    # Закрыть «проколы» в контуре и смягчить край, чтобы не было белой каймы.
    alpha = ImageChops.invert(background_mask)
    alpha = alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(5))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))
    result = image.copy()
    result.putalpha(alpha)
    return result


def trim(image: Image.Image) -> Image.Image:
    box = image.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    return image.crop(box) if box else image


def shadow(canvas: Image.Image, part: Image.Image, x: int, y: int, strength: int = 110) -> None:
    """Мягкая тень под предметом — как на карточках витрины."""
    alpha = part.getchannel("A").point(lambda v: min(255, v))
    blob = Image.new("RGBA", part.size, (0, 0, 0, 0))
    blob.putalpha(alpha.point(lambda v: v * strength // 255))
    blob = blob.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(blob, (x + 10, y + 16))


def fit(part: Image.Image, width: int, height: int, max_scale: float = 1.6) -> Image.Image:
    """Вписать в габарит. Маленький исходник сильнее чем в 1,6 раза не растягиваем — мылит."""
    scale = min(width / part.width, height / part.height, max_scale)
    return part.resize((max(1, round(part.width * scale)), max(1, round(part.height * scale))),
                       Image.LANCZOS)


def classify(parts: list[Image.Image]) -> dict[str, Image.Image]:
    """Внутренний блок — самый вытянутый, пульт — самый высокий, наружный — ближе к квадрату."""
    trimmed = [trim(p) for p in parts]
    ratio = lambda p: p.width / p.height
    indoor = max(trimmed, key=ratio)
    remote = min(trimmed, key=ratio)
    rest = [p for p in trimmed if p is not indoor and p is not remote and 1.0 <= ratio(p) <= 1.9]
    outdoor = max(rest, key=lambda p: p.width * p.height) if rest else None
    return {"indoor": indoor, "remote": remote if ratio(remote) < 0.7 else None, "outdoor": outdoor}


def compose_parts(indoor: Image.Image, outdoor: Image.Image | None,
                  remote: Image.Image | None) -> Image.Image:
    """Внутренний блок, пульт и наружный блок — все три обязательны: это общий стиль
    витрины (владелец 24.09.2026). Нет своего снимка — в photo_sources.json ставится
    кадр того же бренда и типа (поле _outdoor_from / _donor), без него не собираем."""
    if outdoor is None or remote is None:
        raise ValueError("нужны все три кадра: внутренний блок, пульт и наружный блок")
    if indoor.width / indoor.height < 0.7:
        return compose_column(indoor, outdoor, remote)
    canvas = background()
    top = fit(indoor, 840, 300)
    tx, ty = (SIZE - top.width) // 2, 70
    shadow(canvas, top, tx, ty, 90)
    canvas.alpha_composite(top, (tx, ty))
    floor = 930
    out = fit(outdoor, 600, 470)
    ox, oy = SIZE - 70 - out.width, floor - out.height
    shadow(canvas, out, ox, oy)
    canvas.alpha_composite(out, (ox, oy))
    rem = fit(remote, 150, 400)
    rx, ry = 110, floor - rem.height
    shadow(canvas, rem, rx, ry)
    canvas.alpha_composite(rem, (rx, ry))
    return canvas


def compose_column(indoor: Image.Image, outdoor: Image.Image, remote: Image.Image) -> Image.Image:
    """Колонный блок высокий и узкий: сверху он превратился бы в спичку, поэтому
    колонна стоит слева во весь рост, наружный блок справа, пульт между ними."""
    canvas = background()
    floor = 930
    column = fit(indoor, 230, 860)
    cx, cy = 110, floor - column.height
    shadow(canvas, column, cx, cy)
    canvas.alpha_composite(column, (cx, cy))
    out = fit(outdoor, 470, 440)
    ox, oy = SIZE - 70 - out.width, floor - out.height
    shadow(canvas, out, ox, oy)
    canvas.alpha_composite(out, (ox, oy))
    # пульт — в промежуток между колонной и наружным блоком, не наезжая на них
    rem = fit(remote, min(110, max(40, ox - cx - column.width - 40)), 320)
    rx, ry = (cx + column.width + ox - rem.width) // 2, floor - rem.height
    shadow(canvas, rem, rx, ry)
    canvas.alpha_composite(rem, (rx, ry))
    return canvas


def compose_set(image: Image.Image) -> Image.Image:
    """Готовый комплект на белом фоне: вырезать и поставить на наш фон."""
    cut = trim(cut_white(image))
    canvas = background()
    placed = fit(cut, 900, 880)
    x, y = (SIZE - placed.width) // 2, (SIZE - placed.height) // 2 + 10
    shadow(canvas, placed, x, y, 80)
    canvas.alpha_composite(placed, (x, y))
    return canvas


def build(spec: dict) -> Image.Image:
    """spec: {"set": url} или {"indoor": url, "outdoor": url, "remote": url} или {"parts": [urls]}."""
    if spec.get("set"):
        return compose_set(load(spec["set"]))
    if spec.get("parts"):
        kinds = classify([load_part(url) for url in spec["parts"]])
        return compose_parts(kinds["indoor"], kinds["outdoor"], kinds["remote"])
    indoor = load_part(spec["indoor"])
    outdoor = load_part(spec["outdoor"]) if spec.get("outdoor") else None
    remote = load_part(spec["remote"]) if spec.get("remote") else None
    return compose_parts(indoor, outdoor, remote)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Фото серий в стиле витрины из оригиналов")
    parser.add_argument("--only", nargs="*", help="имена файлов фото")
    parser.add_argument("--sources", default=str(SOURCES_FILE))
    args = parser.parse_args(argv)
    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    TARGET.mkdir(parents=True, exist_ok=True)
    done, failed = 0, []
    for name, spec in sources.items():
        if name.startswith("_") or (args.only and name not in args.only):
            continue
        try:
            build(spec).convert("RGB").save(TARGET / name, "WEBP", quality=88, method=6)
            done += 1
        except Exception as error:
            failed.append("%s: %s" % (name, error))
    report = "собрано: %d\n%s\n%s\n" % (done, "\n".join(failed), TARGET)
    sys.stdout.buffer.write(report.encode("utf-8"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
