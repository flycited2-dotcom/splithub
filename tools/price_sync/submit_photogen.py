#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Постановка задач фотоген-агенту: перерисовать снимки товаров в стиле СплитХаба.

Скачанные со страниц дилеров оригиналы годятся как временная затычка, но они с
чужими фонами и подписями. Фотоген (`mode=conditioner`) переснимает товар на нашем
сером фоне. Задачи ставятся ЧЕРЕЗ СЕРВЕР: токен агента и chat_id владельца лежат
в `/root/ritualb2b/.env` и никуда не копируются.

    python -m tools.price_sync.submit_photogen            # поставить задачи
    python -m tools.price_sync.submit_photogen --dry-run  # только показать, что уйдёт
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import paramiko

from tools.price_sync.sync import DEFAULT_OUT

SITE_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_CONFIG = SITE_ROOT / "converter" / "config" / "deploy.json"

#: Каталог фотоген-агента на VPS и путь, куда кладём исходники перед постановкой.
FOTOGEN_ROOT = "/root/ritualb2b"
UPLOAD_DIR = "/tmp/splithub_photos"

#: Хост, на котором крутится фотоген (тот же VPS, что и база SplitHome).
SSH_ALIAS_HOST = "212.116.115.150"
SSH_PORT = 2222
SSH_USER = "root"
SSH_KEY = str(Path.home() / ".ssh" / "id_ritualb2b_admin")


def jobs_from_catalog(out_dir: Path, originals: Path, only: set[str] | None = None) -> list[dict]:
    """По одной задаче на серию: фото + бренд + серия + преимущества."""
    catalog = json.loads((out_dir / "catalog" / "products.json").read_text(encoding="utf-8"))
    by_photo: dict[str, dict] = {}
    for product in catalog:
        photo = product.get("photo") or ""
        if only and photo not in only:
            continue
        stem = Path(photo).stem
        source = next((f for f in originals.iterdir() if f.stem == stem), None)
        if source is None:
            continue
        entry = by_photo.setdefault(photo, {
            "photo": photo, "source": source, "brand": product["brand"],
            "series": product["series"], "specs": product.get("benefits") or [],
        })
        if len(product.get("benefits") or []) > len(entry["specs"]):
            entry["specs"] = product["benefits"]
    return sorted(by_photo.values(), key=lambda job: job["photo"])


def connect() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_ALIAS_HOST, port=SSH_PORT, username=SSH_USER,
                key_filename=SSH_KEY, timeout=20)
    return ssh


def submit(jobs: list[dict], dry_run: bool, mode: str) -> int:
    if dry_run:
        for job in jobs:
            print("  %-46s %s / %s (%d пунктов ТТХ)" % (
                job["photo"], job["brand"], job["series"][:28], len(job["specs"])))
        return 0

    ssh = connect()
    sftp = ssh.open_sftp()
    ssh.exec_command("mkdir -p " + UPLOAD_DIR)[1].channel.recv_exit_status()
    queued, failed = 0, []
    try:
        for job in jobs:
            remote = UPLOAD_DIR + "/" + job["source"].name
            sftp.put(str(job["source"]), remote)
            specs = "\\n".join(job["specs"][:10]).replace('"', "'")
            # Токен и chat_id читаются НА СЕРВЕРЕ: sed вместо source, потому что
            # в .env есть значения с пробелами, и shell пытается их выполнить.
            command = (
                'T=$(sed -n "s/^API_TOKEN=//p" %(root)s/.env); '
                'C=$(sed -n "s/^TELEGRAM_ALLOWED_USER_ID=//p" %(root)s/.env); '
                'curl -sS -X POST http://127.0.0.1:8765/api/submit-job '
                '-H "x-agent-token: $T" '
                '-F "mode=%(mode)s" -F "chat_id=$C" '
                '-F "brand=%(brand)s" -F "model=%(model)s" '
                '-F "specs=$(printf \'%%b\' "%(specs)s")" '
                '-F "photo=@%(file)s"'
            ) % {"root": FOTOGEN_ROOT, "brand": job["brand"], "mode": mode,
                 "model": job["series"], "specs": specs, "file": remote}
            _, out, err = ssh.exec_command(command)
            answer = out.read().decode("utf-8", "replace").strip()
            out.channel.recv_exit_status()
            if '"ok":true' in answer.replace(" ", ""):
                queued += 1
                print("  поставлено: %-44s %s" % (job["photo"], job["brand"]))
            else:
                failed.append((job["photo"], answer[:120] or err.read().decode("utf-8", "replace")[:120]))
    finally:
        sftp.close()
        ssh.close()

    for photo, reason in failed:
        print("  НЕ поставлено: %-40s %s" % (photo, reason))
    print("\nВ очередь ушло: %d из %d" % (queued, len(jobs)))
    return 0 if queued else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Поставить задачи фотоген-агенту")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--mode", default="conditioner",
                        choices=("conditioner", "mcp", "kbt"),
                        help="стиль карточки: conditioner — светлый, mcp — графитовый фон")
    parser.add_argument("--source", default=None,
                        help="папка с исходниками (по умолчанию out/photos/originals)")
    parser.add_argument("--only", default=None,
                        help="только эти файлы каталога, через запятую")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    originals = Path(args.source) if args.source else out_dir / "photos" / "originals"
    only = {n.strip() for n in args.only.split(",")} if args.only else None
    jobs = jobs_from_catalog(out_dir, originals, only)
    if not jobs:
        print("нечего ставить: нет исходников в " + str(originals))
        return 1
    sys.stdout.buffer.write(("Задач к постановке: %d\n" % len(jobs)).encode("utf-8"))
    return submit(jobs, args.dry_run, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
