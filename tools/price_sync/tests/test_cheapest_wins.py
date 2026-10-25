# -*- coding: utf-8 -*-
"""Позиция есть у нескольких поставщиков — побеждает самая низкая цена витрины.

Но сначала — наличие: дешёвое «нет»/«под заказ» не перебивает «в наличии» у другого
поставщика (24.09.2026: DAICHI ICE25 шла «Нет в наличии» по цене трио, хотя у
Техносистемса она была на складе).
"""
from tools.price_sync import matching, sources_oasis, sources_techno, sources_trio, sync


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


def breez_row(title, warehouse, quantity, base):
    return {"source": "oasis", "supplier": "breeze", "nc_code": "НС-1", "brand": "ROYAL CLIMA",
            "title": title, "series": "", "price_wholesale": base * 1.4, "price_base": 0.0,
            "warehouse": warehouse, "quantity": quantity, "breez_base": base}


def test_briz_vne_kryma_pod_zakaz_7_dney_no_silnee_net_u_trio():
    # Владелец 24.09: склады Бриза вне Крыма — «Под заказ 7 дней». Но товар там реально
    # есть: дешёвое «нет» у трио не должно его перебить и сделать карточку «Нет в наличии».
    title = "Классическая сплит-система серии VELA NUOVA RC-VNE28HN (комплект)"
    oasis_rows = [breez_row(title, "ФРЦ Бриз Шерризон-Норд WMS", 5, 17000.0)]
    trio_rows = [{"source": "trio", "page": "bytovye-kondicionery", "section": 32, "series": "",
                  "model": "RC-VNE28HN", "availability": "нет", "dealer": 15000.0, "promo": None}]
    sources = {
        "techno": ([], sources_techno, []),
        "trio": (matching.build_index(trio_rows, lambda o: o["model"]), sources_trio, trio_rows),
        "jac": ({}, None, []),
        "oasis": (matching.build_text_index(oasis_rows, sources_oasis.model_of), sources_oasis, oasis_rows),
    }
    product = {"model": "ROYAL CLIMA RC-VNE28HN on/off", "brand": "ROYAL CLIMA", "group": "onoff"}
    source, module, offer = sync.find_offer(sources, product)
    assert source == "oasis"
    assert module.stock_of(offer) == ("order_7", "Под заказ 7 дней")


def test_vne_kryma_u_lyubogo_postavshchika_pod_zakaz_7_dney():
    # владелец 11.10.2026: в наличии — только Крым, «3–5 дней» больше нет
    row = breez_row("x", "Москва", 3, 1000.0)
    row["supplier"] = "rusklimat"
    assert sources_oasis.stock_of(row) == ("order_7", "Под заказ 7 дней")
    assert sources_oasis.stock_rank(row) == 2
    assert sources_oasis.stock_of(breez_row("x", "Симферополь", 2, 1000.0)) == ("in_stock", "В наличии")


def test_kod_bez_slova_serii_nahoditsya():
    # на сайте «ECLIPSE ECP-I18PN inv», у Бриза между серией и кодом год: «… 2026 ECP-I18PN»
    title = "Инверторная сплит-система серии ECLIPSE Inverter 2026 ECP-I18PN (комплект)"
    rows = [breez_row(title, "ФРЦ Бриз Шерризон-Норд WMS", 9, 39200.0)]
    sources = {
        "techno": ([], sources_techno, []), "trio": ({}, sources_trio, []), "jac": ({}, None, []),
        "oasis": (matching.build_text_index(rows, sources_oasis.model_of), sources_oasis, rows),
    }
    product = {"model": "ECLIPSE ECP-I18PN inv", "brand": "ULTIMA COMFORT", "group": "inv"}
    source, module, offer = sync.find_offer(sources, product)
    assert source == "oasis" and module.stock_of(offer) == ("order_7", "Под заказ 7 дней")
    assert sync.model_code("MHI SRK63ZTL-W inv 6.3") == "SRK63ZTL-W"


def techno_row_series(model, price, series):
    row = techno_row(model, price)
    row["series"] = series
    return row


def test_korotkiy_kod_invertora_ne_cepliaetsya_k_onoff():
    # У Техносистемса «ICE20» — инвертор ICE20AVQS1R-2 (серия «ICE (-15°C inverter)»).
    # Новая on/off DAICHI ICE20AVQ1-1 содержит тот же «ICE20», но это другой товар.
    rows = [techno_row_series("ICE20", 25900, "ICE (-15°C inverter)")]
    sources = {
        "techno": (matching.build_text_index(rows, sources_techno.model_of), sources_techno, rows),
        "trio": ({}, sources_trio, []), "jac": ({}, None, []), "oasis": ([], None, []),
    }
    onoff = {"model": "DAICHI ICE20AVQ1-1 on/off", "brand": "DAICHI", "group": "onoff"}
    assert sync.find_offer(sources, onoff) == (None, None, None)
    inverter = {"model": "DAICHI ICE20AVQS1R-2", "brand": "DAICHI", "group": "inv"}
    assert sync.find_offer(sources, inverter)[0] == "techno"


def test_akciya_pri_padenii_ceny_i_snyatie_plashki():
    from tools.price_sync import publish
    live = [{"id": "1", "model": "X", "price": 40000, "stock": "in_stock"}]
    built = [{"id": "1", "model": "X", "price": 26000, "stock": "in_stock"}]
    final, report = publish.guard(live, built)
    assert final[0]["price"] == 26000 and final[0]["badge"] == "sale" and final[0]["price_regular"] == 40000
    assert report["sales"] and not report["held"]
    # цена вернулась — плашка снимается сама
    final2, report2 = publish.guard(final, [dict(final[0], price=39000)])
    assert final2[0]["price"] == 39000 and "badge" not in final2[0] and report2["sales_over"] == ["X"]
    # рост без акции применяется (владелец 21.10.2026); на проверку — только цена, выросшая вдвое
    final3, report3 = publish.guard(live, [dict(built[0], price=60000)])
    assert final3[0]["price"] == 60000 and not report3["held"]
    final4, report4 = publish.guard(live, [dict(built[0], price=90000)])
    assert final4[0]["price"] == 40000 and report4["held"]


def test_technosistems_onoff_i_invertor_odnogo_razmera():
    # «DU-07» и «DU-07 inv» нормализуются в один ключ — брать надо строку своего типа
    rows = [techno_row_series("DU-07 inv", 20000, "TCL inverter"), techno_row_series("DU-07", 14200, "TCL on/off")]
    sources = {
        "techno": (matching.build_text_index(rows, sources_techno.model_of), sources_techno, rows),
        "trio": ({}, sources_trio, []), "jac": ({}, None, []), "oasis": ([], None, []),
    }
    onoff = {"model": "DENKO DU-07", "brand": "DENKO", "group": "onoff"}
    inv = {"model": "DENKO DU-07 inv", "brand": "DENKO", "group": "inv"}
    assert sync.find_offer(sources, onoff)[2]["model"] == "DU-07"
    assert sync.find_offer(sources, inv)[2]["model"] == "DU-07 inv"
