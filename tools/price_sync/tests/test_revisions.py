# -*- coding: utf-8 -*-
"""Модели, сменённые производителем новой ревизией.

MIDEA MSFE-xxN8D6 больше никто не продаёт: у трио в серии Breezeless E теперь
MSFE1S-xxFRN8G1 (есть), а старый код жил только залежалой строкой Daichi — 0 шт. и
цена двухлетней давности. Сайт показывал «под заказ» и цену «с потолка».
"""
from tools.price_sync import matching, sync


def test_staraya_model_zamenyaetsya_novoy():
    catalog = [{"model": "MIDEA MSFE-12N8D6-I inv"}, {"model": "MIDEA MSAG1-09HRN8-I on/off"}]
    sync.apply_revisions(catalog, {"MIDEA MSFE-12N8D6-I inv": "MIDEA MSFE1S-12FRN8G1-I inv"})
    assert catalog[0]["model"] == "MIDEA MSFE1S-12FRN8G1-I inv"
    assert catalog[1]["model"] == "MIDEA MSAG1-09HRN8-I on/off"


def test_povtornoe_primenenie_nichego_ne_lomaet():
    catalog = [{"model": "MIDEA MSFE1S-12FRN8G1-I inv"}]
    sync.apply_revisions(catalog, {"MIDEA MSFE-12N8D6-I inv": "MIDEA MSFE1S-12FRN8G1-I inv"})
    assert catalog[0]["model"] == "MIDEA MSFE1S-12FRN8G1-I inv"


def test_novaya_model_uznaetsya_v_prayse_trio():
    rows = [{"model": "MSFE1S-12FRN8G1-I/MOFE1-12FRN8G1-O"}]
    index = matching.build_index(rows, lambda o: o["model"])
    assert matching.lookup(index, "MIDEA MSFE1S-12FRN8G1-I inv", "MIDEA") is rows[0]


def test_fayl_revisiy_sootvetstvuet_trio():
    revisions = sync.load_revisions()
    for old, new in revisions.items():
        # новая ревизия — та же марка; null — карточка снята (её заменила другая)
        assert new is None or (old != new and new.split()[0] == old.split()[0])
    assert revisions["MIDEA MSFE-12N8D6-I inv"] == "MIDEA MSFE1S-12FRN8G1-I inv"


def test_revisiya_null_snimaet_kartochku():
    catalog = [{"model": "MIDEA MSAG3-12N8C2S-I inv"}, {"model": "MIDEA MSAG2-12N8C2S-I inv"}, {"model": "X"}]
    sync.apply_revisions(catalog, {"MIDEA MSAG3-12N8C2S-I inv": None,
                                   "MIDEA MSAG2-12N8C2S-I inv": "MIDEA MSAG2-12N8C2U-I inv"})
    assert [p["model"] for p in catalog] == ["MIDEA MSAG2-12N8C2U-I inv", "X"]
