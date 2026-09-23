#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Деплой фикса Telegram-уведомлений (коммит 23138be) на прод + смоук-тест заявкой.

Запуск из корня репозитория (нужны git и Python 3; paramiko поставится сам):
    python tools/deploy_tg_fix.py --dry-run     # только показать план, ничего не менять
    python tools/deploy_tg_fix.py               # деплой + тестовая заявка
    python tools/deploy_tg_fix.py --rollback 20260923-183000   # откат из бэкапов

Креды SFTP — converter/config/deploy.json (как у converter/deploy.py).

Безопасность (прод может расходиться с git, см. HANDOFF.md):
  * файл на сервере == версия до фикса  → заливаем новую версию;
  * файл на сервере уже == новой версии → пропуск;
  * файл на сервере отличается          → 3-way merge (git merge-file): база = версия до фикса,
    «наши» = боевая, «их» = новая. Чистое слияние заливаем, при конфликте НИЧЕГО не заливаем.
  * всё или ничего: сначала план по всем файлам, потом бэкап <файл>.bak.<ts> и заливка.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
BASE_COMMIT = "41f2644"  # состояние до фикса
FILES = [
    "send.php",
    "api/admin.php",
    "api/auth.php",
    "api/price-send.php",
    "api/reports.php",
    "api/tg_poll.php",
    "api/lib/manager_notify.php",
]
SITE_URL = "https://splithub.ru"
CONFIG_KEYS = ["BOT_TOKEN", "CHAT_ID", "TG_FORCE_IP", "WEBHOOK_SECRET", "EMAIL_TO"]


def git_show(rev, path):
    return subprocess.run(["git", "show", f"{rev}:{path}"], cwd=REPO,
                          capture_output=True, check=True).stdout


def merge3(base, ours, theirs):
    """git merge-file: возвращает (ok, merged_bytes)."""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, data in (("ours", ours), ("base", base), ("theirs", theirs)):
            p = Path(d) / name
            p.write_bytes(data)
            paths.append(str(p))
        r = subprocess.run(["git", "merge-file", "-p", *paths], capture_output=True)
        return r.returncode == 0, r.stdout


class SftpRemote:
    def __init__(self, cfg):
        try:
            import paramiko
        except ImportError:
            print("Устанавливаю paramiko...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
            import paramiko
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kw = dict(hostname=cfg["host"], port=int(cfg.get("port", 22)), username=cfg["username"],
                  timeout=cfg.get("timeout", 30), banner_timeout=30)
        if cfg.get("key_path"):
            kw["key_filename"] = cfg["key_path"]
        else:
            kw["password"] = cfg["password"]
        self.ssh.connect(**kw)
        self.sftp = self.ssh.open_sftp()

    def read(self, path):
        try:
            with self.sftp.open(path, "rb") as f:
                return f.read()
        except IOError:
            return None

    def write(self, path, data):
        with self.sftp.open(path, "wb") as f:
            f.write(data)

    def listdir(self, path):
        try:
            return self.sftp.listdir(path)
        except IOError:
            return []

    def close(self):
        self.sftp.close()
        self.ssh.close()


def site_dir_from(cfg):
    remote = str(cfg["remote_path"]).rstrip("/")
    return remote.rsplit("/", 1)[0] if remote.endswith(".js") else remote


def plan_files(remote, site):
    plan, problems = [], []
    for rel in FILES:
        new = (REPO / rel).read_bytes()
        base = git_show(BASE_COMMIT, rel)
        cur = remote.read(f"{site}/{rel}")
        if cur is None:
            problems.append(f"{rel}: нет на сервере")
        elif cur == new:
            plan.append((rel, "уже актуален", None, cur))
        elif cur == base:
            plan.append((rel, "заливка новой версии", new, cur))
        else:
            ok, merged = merge3(base, cur, new)
            if ok:
                plan.append((rel, "на проде есть свои правки → слито 3-way без конфликтов", merged, cur))
            else:
                problems.append(f"{rel}: на проде свои правки, слияние с конфликтом — нужен ручной разбор")
    return plan, problems


def check_config(remote, site):
    """Показывает, какие ключи заданы во внешнем config.php (значения не печатаются)."""
    path = site.rsplit("/", 1)[0] + "/config.php"
    data = remote.read(path)
    print(f"\nВнешний config.php ({path}):")
    if data is None:
        print("  ⚠ не найден/не читается")
        return
    text = data.decode("utf-8", "replace")
    import re
    for key in CONFIG_KEYS:
        m = re.search(r"define\(\s*['\"]" + key + r"['\"]\s*,\s*(.*?)\)\s*;", text)
        if not m:
            print(f"  ❌ {key}: НЕ ЗАДАН")
            continue
        val = m.group(1).strip().strip("'\"")
        print(f"  {'✅' if val else '❌'} {key}: {'задан (' + str(len(val)) + ' симв.)' if val else 'ПУСТОЙ'}")


def smoke_test():
    items = json.loads((REPO / "products.json").read_text(encoding="utf-8"))
    p = next(x for x in items if x["id"] == "1070")  # «15мм*20м» — раньше ломал Markdown
    payload = {
        "name": "ТЕСТ Claude — проверка уведомлений",
        "phone": "+7 000 000-00-00",
        "client_tg": "@test_user_check",
        "comment": "Тестовая заявка после деплоя фикса Telegram, не обрабатывать (спецсимволы: * _ < &)",
        "items": [{"id": p["id"], "name": p["model"], "brand": p["brand"],
                   "price": p["price"], "qty": 1, "group": p["group"]}],
    }
    req = urllib.request.Request(f"{SITE_URL}/send.php", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
    print(f"\nОтвет send.php: {body}")
    try:
        d = json.loads(body)
    except ValueError:
        return False
    return bool(d.get("ok")) and d.get("tg") == "sent"


def show_error_log_tail(remote, site):
    for cand in (f"{site}/error_log", f"{site}/error.log", f"{site.rsplit('/', 1)[0]}/logs/error.log"):
        data = remote.read(cand)
        if data:
            lines = [l for l in data.decode("utf-8", "replace").splitlines() if "SplitHub" in l][-5:]
            if lines:
                print(f"\nПоследние строки [SplitHub] из {cand}:")
                for l in lines:
                    print("  " + l[:400])
                return
    print("\nЛог PHP с [SplitHub] не найден по стандартным путям — смотрите в панели хостинга.")


def rollback(remote, site, ts):
    for rel in FILES:
        bak = remote.read(f"{site}/{rel}.bak.{ts}")
        if bak is None:
            print(f"  нет бэкапа: {rel}.bak.{ts}")
            continue
        remote.write(f"{site}/{rel}", bak)
        print(f"  восстановлен: {rel}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", metavar="TS")
    ap.add_argument("--no-test", action="store_true")
    args = ap.parse_args()

    cfg = json.loads((REPO / "converter" / "config" / "deploy.json").read_text(encoding="utf-8"))
    site = site_dir_from(cfg)
    print(f"Подключаюсь к {cfg['host']} …  webroot: {site}")
    remote = SftpRemote(cfg)
    try:
        if args.rollback:
            rollback(remote, site, args.rollback)
            return 0

        check_config(remote, site)
        plan, problems = plan_files(remote, site)
        print("\nПлан:")
        for rel, what, _, _ in plan:
            print(f"  {rel}: {what}")
        if problems:
            print("\n⛔ Деплой остановлен, ничего не изменено:")
            for p in problems:
                print("  " + p)
            return 2
        if args.dry_run:
            print("\n--dry-run: изменений не вносилось.")
            return 0

        ts = time.strftime("%Y%m%d-%H%M%S")
        for rel, _, data, cur in plan:
            if data is None:
                continue
            remote.write(f"{site}/{rel}.bak.{ts}", cur)
            remote.write(f"{site}/{rel}", data)
            print(f"  залит: {rel}  (бэкап {rel}.bak.{ts})")
        print(f"\nОткат при необходимости: python tools/deploy_tg_fix.py --rollback {ts}")

        if args.no_test:
            return 0
        ok = smoke_test()
        if ok:
            print("\n✅ Смоук-тест пройден: заявка принята, tg=sent. Проверьте сообщение в группе Telegram.")
            return 0
        print("\n❌ Смоук-тест: Telegram не отправлен (или заявка не принята).")
        show_error_log_tail(remote, site)
        return 1
    finally:
        remote.close()


if __name__ == "__main__":
    sys.exit(main())
