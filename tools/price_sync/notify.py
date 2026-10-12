#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Короткое сообщение владельцу в Telegram от бота остатков.

Токен и chat_id берутся из .env бота остатков (проект Site_ostatki_api_teleram) при
каждом вызове — в этот репозиторий они не копируются. Отправка никогда не роняет
прогон: не ушло сообщение — пишем в лог и живём дальше, цены важнее уведомления.

    python -m tools.price_sync.notify "текст"
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

#: На сервере сверки — .env бота остатков там же (см. server/run_sync.sh).
BOT_ENV = Path(os.getenv(
    "SPLITHUB_TG_ENV",
    r"C:\Users\TLT-1\Documents\GitHub\Site_ostatki_api_teleram\.env"))
ATTEMPTS = 5
PAUSE = 10


def _read_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def quiet_hours(now: datetime | None = None) -> bool:
    """Ночь (23:00–08:00): прогон идёт в 04:00, и итог не должен будить владельца."""
    hour = (now or datetime.now()).hour
    return hour >= 23 or hour < 8


def send(text: str) -> bool:
    """Отправить сообщение. True — ушло, False — нет (причина уже выведена)."""
    env = _read_env(BOT_ENV)
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat = env.get("TELEGRAM_OWNER_CHAT_ID", "")
    api = (env.get("TELEGRAM_API_URL") or "https://api.telegram.org").rstrip("/")
    if not token or not chat:
        print("telegram: нет токена или chat_id в " + str(BOT_ENV))
        return False
    data = {"chat_id": chat, "text": text, "disable_web_page_preview": "true"}
    if quiet_hours():
        data["disable_notification"] = "true"   # придёт без звука, прочитает утром
    # С сервера api.telegram.org отвечает не с первого раза: бот остатков там же
    # регулярно ловит пару таймаутов подряд, а потом отправляет.
    for attempt in range(ATTEMPTS):
        try:
            response = requests.post(api + "/bot" + token + "/sendMessage",
                                     data=data, timeout=30)
            if response.ok:
                return True
            print("telegram: ответ %s" % response.status_code)
        except Exception as error:
            print("telegram: попытка %d не удалась: %s" % (attempt + 1, type(error).__name__))
        if attempt < ATTEMPTS - 1:
            time.sleep(PAUSE)
    return False


if __name__ == "__main__":
    raise SystemExit(0 if send(" ".join(sys.argv[1:]) or "проверка связи") else 1)
