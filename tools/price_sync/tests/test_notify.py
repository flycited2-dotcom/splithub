# -*- coding: utf-8 -*-
"""Итог ночного прогона приходит в Telegram без звука, дневные сообщения — со звуком."""
from datetime import datetime

from tools.price_sync import notify


def test_nochyu_tiho():
    assert notify.quiet_hours(datetime(2026, 9, 26, 4, 3))
    assert notify.quiet_hours(datetime(2026, 9, 26, 23, 30))
    assert notify.quiet_hours(datetime(2026, 9, 26, 7, 59))


def test_dnem_so_zvukom():
    assert not notify.quiet_hours(datetime(2026, 9, 26, 8, 0))
    assert not notify.quiet_hours(datetime(2026, 9, 26, 20, 3))


def test_nochnoe_soobshchenie_uhodit_bez_zvuka(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_BOT_TOKEN=t\nTELEGRAM_OWNER_CHAT_ID=1\n", encoding="utf-8")
    monkeypatch.setattr(notify, "BOT_ENV", env)
    monkeypatch.setattr(notify, "quiet_hours", lambda now=None: True)
    sent = []

    class Ok:
        ok = True

    monkeypatch.setattr(notify.requests, "post", lambda url, data, timeout: sent.append(data) or Ok())
    assert notify.send("сайт обновлён")
    assert sent[0]["disable_notification"] == "true"
