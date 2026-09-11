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
