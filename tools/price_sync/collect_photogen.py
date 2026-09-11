#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сбор готовых карточек от фотоген-агента и замена ими временных снимков.

Задачи ставит `submit_photogen`. Когда агент отрисовал товар на фирменном фоне,
файл лежит в OUTPUT_DIR на VPS. Здесь мы находим готовые задачи по бренду и серии,
забираем результат, переводим в webp под именем, которое ждёт каталог, и кладём
в assets/img/products. Заливку на сайт делает `deploy_file`.

    python -m tools.price_sync.collect_photogen             # забрать готовое
    python -m tools.price_sync.collect_photogen --status    # только показать очередь
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image

from tools.price_sync.submit_photogen import FOTOGEN_ROOT, connect, jobs_from_catalog
from tools.price_sync.sync import DEFAULT_OUT

SITE_ROOT = Path(__file__).resolve().parents[2]
ASSETS = SITE_ROOT / "assets" / "img" / "products"
QUEUE = FOTOGEN_ROOT + "/queue.db"
OUTPUT_DIR = FOTOGEN_ROOT + "/output"

#: Сколько последних задач просматриваем — свои ставили одной пачкой.
LOOKBACK = 40


def query(ssh, sql: str) -> list[list[str]]:
    # Свой разделитель через exec_command не долетает до sqlite3 — берём его «|» по умолчанию.
    _, out, _ = ssh.exec_command('sqlite3 %s "%s"' % (QUEUE, sql.replace('"', "'")))
    text = out.read().decode("utf-8", "replace").strip()
    out.channel.recv_exit_status()
    rows = []
    for line in text.split("\n"):
        if not line:
            continue
        cells = line.split("|")
        cells += [""] * (5 - len(cells))     # у чужих задач бренд и модель пустые
        rows.append(cells)
    return rows


def statuses(ssh) -> list[list[str]]:
    return query(ssh, "select id, status, brand, model, coalesce(output_filename,'') "
                      "from jobs order by id desc limit %d" % LOOKBACK)


def collect(check_only: bool) -> int:
    jobs = jobs_from_catalog(DEFAULT_OUT, DEFAULT_OUT / "photos" / "originals")
    # (бренд, серия) → имя файла, которого ждёт каталог
    wanted = {(job["brand"], job["series"]): job["photo"] for job in jobs}

    ssh = connect()
    write = sys.stdout.buffer.write
    try:
        rows = statuses(ssh)
        mine = [r for r in rows if (r[2], r[3]) in wanted]
        done = [r for r in mine if r[1] == "done" and r[4]]
        write(("Наших задач в очереди: %d  |  готово: %d\n" % (len(mine), len(done))).encode("utf-8"))
        for row in mine:
            write(("  %-6s %-11s %-9s %s\n" % (row[0], row[1], row[2][:9], row[3][:34])).encode("utf-8"))
        if check_only or not done:
            return 0

        ASSETS.mkdir(parents=True, exist_ok=True)
        sftp = ssh.open_sftp()
        saved = []
        try:
            for job_id, _, brand, model, output in done:
                target = ASSETS / wanted[(brand, model)]
                with sftp.open(OUTPUT_DIR + "/" + output, "rb") as handle:
                    data = handle.read()
                with Image.open(io.BytesIO(data)) as image:
                    image = image.convert("RGB")
                    image.thumbnail((1000, 1000))
                    image.save(target, "WEBP", quality=86, method=6)
                saved.append(target.name)
                write(("  забрано: %-44s (задача %s)\n" % (target.name, job_id)).encode("utf-8"))
        finally:
            sftp.close()
        write(("\nЗабрано файлов: %d. Залить: python -m tools.price_sync.deploy_file %s\n" % (
            len(saved), " ".join("assets/img/products/" + n for n in saved[:3]) + (" ..." if len(saved) > 3 else ""))
        ).encode("utf-8"))
    finally:
        ssh.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Забрать готовые карточки у фотогена")
    parser.add_argument("--status", action="store_true", help="только показать состояние очереди")
    args = parser.parse_args(argv)
    return collect(args.status)


if __name__ == "__main__":
    raise SystemExit(main())
