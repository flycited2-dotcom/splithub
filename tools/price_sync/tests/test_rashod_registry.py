# -*- coding: utf-8 -*-
"""Расходники трио по реестру (rashod_map.json).

Владелец 25.09.2026 прислал шесть разделов трио — медь, кронштейны, дренажные
насосы, ленту, дренаж и фреон: «наценка плюс 10%», чего нет у нас — выложить,
«какого нет — естественно пишешь нет в наличии».
"""
from tools.price_sync import consumables, matching, merge, new_cards, pricing, sources_trio, sync


def trio_row(section, model, dealer, promo=None, availability="есть"):
    return {"source": "trio", "page": "raskhodnye-materialy", "section": section,
            "series": "", "image": "", "model": model, "availability": availability,
            "dealer": dealer, "promo": promo}


ROWS = [
    trio_row(48, "Кронштейны 400x450, S=2,0мм", 260.0),
    trio_row(48, "Кронштейны ОЦ сборные 400x450, S=2,0мм", 700.0),
    trio_row(48, "PROFcool VR-X250 виброопора (под болт М8) 1шт. для мембранных плоских кровель",
             1350.0, availability="ожидается"),
    trio_row(54, "Труба металлопластиковая, 16мм", 44.0, promo=3800.0),
    trio_row(58, "R-410a", 17000.0, promo=14500.0),
    trio_row(58, "R404", 0.0, availability="нет"),
]

REGISTRY = {
    "kronshtein-oc-400-450-2,0": {
        "sku": "kronshtein-oc-400-450-2,0", "section": 48,
        "trio": "Кронштейны ОЦ сборные 400x450, S=2,0мм",
        "card": {"brand": "Кронштейны", "brandCode": "kron", "series": "Оцинкованные",
                 "model": "Кронштейны ОЦ сборные 400×450, 2,0 мм",
                 "descShort": "Оцинкованные, сборные · 400×450 мм · металл 2,0 мм",
                 "cardBenef": "Оцинкованные · 400×450 · 2,0 мм",
                 "benefits": ["Размер 400×450 мм"], "photo": "kronshtein-oc.webp"},
    },
    "vibroopora-profcool-vr-x250": {
        "sku": "vibroopora-profcool-vr-x250", "section": 48,
        "trio": "PROFcool VR-X250 виброопора (под болт М8) 1шт. для мембранных плоских кровель",
        "card": {"brand": "Подставки, опоры, козырьки", "brandCode": "podst", "series": "PROFcool",
                 "model": "Виброопора PROFcool VR-X250", "descShort": "Под болт М8",
                 "cardBenef": "Для плоской кровли", "benefits": [], "photo": "vr-x250.webp"},
    },
    "drenazh-metalloplast-100": {
        "sku": "drenazh-metalloplast-100", "section": 54,
        "trio": "Труба металлопластиковая, 16мм", "pack": 100, "pack_promo": True,
    },
    "freon-22": {"sku": "freon-22", "section": 58, "trio": "R-22"},
    "freon-404": {"sku": "freon-404", "section": 58, "trio": "R404",
                  "card": {"brand": "ФРЕОН", "brandCode": "freon", "series": "R404",
                           "model": "Фреон R-404A", "descShort": "Фреон R-404A",
                           "cardBenef": "Фреон R-404A", "benefits": [], "photo": "freon-404.webp"}},
}


def product(sku, model="", brand="", group="rashod"):
    return {"sku": sku, "model": model, "brand": brand, "group": group}


def sources(rows):
    return {"techno": ([], None, []),
            "trio": (matching.build_index(rows, lambda o: o["model"]), sources_trio, rows),
            "jac": ({}, None, []), "oasis": ([], None, [])}


def test_reestr_beryot_imenno_svoyu_stroku_a_ne_deshevuyu_togo_zhe_razmera():
    # по размеру и толщине подошёл бы и крашеный кронштейн за 260 ₽
    found = consumables.match(
        product("kronshtein-oc-400-450-2,0", "Кронштейны ОЦ сборные 400×450, 2,0 мм", "Кронштейны"),
        ROWS, REGISTRY)
    assert found["dealer"] == 700.0


def test_probely_v_nazvanii_postavshchika_ne_meshayut():
    rows = [trio_row(48, "Кронштейны  ОЦ сборные 400x450,\xa0S=2,0мм ", 700.0)]
    found = consumables.match(product("kronshtein-oc-400-450-2,0"), rows, REGISTRY)
    assert found is not None


def test_bukhta_po_cene_iz_akcii():
    # «44,00» — за метр, «Акция 3800 за бухту 100м» — цена всей бухты
    found = consumables.match(product("drenazh-metalloplast-100", "16 металлопласт 100 м. бухта"),
                              ROWS, REGISTRY)
    assert found["dealer"] == 4400.0
    assert sources_trio.cost_of(found) == 3800.0


def test_bukhta_bez_akcii_schitaetsya_po_metram():
    rows = [trio_row(54, "Труба металлопластиковая, 16мм", 44.0)]
    found = consumables.match(product("drenazh-metalloplast-100"), rows, REGISTRY)
    assert sources_trio.cost_of(found) == 4400.0


def test_kartochka_ne_iz_reestra_idyot_po_staroy_logike():
    found = consumables.match({"model": "Кронштейн-400-450-2,0", "brand": "Кронштейны",
                               "group": "rashod"}, ROWS, REGISTRY)
    assert found["dealer"] == 260.0


def test_nacenka_reestra_10_procentov_dazhe_so_slovom_bolt():
    # «под болт М8» в названии не делает виброопору крепежом с наценкой 100%
    name, _, offer = sync.find_offer(
        sources(ROWS), product("vibroopora-profcool-vr-x250", "Виброопора PROFcool VR-X250 под болт",
                               "Подставки, опоры, козырьки"), REGISTRY)
    assert name == "trio_rashod"
    assert pricing.compute_price(sources_trio.cost_of(offer), name) == 1490


def test_pozicii_reestra_net_u_trio_net_v_nalichii():
    assert consumables.delisted(product("freon-22"), ROWS, REGISTRY)


def test_nulevaya_cena_u_trio_net_v_nalichii():
    assert consumables.delisted(product("freon-404"), ROWS, REGISTRY)


def test_est_u_trio_ne_snyata():
    assert not consumables.delisted(product("drenazh-metalloplast-100"), ROWS, REGISTRY)


def test_razdel_ne_skachalsya_nichego_ne_snimaem():
    # сломался разбор страницы — это не повод гасить весь фреон на сайте
    rows = [row for row in ROWS if row["section"] != 58]
    assert not consumables.delisted(product("freon-22"), rows, REGISTRY)


def test_ne_iz_reestra_ne_snimaetsya():
    assert not consumables.delisted(product("kronshtein-415-450-1,8"), ROWS, REGISTRY)


def test_novaya_kartochka_iz_reestra():
    catalog = [{"id": "1100", "sku": "freon-22", "brand": "ФРЕОН", "brandCode": "freon"}]
    cards = new_cards.build_rashod_cards(ROWS, catalog, 1101, REGISTRY)
    oc = next(card for card in cards if card["sku"] == "kronshtein-oc-400-450-2,0")
    assert oc["id"] == "1101"
    assert oc["price"] == 770                       # 700 + 10%
    assert oc["stock"] == "in_stock"
    assert oc["group"] == "rashod" and oc["type"] == "sol"
    assert oc["model"] == "Кронштейны ОЦ сборные 400×450, 2,0 мм"
    assert not merge.validate([oc])


def test_novaya_kartochka_pod_zakaz_nesmotrya_na_bolt():
    cards = new_cards.build_rashod_cards(ROWS, [], 1, REGISTRY)
    vr = next(card for card in cards if card["sku"] == "vibroopora-profcool-vr-x250")
    assert vr["price"] == 1490 and vr["stock"] == "order_7"


def test_bez_ceny_u_trio_kartochka_bez_ceny():
    # R404 у трио «нет» и 0,00 ₽ — карточка ждёт цену, merge её отложит
    cards = new_cards.build_rashod_cards(ROWS, [], 1, REGISTRY)
    assert next(card for card in cards if card["sku"] == "freon-404")["price"] == 0


def test_uzhe_vylozhennaya_ne_dubliruetsya():
    catalog = [{"id": "5", "sku": "kronshtein-oc-400-450-2,0"}]
    cards = new_cards.build_rashod_cards(ROWS, catalog, 6, REGISTRY)
    assert all(card["sku"] != "kronshtein-oc-400-450-2,0" for card in cards)


def test_tekst_vylozhennoy_kartochki_beryotsya_iz_reestra():
    old = {"id": "1063", "sku": "kronshtein-oc-400-450-2,0", "model": "Кронштейн-400-450-2,0",
           "cardBenef": "400-450-2,1", "benefits": ["400-450-2,2"], "price": 290,
           "stock": "in_stock", "brand": "Кронштейны", "photo": "kronshtein.webp"}
    changed = consumables.apply_cards([old], REGISTRY)
    assert changed == 1
    assert old["model"] == "Кронштейны ОЦ сборные 400×450, 2,0 мм"
    assert old["benefits"] == ["Размер 400×450 мм"]
    assert old["price"] == 290 and old["id"] == "1063" and old["stock"] == "in_stock"
    assert consumables.apply_cards([old], REGISTRY) == 0      # повторно — без изменений
