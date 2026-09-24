# -*- coding: utf-8 -*-
"""Новые карточки из прайсов трио и Бриза по реестру серий (series_map.json).

Владелец 24.09.2026: «начинай с тех, что в наличии; FUNAI — через API Бриза».
"""
from tools.price_sync import new_cards


def trio_row(model, series, availability="есть", section=25, dealer=20000.0):
    return {"source": "trio", "page": "bytovye-kondicionery", "section": section,
            "series": series, "image": "", "model": model, "availability": availability,
            "dealer": dealer, "promo": None}


def breez_row(title, series, warehouse="Симферополь", quantity=4, brand="FUNAI"):
    return {"source": "oasis", "supplier": "breeze", "nc_code": "НС-1", "brand": brand,
            "title": title, "series": series, "price_wholesale": 30000.0, "price_base": 30000.0,
            "warehouse": warehouse, "quantity": quantity, "breez_base": 25000.0}


EASY = {"supplier": "trio", "section": 25, "match": "Сплит-системы Midea серии EASY (MSES) Inverter",
        "brand": "MIDEA", "series": "EASY inverter", "group": "inv", "suffix": "inv",
        "size": "btu", "photo": "midea-easy-inv.webp"}
KADZOKU = {"supplier": "breez", "brand_at_supplier": "FUNAI",
           "match": "Инверторные сплит-системы серии KADZOKU Inverter 2025",
           "brand": "FUNAI", "series": "KADZOKU inverter 2025", "group": "inv", "suffix": "inv",
           "size": "kw", "photo": "funai-kadzoku-inv.webp"}


def test_kod_vnutrennego_bloka_u_trio():
    assert new_cards.trio_code("MSES1S-07FRN8G1/MOES1-07FRN8G1") == "MSES1S-07FRN8G1"
    assert new_cards.trio_code("DA25EVQ1R /DF25EV1R") == "DA25EVQ1R"
    # Roland: «/N6» — часть кода, а блоки разделены «-IN»/«-OUT»
    assert new_cards.trio_code("FU-07HSS010/N6-IN FU-07HSS010/N6-OUT") == "FU-07HSS010/N6"


def test_kod_modeli_iz_nazvaniya_briza():
    assert new_cards.breez_code(
        "Инверторная сплит-система серии KADZOKU Inverter 2025 RAC-I-KD25HP.D03 (комплект)",
        "Инверторные сплит-системы серии KADZOKU Inverter 2025") == "RAC-I-KD25HP.D03"
    # регистр в названии и в серии у Бриза не совпадает
    assert new_cards.breez_code(
        "Инверторная сплит-система напольно-потолочного типа серии COMPETENZA DC EU INVERTER 2023 CO-F 36HNBI/CO-E 36HNBI (комплект)",
        "Инверторная сплит-система напольно-потолочного типа серии COMPETENZA DC EU Inverter 2023"
    ) == "CO-F 36HNBI/CO-E 36HNBI"


def test_kod_kogda_nazvanie_serii_v_tovare_drugoe():
    # в товаре серия короче, чем в справочнике серий
    assert new_cards.breez_code(
        "Инверторная сплит-система серии PROCOOL B07TS (комплект)",
        "Инверторные сплит-системы серии PROCOOL DUAL Inverter") == "B07TS"
    # лишнее слово перед кодом и пометка хладагента — не код
    assert new_cards.breez_code(
        "Классическая сплит-система серии GLORIA UPGRADE RC-GL22HN (комплект)",
        "Классические сплит-системы серии GLORIA") == "RC-GL22HN"
    assert new_cards.breez_code(
        "Инверторная сплит-система серии X-COMFORT (R32) RAK-18REF/RAC-18WEF (комплект)",
        "Инверторные сплит-системы серии X-Comfort") == "RAK-18REF/RAC-18WEF"
    # а «CO-D» — часть кода канального блока, её не отрезаем
    assert new_cards.breez_code(
        "Инверторная сплит-система канального типа серии COMPETENZA DC EU Inverter 2023 CO-D 36HNBI /CO-E 36HNBI (комплект)",
        "Инверторные сплит-системы канального типа серии COMPETENZA DC EU Inverter 2023"
    ) == "CO-D 36HNBI/CO-E 36HNBI"


def test_tiporazmer_po_kodu():
    assert new_cards.size_of("MSES1-07HRN8G1", "btu") == "07"
    assert new_cards.size_of("FU-07HSS010/N6", "btu") == "07"
    assert new_cards.size_of("CO-F 36HNX/CO-E 36HNX", "btu") == "36"
    assert new_cards.size_of("DA20EVQ1R", "kw") == "07"
    assert new_cards.size_of("ICE60AVQ1-1", "kw") == "24"     # 6 кВт, а не 60 000 BTU
    assert new_cards.size_of("RAC-I-KD55HP.D03", "kw") == "18"


def test_trio_beryotsya_tolko_v_nalichii():
    rows = [trio_row("MSES1S-07FRN8G1/MOES1-07FRN8G1", "Сплит-системы Midea серии EASY (MSES)  Inverter"),
            trio_row("MSES1S-09FRN8G1/MOES1-09FRN8G1", "Сплит-системы Midea серии EASY (MSES)  Inverter",
                     availability="ожидается")]
    found = list(new_cards.supplier_offers(rows, [], [EASY]))
    assert [code for _, code, _ in found] == ["MSES1S-07FRN8G1"]


def test_briz_tolko_simferopol_i_ostatok():
    series = "Инверторные сплит-системы серии KADZOKU Inverter 2025"
    rows = [breez_row("Инверторная сплит-система серии KADZOKU Inverter 2025 RAC-I-KD25HP.D03 (комплект)", series),
            breez_row("Инверторная сплит-система серии KADZOKU Inverter 2025 RAC-I-KD35HP.D03 (комплект)", series,
                      warehouse="ФРЦ Бриз Шереметьево"),
            breez_row("Инверторная сплит-система серии KADZOKU Inverter 2025 RAC-I-KD55HP.D03 (комплект)", series,
                      quantity=0)]
    found = list(new_cards.supplier_offers([], rows, [KADZOKU]))
    assert [code for _, code, _ in found] == ["RAC-I-KD25HP.D03"]


def test_uzhe_est_na_sayte_korotkim_kodom():
    # На сайте «DAICHI SIB25» (код Техносистемса), у трио — «SIB25AVQS1R»: это тот же товар.
    catalog = [{"brand": "DAICHI", "model": "DAICHI SIB25"},
               {"brand": "FUNAI", "model": "FUNAI Inverter RAC-I-DA25HP.D01"}]
    index = new_cards.catalog_codes(catalog)
    assert new_cards.already_listed(index, "SIB25AVQS1R")
    assert new_cards.already_listed(index, "RAC-I-DA25HP.D01")
    assert not new_cards.already_listed(index, "SIB50AVQS1R")
    assert not new_cards.already_listed(index, "RAC-I-DA35HP.D01")


def test_hvost_v_odnu_bukvu_eto_drugoy_tovar():
    # «B» в конце — чёрный BLACK CRYSTAL, без неё — белый NEO Premium: разные товары
    index = new_cards.catalog_codes([{"brand": "HISENSE", "model": "HISENSE AS-10HW4SYDTG5B on/off"}])
    assert not new_cards.already_listed(index, "AS-10HW4SYDTG5")
    assert new_cards.already_listed(index, "AS-10HW4SYDTG5B")


def test_nazvanie_serii_bez_slov_kotorye_dopishet_vitrina():
    # витрина сама пишет «Inverter»/«On/Off» после названия серии инвертора и on/off
    assert new_cards.display_series(KADZOKU) == "KADZOKU 2025"
    assert new_cards.display_series({"series": "KADZOKU on/off 2025", "group": "onoff"}) == "KADZOKU 2025"
    assert new_cards.display_series({"series": "SIBERIA (-25°C inverter)", "group": "inv"}) == "SIBERIA (-25°C)"
    assert new_cards.display_series({"series": "MEGACOOL", "group": "inv"}) == "MEGACOOL"
    # у полупрома витрина ничего не дописывает — название как есть
    assert new_cards.display_series({"series": "COMPETENZA on/off", "group": "pac_onoff"}) == "COMPETENZA on/off"


def test_vylozhennye_kartochki_pereimenovyvayutsya_odin_raz():
    catalog = [{"brand": "FUNAI", "series": "KADZOKU inverter 2025", "model": "FUNAI RAC-I-KD25HP.D03 inv"},
               {"brand": "DENKO", "series": "TCL on/off", "model": "DENKO DU-07"}]
    assert new_cards.rename_registry_series(catalog, [KADZOKU]) == 1
    assert catalog[0]["series"] == "KADZOKU 2025"
    assert catalog[1]["series"] == "TCL on/off"          # не из реестра — не трогаем
    assert new_cards.rename_registry_series(catalog, [KADZOKU]) == 0


def test_novinka_beryot_napolnenie_po_klyuchu_reestra():
    content = {"FUNAI|KADZOKU inverter 2025": {"cardBenef": "Инвертор", "descTemplate": "Инвертор {btu} BTU"}}
    card = new_cards.supplier_card(KADZOKU, "RAC-I-KD25HP.D03", [], 1)
    assert card["series"] == "KADZOKU 2025"
    filled = new_cards.enrich(card, content, {}, "FUNAI|KADZOKU inverter 2025")
    assert filled["cardBenef"] == "Инвертор" and filled["descShort"] == "Инвертор 09 BTU"


def test_kartochka_iz_reestra():
    card = new_cards.supplier_card(EASY, "MSES1S-12FRN8G1", [{"id": "1778", "brand": "MIDEA",
                                                             "brandCode": "mdpri", "model": "x"}], 1779)
    assert card["model"] == "MIDEA MSES1S-12FRN8G1 inv"
    assert card["sku"] == "midea-mses1s-12frn8g1"
    assert card["brandCode"] == "mdpri"
    assert card["btu"] == "12" and card["area"] == 35
    assert card["photo"] == "midea-easy-inv.webp" and card["group"] == "inv"
