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


def test_rost_ceny_posle_akcii_primenyaetsya():
    # владелец 21.10.2026: Hisense +30% — товар вышел из акции, цена должна быть актуальной
    final, report = publish.guard([item("1", 18290)], [item("1", 23690)])
    assert final[0]["price"] == 23690 and not report["held"] and report["prices"] == 1


def test_cena_vyrosshaya_vdvoe_derzhitsya_na_proverku():
    final, report = publish.guard([item("1", 165)], [item("1", 8250)])      # потерялась фасовка
    assert final[0]["price"] == 165
    assert report["held"][0]["new"] == 8250 and report["prices"] == 0


def test_nalichie_obnovlyaetsya_dazhe_pri_zaderzhannoy_cene():
    final, report = publish.guard([item("1", 29190, "order_7")], [item("1", 70000, "out")])
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


def test_smena_modeli_ne_zaderzhivaetsya():
    # MSFE-12N8D6 сменилась ревизией MSFE1S-12FRN8G1: это другая модель, и старая цена
    # (залежалая строка Daichi) ей не ориентир — предохранитель её не держит.
    final, report = publish.guard(
        [item("1", 30890, "order_7", model="MIDEA MSFE-12N8D6-I inv")],
        [item("1", 40090, "in_stock", model="MIDEA MSFE1S-12FRN8G1-I inv")])
    assert final[0]["price"] == 40090 and not report["held"]
    assert report["replaced"] == 1


def test_soobshchenie_pro_zamenu_modeley():
    report = {"prices": 0, "stocks": 4, "added": 0, "held": [], "replaced": 4}
    assert "заменено моделей: 4" in publish.message(report, True, datetime(2026, 9, 24, 12, 0))


def test_obval_ceny_bolee_chem_na_70_procentov_derzhim_staruyu():
    # 21.10.2026: «Гайка М10» 165 → 5 ₽ (−97%) ушла на сайт как «Акция» — это ошибка данных
    # (потерялась фасовка), а не акция. Настоящее падение бывает до ~50%.
    final, report = publish.guard([item("1", 165)], [item("1", 5)])
    assert final[0]["price"] == 165 and "badge" not in final[0]
    assert report["held_drop"][0]["new"] == 5 and not report["sales"]
    assert "5" in publish.message(dict(report, prices=0, stocks=0, added=0), False,
                                  datetime(2026, 10, 21, 4, 0))


def test_padenie_na_40_procentov_ostaetsya_akciey():
    final, report = publish.guard([item("1", 1000)], [item("1", 600)])
    assert final[0]["price"] == 600 and final[0]["badge"] == "sale"
    assert not report["held_drop"]
