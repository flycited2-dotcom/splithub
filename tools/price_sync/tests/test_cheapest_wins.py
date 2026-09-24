# -*- coding: utf-8 -*-
"""Позиция есть у нескольких поставщиков — побеждает самая низкая цена витрины.

Но сначала — наличие: дешёвое «нет»/«под заказ» не перебивает «в наличии» у другого
поставщика (24.09.2026: DAICHI ICE25 шла «Нет в наличии» по цене трио, хотя у
Техносистемса она была на складе).
"""
from tools.price_sync import matching, sources_techno, sources_trio, sync


def techno_row(model, price, availability="есть"):
    return {"source": "techno", "brand": "DAICHI", "series": "ICE", "model": model,
            "category": "настенный", "price_1": price, "price_2": 0.0,
            "availability": availability, "note": ""}


def trio_row(model, dealer, availability="есть"):
    return {"source": "trio", "page": "bytovye-kondicionery", "section": 27, "series": "ICE",
            "model": model, "availability": availability, "dealer": dealer, "promo": None}


def build(techno_price, trio_dealer, techno_avail="есть", trio_avail="есть"):
    techno_rows = [techno_row("ICE35", techno_price, techno_avail)]
    trio_rows = [trio_row("ICE35AVQS1R-2", trio_dealer, trio_avail)]
    return {
        "techno": (matching.build_text_index(techno_rows, sources_techno.model_of),
                   sources_techno, techno_rows),
        "trio": (matching.build_index(trio_rows, lambda o: o["model"]), sources_trio, trio_rows),
        "jac": ({}, None, []),
        "oasis": ([], None, []),
    }


PRODUCT = {"model": "DAICHI ICE35AVQS1R-2", "brand": "DAICHI", "group": "inv"}


def test_pobezhdaet_trio_kogda_ono_deshevle():
    # трио 30 000 +5% = 31 590, Техносистемс 31 650 +10% = 34 890
    source, _, offer = sync.find_offer(build(31650, 30000), PRODUCT)
    assert source == "trio" and offer["dealer"] == 30000


def test_pobezhdaet_technosistems_kogda_on_deshevle():
    # Техносистемс 25 900 +10% = 28 490, трио 34 000 +5% = 35 790
    source, _, offer = sync.find_offer(build(25900, 34000), PRODUCT)
    assert source == "techno" and offer["model"] == "ICE35"


def test_korotkiy_kod_postavshchika_nahoditsya_v_nashey_modeli():
    found = matching.lookup_contained_in(
        matching.build_text_index([techno_row("ICE35", 1)], sources_techno.model_of),
        "DAICHI ICE35AVQS1R-2", "DAICHI")
    assert found is not None


def test_pozicii_bez_ceny_ne_uchastvuyut():
    sources = build(0, 30000)          # у Техносистемса «уточняйте»
    source, _, offer = sync.find_offer(sources, PRODUCT)
    assert source == "trio"


def test_kod_postavshchika_dlinnee_nashego():
    # «RK-07SCDG/E» в прайсе против «DANTEX RK-07SCDG on/off» в каталоге
    index = matching.build_text_index([techno_row("RK-07SCDG/E", 18650)], sources_techno.model_of)
    assert matching.lookup_either(index, "DANTEX RK-07SCDG on/off", "DANTEX") is not None


def test_kod_postavshchika_koroche_nashego():
    index = matching.build_text_index([techno_row("ICE20", 25900)], sources_techno.model_of)
    assert matching.lookup_either(index, "DAICHI ICE20AVQS1R-2", "DAICHI") is not None


def test_tochnoe_sovpadenie_pobezhdaet_vhozhdenie():
    # В прайсе наружный блок MULT-18/2 (43 300) стоит раньше внутреннего MULT-18 (14 450).
    # «MULT18» входит в «MULT18/2», и внутреннему блоку доставалась цена наружного.
    rows = [techno_row("MULT-18/2", 43300), techno_row("MULT-18", 14450)]
    index = matching.build_text_index(rows, sources_techno.model_of)
    found = matching.lookup_either(index, "DENKO MULT-18", "DENKO")
    assert found["model"] == "MULT-18"


def test_v_nalichii_vazhnee_deshevizny():
    # трио «нет» 30 000 → 31 590, Техносистемс «есть» 31 650 → 34 890: продаём то, что есть
    source, _, _ = sync.find_offer(build(31650, 30000, trio_avail="нет"), PRODUCT)
    assert source == "techno"


def test_pod_zakaz_ne_perebivaet_nalichie():
    source, _, _ = sync.find_offer(build(31650, 30000, trio_avail="под заказ"), PRODUCT)
    assert source == "techno"


def test_bez_ostatka_u_vseh_pobezhdaet_deshevle():
    # Ни у кого нет на складе — прежнее правило: дешевле. «Под заказ» у одного не
    # перебивает «нет» у другого: владелец велел показывать «нет», как у трио.
    source, _, _ = sync.find_offer(
        build(31650, 30000, techno_avail="под заказ", trio_avail="нет"), PRODUCT)
    assert source == "trio"
