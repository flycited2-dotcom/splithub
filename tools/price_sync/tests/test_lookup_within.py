# -*- coding: utf-8 -*-
from tools.price_sync import matching

OFFERS = [
    {"title": "Инверторные сплит-системы серии ELYSIUM Inverter ELB-I07PN"},
    {"title": "Классическая сплит-система серии ELYSIUM ELB-07PN (комплект)"},
    {"title": "Инверторная сплит-система серии JETPRO Inverter XGI-JP21RHA (комплект)"},
    {"title": "Сплит-система LG P07SP2"},
]
INDEX = matching.build_text_index(OFFERS, lambda offer: offer["title"])


def test_nahodit_kod_vnutri_opisaniya():
    found = matching.lookup_within(INDEX, "ELYSIUM ELB-I07PN inv", "ULTIMA COMFORT")
    assert found["title"].endswith("ELB-I07PN")


def test_ne_putaet_invertor_s_klassikoy():
    found = matching.lookup_within(INDEX, "ELYSIUM ELB-07PN", "ULTIMA COMFORT")
    assert "Классическая" in found["title"]


def test_nahodit_xigma():
    found = matching.lookup_within(INDEX, "XIGMA XGI-JP21RHA inv", "XIGMA")
    assert "JETPRO" in found["title"]


def test_korotkiy_klyuch_ne_lovit_lishnego():
    # «LG» после снятия бренда даёт слишком короткий ключ — совпадения быть не должно
    assert matching.lookup_within(INDEX, "LG XX1", "LG") is None


def test_chuzhaya_model_ne_nahoditsya():
    assert matching.lookup_within(INDEX, "MDV MDSAI-07HRN8 inv", "MDV") is None


LG_OFFERS = [
    {"title": "Инверторная сплит-система серии DELUXE PRO DUAL Inverter H09S1D (комплект)"},
    {"title": "Инверторная сплит-система серии PROCOOL B07TS (комплект)"},
]
LG_INDEX = matching.build_text_index(LG_OFFERS, lambda offer: offer["title"])


def test_lg_tochka_v_artikule_ne_meshaet():
    # у нас «H09S1D.NS1R», у поставщика только «H09S1D»
    found = matching.lookup_within(LG_INDEX, "LG H09S1D.NS1R", "LG")
    assert "DELUXE PRO" in found["title"]


def test_lg_korotkiy_kod_posle_tochki():
    found = matching.lookup_within(LG_INDEX, "LG B07TS.NSJ", "LG")
    assert "PROCOOL" in found["title"]


HISENSE_OFFERS = [
    # чёрный BLACK CRYSTAL стоит в выгрузке раньше и его код длиннее на одну букву
    {"title": "Бытовая сплит-система серии BLACK CRYSTAL Classic A AS-10HW4SYDTG5B (комплект)"},
    {"title": "Классическая сплит-система серии NEO Premium Classic A Wi-Fi AS-10HW4SYDTG5 (комплект)"},
]
HISENSE_INDEX = matching.build_text_index(HISENSE_OFFERS, lambda offer: offer["title"])


def test_obychnaya_versiya_ne_beryot_cenu_wifi():
    # Wi-Fi-версия стоит в выгрузке раньше; код обычной входит в неё целым словом
    offers = [{"title": "Инверторная сплит-система канального типа серии HEAVY EU DC INVERTER Wi-Fi AUD-48UX4REH8/AUW-48U6RN8 WI-FI (комплект)"},
              {"title": "Инверторная сплит-система канального типа серии HEAVY EU DC INVERTER R32 AUD-48UX4REH8/AUW-48U6RN8 (комплект)"}]
    index = matching.build_text_index(offers, lambda offer: offer["title"])
    found = matching.lookup_within(index, "HISENSE AUD-48UX4REH8/AUW-48U6RN8", "HISENSE")
    assert "R32" in found["title"]
    found = matching.lookup_within(index, "HISENSE AUD-48UX4REH8/AUW-48U6RN8 WI-FI", "HISENSE")
    assert "WI-FI (" in found["title"]


def test_odin_kod_v_dvuh_strokah_beryotsya_ta_chto_na_sklade():
    # у Бриза кассета Hisense HEAVY лежит в серии «R32» (0 шт.) и в серии «Wi-Fi» (14 шт.)
    offers = [{"title": "Инверторная сплит-система кассетного типа серии HEAVY EU DC INVERTER R32 ACT-12UR4RCC8/PE-QEA/LD/AUW-12U4RS8 (комплект)", "quantity": 0},
              {"title": "Инверторная сплит-система кассетного типа серии HEAVY EU DC INVERTER Wi-Fi ACT-12UR4RCC8/PE-QEA/LD/AUW-12U4RS8", "quantity": 14}]
    index = matching.build_text_index(offers, lambda offer: offer["title"])
    found = matching.lookup_within(index, "HISENSE ACT-12UR4RCC8/PE-QEA/LD/AUW-12U4RS8", "HISENSE",
                                   prefer=lambda offer: 0 if offer["quantity"] > 0 else 4)
    assert "Wi-Fi" in found["title"]


def test_kod_celikom_a_ne_nachalo_chuzhogo():
    found = matching.lookup_within(HISENSE_INDEX, "HISENSE AS-10HW4SYDTG5 on/off", "HISENSE")
    assert "NEO Premium" in found["title"]
    found = matching.lookup_within(HISENSE_INDEX, "HISENSE AS-10HW4SYDTG5B on/off", "HISENSE")
    assert "BLACK CRYSTAL" in found["title"]
