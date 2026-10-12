# -*- coding: utf-8 -*-
import pytest

from tools.price_sync.pricing import compute_price, round_up_90


@pytest.mark.parametrize("raw, expected", [
    (275, 290),          # крепёж: мелкие суммы тоже округляются шагом 100
    (14945, 14990),
    (15692, 15790),      # уже прошли …90 внутри сотни — уходим в следующую
    (21420, 21490),
    (23562, 23590),
    (14990, 14990),      # ровно …90 остаётся на месте
    (14991, 15090),
    (100, 190),
])
def test_round_up_90(raw, expected):
    assert round_up_90(raw) == expected


def test_round_up_90_nikogda_ne_umenshaet():
    for raw in range(20, 5000, 7):
        assert round_up_90(raw) >= raw


def test_trio_pyat_procentov():
    # дилерская 14 945 + 5% = 15 692,25 → 15 790
    assert compute_price(14945, "trio") == 15790


def test_jac_desyat_procentov():
    # закупка 21 420 + 10% = 23 562 → 23 590
    assert compute_price(21420, "jac") == 23590


def test_oasis_kak_jac():
    assert compute_price(21420, "oasis") == compute_price(21420, "jac")


def test_nulevaya_zakupka_oshibka():
    with pytest.raises(ValueError):
        compute_price(0, "trio")


def test_neizvestnyy_istochnik_oshibka():
    with pytest.raises(ValueError):
        compute_price(1000, "neizvestno")


@pytest.mark.parametrize("raw, expected", [
    (99, 100),
    (203.5, 205),
    (187, 190),
    (100, 100),
    (101, 105),
    (467.5, 470),
])
def test_round_up_5(raw, expected):
    from tools.price_sync.pricing import round_up_5
    assert round_up_5(raw) == expected


def test_deshevye_pozicii_shagom_5():
    # болт: закупка 185 + 10% = 203,5 → 205, а не 290
    assert compute_price(185, "trio_rashod") == 205


def test_dorogie_pozicii_po_prezhnemu_do_90():
    assert compute_price(21420, "jac") == 23590


def test_granica_tysyachi():
    # 900 + 10% = 990 — ещё дешёвая позиция, шаг 5
    assert compute_price(900, "jac") == 990
    # 950 + 10% = 1045 — уже дорогая, шаг до …90
    assert compute_price(950, "jac") == 1090


def test_plavayuschaya_tochka_ne_sdvigaet_cenu():
    # 900 * 1.1 в float = 990.0000000000001; цена не должна уехать на 995
    assert compute_price(900, "jac") == 990
    # 13700 * 1.05 = 14385.000000000002 — та же ловушка на дорогой позиции
    assert compute_price(13700, "trio") == 14390
