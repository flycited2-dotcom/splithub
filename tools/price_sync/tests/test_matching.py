# -*- coding: utf-8 -*-
from tools.price_sync import matching


def test_kirillicheskie_gomoglify():
    # трио печатает «В-07FIR» кириллической «В», каталог — латинской «B»
    assert matching.normalize("В-07FIR/B-07FIQ") == matching.normalize("B-07FIR/B-07FIQ")


def test_suffiksy_vitriny_ne_meshayut():
    assert matching.normalize("KENTATSU KSGHA21HFRN1 on/off") == "KENTATSUKSGHA21HFRN1"
    assert matching.normalize("MDV MDSAI-07HRN8 inv") == "MDVMDSAI07HRN8"


def test_brend_otbrasyvaetsya_v_klyuchah():
    assert "B09SIR/B09SIQ" in matching.keys("БИРЮСА B-09SIR/B-09SIQ inv", "БИРЮСА")


def test_para_blokov_matchitsya_po_vnutrennemu():
    # поставщик даёт пару «внутренний/наружный», каталог — только внутренний
    index = matching.build_index(
        [{"model": "KSGHA21HFRN1/KSRHA21HFRN1", "dealer": 100.0}],
        lambda offer: offer["model"],
    )
    found = matching.lookup(index, "KENTATSU KSGHA21HFRN1 on/off", "KENTATSU")
    assert found is not None and found["dealer"] == 100.0


def test_chuzhaya_model_ne_matchitsya():
    index = matching.build_index([{"model": "KSGHA21HFRN1"}], lambda offer: offer["model"])
    assert matching.lookup(index, "MDV MDSAI-07HRN8 inv", "MDV") is None


def test_midea_para_s_kirillicheskim_o():
    index = matching.build_index(
        [{"model": "MSAG3-07HRN8-I/MSAG3-07HRN8-О"}],   # вторая «О» — кириллица
        lambda offer: offer["model"],
    )
    assert matching.lookup(index, "MIDEA MSAG3-07HRN8-I on/off", "MIDEA") is not None
