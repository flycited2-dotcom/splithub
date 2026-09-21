# -*- coding: utf-8 -*-
"""Предохранитель автозаливки: что можно отправить на сайт без человека."""
from datetime import datetime

from tools.price_sync import publish


def item(pid, price, stock="in_stock", model=None):
    return {"id": pid, "model": model or ("M" + pid), "price": price, "stock": stock}


def test_obychnoe_izmenenie_ceny_prohodit():
    final, report = publish.guard([item("1", 79290)], [item("1", 77990)])
    assert final[0]["price"] == 77990
    assert report["prices"] == 1 and not report["held"]


def test_skachok_ceny_derzhim_staruyu():
    # MIDEA MSFE: 29 190 -> 40 190 (+38%) — похоже на заглушку, без человека не льём
    final, report = publish.guard([item("1", 29190)], [item("1", 40190)])
    assert final[0]["price"] == 29190
    assert report["held"][0]["new"] == 40190
    assert report["prices"] == 0


def test_nalichie_obnovlyaetsya_dazhe_pri_zaderzhannoy_cene():
    final, report = publish.guard([item("1", 29190, "order_7")], [item("1", 40190, "out")])
    assert final[0]["price"] == 29190
    assert final[0]["stock"] == "out"
    assert report["stocks"] == 1


def test_granica_skachka_ne_zaderzhivaetsya():
    final, report = publish.guard([item("1", 1000)], [item("1", 1250)])      # ровно +25%
    assert final[0]["price"] == 1250 and not report["held"]


def test_novaya_poziciya_schitaetsya_dobavlennoy():
    final, report = publish.guard([item("1", 100)], [item("1", 100), item("2", 500)])
    assert report["added"] == 1 and len(final) == 2


def test_usyhanie_kataloga():
    live = [item(str(i), 100) for i in range(100)]
    assert publish.shrank_too_much(live, live[:85])
    assert not publish.shrank_too_much(live, live[:95])


def test_soobshchenie_korotkoe_i_s_zaderzhannymi():
    report = {"prices": 1, "stocks": 21, "added": 0,
              "held": [{"model": "MIDEA MSFE-09N8D6-I inv", "old": 29190, "new": 40190, "jump": 0.377}]}
    text = publish.message(report, True, datetime(2026, 9, 21, 20, 5))
    assert text.startswith("✅ СплитХаб 21.09 20:05: цены и остатки обновлены, сайт обновлён.")
    assert "наличие: 21" in text
    assert "MIDEA MSFE-09N8D6-I inv: 29 190 → 40 190 (+38%)" in text


def test_soobshchenie_bez_izmeneniy():
    report = {"prices": 0, "stocks": 0, "added": 0, "held": []}
    assert "изменений нет" in publish.message(report, False, datetime(2026, 9, 21, 20, 5))
