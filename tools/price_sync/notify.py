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
from pathlib import Path

import requests

BOT_ENV = Path(os.getenv(
    "SPLITHUB_TG_ENV",
    r"C:\Users\TLT-1\Documents\GitHub\Site_ostatki_api_teleram\.env"))


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


def send(text: str) -> bool:
    """Отправить сообщение. True — ушло, False — нет (причина уже выведена)."""
    env = _read_env(BOT_ENV)
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat = env.get("TELEGRAM_OWNER_CHAT_ID", "")
    api = (env.get("TELEGRAM_API_URL") or "https://api.telegram.org").rstrip("/")
    if not token or not chat:
        print("telegram: нет токена или chat_id в " + str(BOT_ENV))
        return False
    for attempt in range(3):
        try:
            response = requests.post(api + "/bot" + token + "/sendMessage",
                                     data={"chat_id": chat, "text": text,
                                           "disable_web_page_preview": "true"},
                                     timeout=30)
            if response.ok:
                return True
            print("telegram: ответ %s" % response.status_code)
        except Exception as error:
            print("telegram: попытка %d не удалась: %s" % (attempt + 1, type(error).__name__))
    return False


if __name__ == "__main__":
    raise SystemExit(0 if send(" ".join(sys.argv[1:]) or "проверка связи") else 1)
