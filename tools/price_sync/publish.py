#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Автоматическая заливка пересчитанного каталога на сайт — с предохранителем.

Прогон по расписанию считает цены и наличие, а этот шаг решает, что из этого
можно без человека отправить на splithub.ru, и сообщает владельцу в Telegram.

Предохранитель:
  * цена позиции прыгнула больше чем на MAX_JUMP — на сайте остаётся старая цена,
    позиция уходит в сообщение «на проверку» (как MIDEA MSFE +38% у Daichi при
    нулевом остатке — похоже на заглушку, а не на закупку);
  * наличие обновляется всегда — ради него всё и затевалось;
  * каталог усох больше чем на MAX_SHRINK или не прошёл проверку — не льём вообще.

    python -m tools.price_sync.publish            # залить и сообщить
    python -m tools.price_sync.publish --dry-run  # показать, что уйдёт, ничего не трогая
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

from tools.price_sync import merge, notify
from tools.price_sync.deploy_file import upload
from tools.price_sync.sync import DEFAULT_OUT, render_products_js

LIVE_JSON = "https://splithub.ru/products.json"

#: Скачок цены, после которого позиция не льётся без человека.
MAX_JUMP = 0.25
#: Рост цены. Владелец 21.10.2026: «цены должны быть актуальны, даже если растут — товар просто
#: вышел из акции» — поэтому рост применяем сразу; на проверку уходит только цена, выросшая
#: больше чем вдвое (так выглядит ошибка прайса: потерялась фасовка, лишний ноль).
MAX_RISE = 1.00
#: Во сколько раз каталог может усохнуть, прежде чем мы откажемся его лить.
MAX_SHRINK = 0.10
#: Падение цены глубже этого — не акция, а ошибка данных (потерялась фасовка, ноль в прайсе):
#: цену держим и зовём человека. 21.10.2026 «Гайка М10» 165 → 5 ₽ ушла на сайт как «Акция».
MAX_CRASH = 0.70

STOCK_NAMES = {"in_stock": "в наличии", "out": "нет", "wait": "ожидается",
               "order_7": "под заказ", "days_7": "7 дней", "days_3_5": "3–5 дней",
               "days_1_2": "1–2 дня"}


def guard(live: list[dict], built: list[dict], max_jump: float = MAX_JUMP, max_rise: float = MAX_RISE):
    """Применить предохранитель. Возвращает (итоговый каталог, отчёт).

    Отчёт: сколько цен и остатков поменялось, какие позиции отложены, сколько новых.
    """
    before = {product["id"]: product for product in live}
    final, held, held_drop, sales, sales_over = [], [], [], [], []
    prices = stocks = added = replaced = 0
    for product in built:
        item = dict(product)
        old = before.get(item["id"])
        if old is None:
            added += 1
        else:
            old_price, new_price = old.get("price") or 0, item.get("price") or 0
            on_sale = old.get("badge_auto") == "sale"
            regular = old.get("price_regular") or old_price
            if item.get("model") != old.get("model"):
                # Карточку перевели на новую ревизию модели: прежняя цена была у другого
                # товара и ей не ориентир — держать её значит оставить ошибку на сайте.
                replaced += 1
            elif old_price and new_price != old_price:
                jump = (new_price - old_price) / old_price
                if jump < -MAX_CRASH:
                    held_drop.append({"model": item["model"], "old": old_price,
                                      "new": new_price, "jump": jump})
                    item["price"] = old_price          # цену держим, наличие — обновляем
                elif jump < -max_jump:
                    # Резкое падение — у поставщика акция или распродажа (владелец
                    # 11.10.2026): цену ставим сразу и вешаем плашку «Акция».
                    _start_sale(item, regular)
                    sales.append({"model": item["model"], "old": old_price,
                                  "new": new_price, "jump": jump})
                    prices += 1
                elif on_sale:
                    prices += 1
                    if new_price >= regular * SALE_OVER:
                        _end_sale(item)
                        sales_over.append(item["model"])
                elif jump > max_rise:
                    held.append({"model": item["model"], "old": old_price,
                                 "new": new_price, "jump": jump})
                    item["price"] = old_price          # цену держим, наличие — обновляем
                else:
                    prices += 1
            elif on_sale and new_price >= regular * SALE_OVER:
                _end_sale(item)
                sales_over.append(item["model"])
            if item.get("stock") != old.get("stock"):
                stocks += 1
        final.append(item)
    return final, {"prices": prices, "stocks": stocks, "held": held, "held_drop": held_drop,
                   "added": added, "replaced": replaced, "sales": sales, "sales_over": sales_over}


#: Акция кончилась, когда цена вернулась хотя бы к 90% прежней.
SALE_OVER = 0.90


def _start_sale(item: dict, regular: int) -> None:
    """Плашка «Акция» на витрине (поле badge читает index.html) и цена до акции."""
    item.update(badge="sale", badge_label="Акция", badge_auto="sale", price_regular=regular)


def _end_sale(item: dict) -> None:
    """Снимаем только свою плашку — ручную из админки не трогаем."""
    if item.get("badge_auto") == "sale":
        for field in ("badge", "badge_label", "badge_auto", "price_regular"):
            item.pop(field, None)


def shrank_too_much(live: list[dict], built: list[dict], limit: float = MAX_SHRINK) -> bool:
    return bool(live) and len(built) < len(live) * (1 - limit)


def message(report: dict, published: bool, when: datetime) -> str:
    stamp = when.strftime("%d.%m %H:%M")
    if not published:
        head = "ℹ️ СплитХаб %s: сверка прошла, изменений нет — сайт не трогали." % stamp
    else:
        head = "✅ СплитХаб %s: цены и остатки обновлены, сайт обновлён." % stamp
    counts = ("Цен изменилось: %d · наличие: %d · новых позиций: %d"
              % (report["prices"], report["stocks"], report["added"]))
    if report.get("replaced"):
        counts += " · заменено моделей: %d" % report["replaced"]
    lines = [head, counts]
    if report.get("sales"):
        lines.append("🏷 Цена упала больше %d%% — залита, на сайте плашка «Акция»:" % int(MAX_JUMP * 100))
        for item in report["sales"][:8]:
            lines.append("  %s: %s → %s (%+d%%)" % (item["model"], _rub(item["old"]),
                                                   _rub(item["new"]), round(item["jump"] * 100)))
        if len(report["sales"]) > 8:
            lines.append("  …и ещё %d" % (len(report["sales"]) - 8))
    if report.get("sales_over"):
        lines.append("Акция кончилась, плашка снята: " + ", ".join(report["sales_over"][:8]))
    if report.get("held_drop"):
        lines.append("⏸ На проверку, цена не залита (обвал больше %d%% — похоже на ошибку прайса):"
                     % int(MAX_CRASH * 100))
        for item in report["held_drop"][:8]:
            lines.append("  %s: %s → %s (%+d%%)" % (item["model"], _rub(item["old"]),
                                                    _rub(item["new"]), round(item["jump"] * 100)))
    if report["held"]:
        lines.append("⏸ На проверку, цена не залита (рост больше %d%% — похоже на ошибку прайса):"
                     % int(MAX_RISE * 100))
        for item in report["held"][:8]:
            lines.append("  %s: %s → %s (%+d%%)" % (item["model"], _rub(item["old"]),
                                                   _rub(item["new"]), round(item["jump"] * 100)))
        if len(report["held"]) > 8:
            lines.append("  …и ещё %d" % (len(report["held"]) - 8))
    return "\n".join(lines)


def _rub(value: int) -> str:
    return "{:,}".format(int(value)).replace(",", " ")


def _digest(catalog: list[dict]) -> str:
    return hashlib.sha256(json.dumps(catalog, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def run(dry_run: bool, quiet: bool) -> int:
    now = datetime.now()
    live = requests.get(LIVE_JSON, params={"t": int(now.timestamp())}, timeout=60).json()
    built = json.loads((DEFAULT_OUT / "catalog" / "products.json").read_text(encoding="utf-8"))

    if shrank_too_much(live, built):
        text = ("⚠️ СплитХаб %s: каталог усох с %d до %d позиций — не заливаю, сайт не тронут."
                % (now.strftime("%d.%m %H:%M"), len(live), len(built)))
        print(text)
        if not dry_run and not quiet:
            notify.send(text)
        return 1

    final, report = guard(live, built)
    problems = merge.validate(final)
    if problems:
        text = ("⚠️ СплитХаб %s: каталог не прошёл проверку — не заливаю, сайт не тронут.\n%s"
                % (now.strftime("%d.%m %H:%M"), "\n".join(problems[:5])))
        print(text)
        if not dry_run and not quiet:
            notify.send(text)
        return 1

    changed = _digest(final) != _digest(live)
    text = message(report, changed, now)
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    if dry_run:
        return 0

    if changed:
        target = DEFAULT_OUT / "publish"
        target.mkdir(parents=True, exist_ok=True)
        (target / "products.json").write_text(
            json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (target / "products.js").write_text(render_products_js(final), encoding="utf-8")
        # Сначала серверный каталог (по нему проверяются заявки), потом витрина.
        upload([(target / "products.json", "products.json"),
                (target / "products.js", "products.js")])
        check = requests.get(LIVE_JSON, params={"t": int(datetime.now().timestamp())}, timeout=60).json()
        if _digest(check) != _digest(final):
            text = ("⚠️ СплитХаб %s: файлы залиты, но сайт отдаёт другое содержимое — проверьте."
                    % now.strftime("%d.%m %H:%M"))
            print(text)
            if not quiet:
                notify.send(text)
            return 1

    if not quiet:
        notify.send(text)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Залить каталог на сайт с предохранителем")
    parser.add_argument("--dry-run", action="store_true", help="ничего не заливать и не слать")
    parser.add_argument("--quiet", action="store_true", help="не слать сообщение в Telegram")
    args = parser.parse_args(argv)
    return run(args.dry_run, args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
