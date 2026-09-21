#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Заливка одного файла сайта по SFTP с бэкапом на сервере.

`converter/deploy.py` умеет только каталог (products.js/json). Этот скрипт нужен,
когда правится сам сайт — например index.html. Перед заменой снимает бэкап с меткой
времени, чтобы откат не зависел от единственного `.bak`, который перетирается.

    python -m tools.price_sync.deploy_file index.html
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import paramiko

SITE_ROOT = Path(__file__).resolve().parents[2]
CONFIG = SITE_ROOT / "converter" / "config" / "deploy.json"


def remote_dir(cfg: dict) -> str:
    remote = str(cfg["remote_path"]).rstrip("/")
    return remote.rsplit("/", 1)[0] if remote.endswith(".js") else remote


def upload(pairs: list[tuple[Path, str]], attempts: int = 3) -> None:
    """Залить (локальный файл, путь на сайте) с датированным бэкапом каждого.

    Сеть до хостинга иногда рвётся — пробуем несколько раз, прежде чем сдаться.
    """
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    site = remote_dir(cfg)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for attempt in range(1, attempts + 1):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(cfg["host"], port=cfg["port"], username=cfg["username"],
                        password=cfg["password"], timeout=cfg.get("timeout", 15))
            sftp = ssh.open_sftp()
            try:
                for local, name in pairs:
                    target = site + "/" + name
                    backup = "%s.bak.%s" % (target, stamp)
                    _, out, _ = ssh.exec_command('cp -p "%s" "%s"' % (target, backup))
                    out.channel.recv_exit_status()
                    sftp.put(str(local), target)
                    print("залито: %s (%d КБ), бэкап %s" % (
                        name, Path(local).stat().st_size // 1024, backup.rsplit("/", 1)[-1]))
            finally:
                sftp.close()
                ssh.close()
            return
        except Exception as error:
            print("заливка: попытка %d из %d не удалась: %s" % (attempt, attempts, error))
            if attempt == attempts:
                raise
            time.sleep(30 * attempt)


def deploy(names: list[str]) -> int:
    pairs = []
    for name in names:
        local = SITE_ROOT / name
        if not local.exists():
            print("пропуск: нет файла " + str(local))
            continue
        pairs.append((local, name))
    upload(pairs)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("укажите файлы: python -m tools.price_sync.deploy_file index.html")
        raise SystemExit(2)
    raise SystemExit(deploy(sys.argv[1:]))
