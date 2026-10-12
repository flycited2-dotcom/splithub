# -*- coding: utf-8 -*-
from tools.price_sync import new_cards

SIBLING = {
    "brand": "EUROHOFF", "model": "EUROHOFF EM-09I inv", "series": "CALLISTO",
    "group": "inv", "btu": "09", "area": 25,
    "descShort": "Инвертор 09 BTU · до 25 м²",
    "cardBenef": "GMCC Toshiba · Gold Fin · Самоочистка · 3 года",
    "benefits": ["Компрессор GMCC Toshiba", "Gold Fin"],
    "compressor": "GMCC Toshiba", "freon": "R32", "photo": "eurohoff-callisto.webp",
}
NEWBIE = {
    "brand": "EUROHOFF", "model": "EUROHOFF EM-07I", "series": "CALLISTO inverter (Midea)",
    "group": "inv", "btu": "07", "area": 20, "descShort": "", "cardBenef": "",
    "benefits": [], "compressor": "", "freon": "", "photo": "eurohoff-callisto-inverter-midea.webp",
}


def test_odna_liniya_raznyy_tiporazmer():
    assert (new_cards.family_key("EUROHOFF", "EUROHOFF EM-07I")
            == new_cards.family_key("EUROHOFF", "EUROHOFF EM-09I inv"))


def test_raznye_linii_ne_rodstvenniki():
    assert (new_cards.family_key("DENKO", "DENKO DU-07")
            != new_cards.family_key("EUROHOFF", "EUROHOFF EM-07I"))


def test_nahodit_rodstvennika():
    assert new_cards.find_sibling(NEWBIE, [SIBLING]) is SIBLING


def test_rodstvennika_net():
    assert new_cards.find_sibling(NEWBIE, []) is None


def test_nasleduet_napolnenie_i_foto():
    filled = new_cards.inherit(NEWBIE, SIBLING)
    assert filled["compressor"] == "GMCC Toshiba"
    assert filled["freon"] == "R32"
    assert filled["photo"] == "eurohoff-callisto.webp"   # фото уже есть, снимать не надо
    assert filled["benefits"] == ["Компрессор GMCC Toshiba", "Gold Fin"]


def test_opisanie_pereschityvaetsya_pod_svoy_tiporazmer():
    filled = new_cards.inherit(NEWBIE, SIBLING)
    assert filled["descShort"] == "Инвертор 07 BTU · до 20 м²"


def test_nasledovanie_ne_portit_cenu_i_nalichie():
    card = dict(NEWBIE, price=25690, stock="in_stock")
    filled = new_cards.inherit(card, SIBLING)
    assert filled["price"] == 25690 and filled["stock"] == "in_stock"


CATALOG = [
    {"brand": "DAICHI", "brandCode": "daice", "model": "DAICHI ICE20AVQS1R-2"},
    {"brand": "DAICHI", "brandCode": "daice", "model": "DAICHI ICE25AVQS1R-2"},
    {"brand": "EUROHOFF", "brandCode": "ehas", "model": "EUROHOFF AVE-07M"},
    {"brand": "EUROHOFF", "brandCode": "ehcal", "model": "EUROHOFF EM-09I"},
]


def test_beret_kod_suschestvuyuschego_brenda():
    # иначе DAICHI покажется на витрине двумя блоками вместо одного
    assert new_cards.brand_code_for("DAICHI", CATALOG) == "daice"


def test_pri_neskolkih_kodah_beret_samyy_chastyy():
    assert new_cards.brand_code_for("EUROHOFF", CATALOG) in ("ehas", "ehcal")


def test_novyy_brend_poluchaet_slag():
    assert new_cards.brand_code_for("DENKO", CATALOG) == "denko"


def test_kod_ne_zavisit_ot_registra_nazvaniya():
    assert new_cards.brand_code_for("YNOVIK", []) == "ynovik"
