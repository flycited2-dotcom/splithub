# -*- coding: utf-8 -*-
import pytest

from tools.price_sync import consumables, sources_trio


def trio_row(section, model, dealer, promo=None):
    return {"source": "trio", "page": "raskhodnye-materialy", "section": section,
            "series": "", "model": model, "availability": "есть",
            "dealer": dealer, "promo": promo}


COPPER = [
    trio_row(49, "1/4 (6,35мм.), 0,61мм, 15м", 2220.0),
    trio_row(49, "1/4 (6,35мм.), 0,60мм, 15м", 2550.0),
    trio_row(49, "1/4 (6,35мм.), 0,76мм, 15м", 2750.0),
    trio_row(49, "1/4 (6,35мм.), 0,76мм, 15м", 3050.0),
    trio_row(49, "3/4 (19,05мм.), 0,81мм, 15м", 11000.0),
    trio_row(49, "3/4 (19,05мм.), 0,89мм, 15м", 12150.0),
    trio_row(49, "3/4 (19,05мм.), 0,9мм, 15м", 10960.0),
]


def card(model, desc="", brand="Медная труба", group="truba"):
    return {"model": model, "descShort": desc, "brand": brand, "group": group}


def test_med_srednyaya_stenka_beret_deshevuyu_tonkuyu():
    found = consumables.match(card("Медная труба 1/4 · бухта 15 м", "Средняя стенка · бухта 15 м"), COPPER)
    assert found["dealer"] == 2220.0


def test_med_gost_beret_samuyu_tolstuyu():
    found = consumables.match(card("Медная труба 1/4 · бухта 15 м", "Толстая (ГОСТ) · бухта 15 м"), COPPER)
    assert found["dealer"] == 2750.0   # из двух предложений 0,76мм — дешёвое


def test_med_blizkie_tolshchiny_odin_klass():
    # 0,89 и 0,9 — один класс ГОСТ, берём дешёвое из двух
    found = consumables.match(card("Медная труба 3/4 · бухта 15 м", "Толстая (ГОСТ) · бухта 15 м"), COPPER)
    assert found["dealer"] == 10960.0


def test_med_drugaya_dlina_ne_matchitsya():
    assert consumables.match(card("Медная труба 1/4 · бухта 50 м", "Средняя стенка"), COPPER) is None


BRACKETS = [
    trio_row(48, "Кронштейны 400x420, S=1,50мм", 240.0, promo=1.0),
    trio_row(48, "Кронштейны 500x600, S=2,5мм", 870.0),
    trio_row(48, "Кронштейны ОЦ сборные 500х600, S=2.0мм", 900.0),
    trio_row(48, "Кронштейны 600x800, S=3,0мм", 2100.0),
]


def test_kronshtein_po_razmeru_i_tolshchine():
    found = consumables.match(card("Кронштейн-500-600-2,0", brand="Кронштейны", group="rashod"), BRACKETS)
    assert found["dealer"] == 900.0    # 2,0 мм, а не 2,5 мм


def test_kronshtein_bez_sovpadeniya_tolshchiny():
    assert consumables.match(card("Кронштейн-415-450-1,8", brand="Кронштейны", group="rashod"), BRACKETS) is None


DRAIN = [trio_row(54, "Труба металлопластиковая, 16мм", 44.0, promo=3800.0),
         trio_row(54, "Шланг гибкий гофрированный, 16мм, 30м", 850.0)]


def test_drenazh_po_pryamomu_sopostavleniyu():
    found = consumables.match(card("16 гибкий 30 м. бухта", brand="Дренаж гибкий", group="rashod"), DRAIN)
    assert found["dealer"] == 850.0


@pytest.mark.parametrize("dealer, promo, expected", [
    (14945.0, 13700.0, 13700.0),   # нормальная акция — берём её
    (44.0, 3800.0, 44.0),          # «акция» выше дилерской: это цена за бухту, не скидка
    (240.0, 1.0, 240.0),           # «акция 1,00» — мусор в прайсе
    (2600.0, 2200.0, 2200.0),
    (15500.0, None, 15500.0),
])
def test_akciya_tolko_razumnaya(dealer, promo, expected):
    assert sources_trio.cost_of({"dealer": dealer, "promo": promo}) == expected


FASTENERS = [
    trio_row(412, "Болт 8х25 ОЦ", 3.40),
    trio_row(412, "8х100", 8.50),
    trio_row(412, "Гайка М10 ОЦ.", 3.00),
]


def test_krepezh_umnozhaetsya_na_upakovku():
    # 3,40 ₽ за штуку × 50 = 170 ₽ за упаковку
    found = consumables.match(card("Болт 8-25", brand="Болт 8-25", group="rashod"), FASTENERS)
    assert found["dealer"] == 170.0
    assert "x50" in found["model"]


def test_gluhar_po_razmeru():
    found = consumables.match(card("Глухарь 8-100мм(50шт)", brand="Глухарь", group="rashod"), FASTENERS)
    assert found["dealer"] == 425.0


def test_neizvestnyy_krepezh_bez_sopostavleniya():
    # дюбелей в таблице нет — вслепую не считаем
    assert consumables.match(card("Дюбель 6х40", brand="Дюбель 6х40", group="rashod"), FASTENERS) is None


DOWELS = [
    trio_row(412, "Дюбель Tchappai 6х40 (полипропилен)", 0.75),
    trio_row(412, "Дюбель Tchappai 12x70 (полипропилен)", 4.00),
]


def test_dyubel_6x40_upakovkoy_50():
    found = consumables.match(card("Дюбель 6х40", brand="Дюбель 6х40", group="rashod"), DOWELS)
    assert found["dealer"] == 37.5


def test_dyubel_12x80_beret_blizhayshiy_razmer():
    found = consumables.match(
        card("Дюбель распорн KPO 12х80(50шт)", brand="Дюбель", group="rashod"), DOWELS)
    assert found["dealer"] == 200.0
