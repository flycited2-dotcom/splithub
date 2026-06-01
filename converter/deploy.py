#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json
from pathlib import Path

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
artifacts = []
for filename in ("products.js", "products.json"):
    local = BASE_DIR / "out" / filename
    remote = str(Path(cfg["remote_path"]).with_name(filename))
    if not local.exists():
        print(f"[ОШИБКА] out/{filename} не найден — сначала запустите конвертер")
        sys.exit(1)
    artifacts.append((local, remote))

print(f"\nПодключаюсь к {cfg['host']}...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(cfg["host"], port=cfg["port"], username=cfg["username"], password=cfg["password"], timeout=15)

sftp = ssh.open_sftp()
for local, remote in artifacts:
    ssh.exec_command(f'cp {remote} {remote}.bak')
    sftp.put(str(local), remote)
sftp.close()

_, stdout, _ = ssh.exec_command(f'wc -l {cfg["remote_path"]}')
lines = stdout.read().decode().strip().split()[0]
ssh.close()

print(f"Загружено:  products.js и products.json  ({int(lines)-2} товаров на сайте)")
print(f"Сайт:       https://splithub.ru")
