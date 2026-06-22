#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from tools.catalog_sync import assert_catalogs_match, parse_products_js, read_products_json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import paramiko
except ImportError:
    print("Устанавливаю paramiko...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    import paramiko

BASE_DIR = Path(__file__).parent
cfg = json.loads((BASE_DIR / "config" / "deploy.json").read_text(encoding="utf-8"))

local_js   = BASE_DIR / "out" / "products.js"
local_json = BASE_DIR / "out" / "products.json"

if not local_js.exists() or not local_json.exists():
    print("[ОШИБКА] out/products.js или out/products.json не найден — сначала запустите конвертер")
    sys.exit(1)

try:
    assert_catalogs_match(
        parse_products_js(local_js.read_text(encoding="utf-8")),
        read_products_json(local_json),
    )
except ValueError as error:
    print(f"[ОШИБКА] Каталоги не синхронизированы: {error}")
    sys.exit(1)

# remote_path может быть каталогом сайта (.../public_html) ИЛИ полным путём к products.js
remote = str(cfg["remote_path"]).rstrip("/")
site_dir = remote.rsplit("/", 1)[0] if remote.endswith(".js") else remote
js_remote   = site_dir + "/products.js"
json_remote = site_dir + "/products.json"

print(f"\nПодключаюсь к {cfg['host']}...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(cfg["host"], port=cfg["port"], username=cfg["username"],
            password=cfg["password"], timeout=cfg.get("timeout", 15))

sftp = ssh.open_sftp()

def deploy_one(local_path, remote_path):
    if not local_path.exists():
        print(f"  пропуск: {local_path.name} не найден в out/ (запустите конвертер)")
        return
    # бэкап текущего файла на сервере (дожидаемся завершения cp)
    _, out, _ = ssh.exec_command(f'cp -p "{remote_path}" "{remote_path}.bak" 2>/dev/null')
    out.channel.recv_exit_status()
    sftp.put(str(local_path), remote_path)
    print(f"  загружено: {remote_path.split('/')[-1]}  ({local_path.stat().st_size // 1024} КБ)")

# products.js (витрина) и products.json (серверный каталог) — только проверенной парой.
deploy_one(local_js, js_remote)
deploy_one(local_json, json_remote)
sftp.close()

_, stdout, _ = ssh.exec_command(f'wc -l "{js_remote}"')
try:
    lines = int(stdout.read().decode().strip().split()[0]) - 2
except Exception:
    lines = 0
ssh.close()

print(f"\nСайт:       https://splithub.ru  (≈{max(lines, 0)} товаров на витрине)")
