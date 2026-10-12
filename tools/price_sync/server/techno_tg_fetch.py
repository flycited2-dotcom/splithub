# -*- coding: utf-8 -*-
"""Новые посты канала «Техносистемс» из личного Telegram владельца — только чтение.

Запускается ВНУТРИ контейнера telegram-personal-mcp (там сессия Telegram; наружу она
не выходит), скрипт подаётся на stdin:

    docker exec -i -w /app -e LAST_ID=260 telegram-personal-mcp-telegram-mcp-1 python - < techno_tg_fetch.py

Печатает JSON-список постов новее LAST_ID: текст, тип вложения, а файлы прайса
(xlsx/csv до 5 МБ) — содержимым в base64. Картинки не качаем: цены с них не разбираем.
"""
import asyncio
import base64
import io
import json
import os
import sys

from telegram_backend import TelegramBackend
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto, PeerChannel

CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "2177370047"))
LAST_ID = int(os.environ.get("LAST_ID", "0") or 0)
MAX_FILE = 5 * 1024 * 1024


async def main():
    backend = TelegramBackend.from_env()
    client = await backend._ready()
    try:
        channel = await client.get_entity(PeerChannel(CHANNEL_ID))
        posts = []
        async for message in client.iter_messages(channel, limit=30, min_id=LAST_ID):
            post = {"id": message.id, "date": message.date.isoformat(), "text": message.message or "",
                    "media": None, "file_name": None}
            if isinstance(message.media, MessageMediaPhoto):
                post["media"] = "photo"
            elif isinstance(message.media, MessageMediaDocument) and message.file:
                post["media"] = "document"
                post["file_name"] = message.file.name
                name = (message.file.name or "").lower()
                if name.endswith((".xlsx", ".xlsm", ".csv")) and (message.file.size or 0) <= MAX_FILE:
                    buffer = io.BytesIO()
                    await client.download_media(message, file=buffer)
                    post["data_b64"] = base64.b64encode(buffer.getvalue()).decode("ascii")
            posts.append(post)
        sys.stdout.write(json.dumps(posts, ensure_ascii=False))
    finally:
        await backend.close()


asyncio.run(main())
