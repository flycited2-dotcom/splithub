# -*- coding: utf-8 -*-
"""Ревизия поставщиков (владелец 12.10.2026).

* Русклимат пока не подключаем вовсе.
* Royal Clima, Hisense, FUNAI — только Бриз, у трио их не берём.
* Трио (ИП Чабанов) берёт у Daichi и даёт отсрочку: если позиция есть у трио, берём
  трио, даже когда у Daichi дешевле. Daichi — только когда у трио нет на складе, а у
  Daichi есть, или у трио этой позиции нет вообще.
"""
from tools.price_sync import matching, sources_oasis, sources_techno, sources_trio, sync


def trio_row(model, dealer, availability="есть", section=26):
    return {"source": "trio", "page": "bytovye-kondicionery", "section": section, "series": "",
            "model": model, "availability": availability, "dealer": dealer, "promo": None}


def oasis_row(supplier, brand, title, cost, quantity, warehouse="Симферополь"):
    return {"source": "oasis", "supplier": supplier, "nc_code": "X-" + title, "brand": brand,
            "title": title, "series": "", "price_wholesale": cost, "price_base": cost,
            "warehouse": warehouse, "quantity": quantity, "breez_base": cost}


def build(trio_rows, oasis_rows):
    return {
        "techno": ([], sources_techno, []),
        "trio": (matching.build_index(trio_rows, lambda o: o["model"]), sources_trio, trio_rows),
        "jac": ({}, None, []),
        "oasis": (matching.build_text_index(oasis_rows, sources_oasis.model_of), sources_oasis, oasis_rows),
    }


KENTATSU = {"model": "KENTATSU KSGHA21HFRN1 inv", "brand": "KENTATSU", "group": "inv"}
DAICHI_TITLE = "Kentatsu KSGHA21HFRN1/KSRHA21HFRN1 HEGEMON"


def test_trio_v_nalichii_pobezhdaet_daichi_dazhe_esli_daichi_deshevle():
    sources = build([trio_row("KSGHA21HFRN1/KSRHA21HFRN1", 40000)],
                    [oasis_row("daichi", "Kentatsu", DAICHI_TITLE, 30000, 3)])
    source, _, offer = sync.find_offer(sources, KENTATSU)
    assert source == "trio" and offer["dealer"] == 40000


def test_u_trio_net_na_sklade_a_u_daichi_est_berem_daichi():
    sources = build([trio_row("KSGHA21HFRN1/KSRHA21HFRN1", 40000, "нет")],
                    [oasis_row("daichi", "Kentatsu", DAICHI_TITLE, 45000, 3)])
    source, _, offer = sync.find_offer(sources, KENTATSU)
    assert source == "oasis" and offer["supplier"] == "daichi"


def test_u_trio_pozicii_net_berem_daichi():
    sources = build([], [oasis_row("daichi", "Kentatsu", DAICHI_TITLE, 45000, 3)])
    source, _, offer = sync.find_offer(sources, KENTATSU)
    assert source == "oasis" and offer["supplier"] == "daichi"


def test_ni_u_kogo_net_na_sklade_trio_vperedi():
    sources = build([trio_row("KSGHA21HFRN1/KSRHA21HFRN1", 40000, "под заказ")],
                    [oasis_row("daichi", "Kentatsu", DAICHI_TITLE, 30000, 0)])
    source, _, _ = sync.find_offer(sources, KENTATSU)
    assert source == "trio"


ROYAL = {"model": "ROYAL CLIMA RC-VNE28HN on/off", "brand": "ROYAL CLIMA", "group": "onoff"}
BREEZ_TITLE = "Классическая сплит-система серии VELA NUOVA RC-VNE28HN (комплект)"


def test_royal_clima_tolko_briz_dazhe_esli_u_trio_est_i_deshevle():
    sources = build([trio_row("RC-VNE28HN", 10000, section=32)],
                    [oasis_row("breeze", "ROYAL CLIMA", BREEZ_TITLE, 17000, 0)])
    source, _, offer = sync.find_offer(sources, ROYAL)
    assert source == "oasis" and offer["supplier"] == "breeze"


def test_royal_clima_net_u_briza_trio_ne_podstavlyaem():
    sources = build([trio_row("RC-VNE28HN", 10000, section=32)], [])
    assert sync.find_offer(sources, ROYAL) == (None, None, None)


def test_hisense_tolko_briz():
    product = {"model": "HISENSE AS-07HR4RYDDJ00 on/off", "brand": "HISENSE", "group": "onoff"}
    sources = build([trio_row("AS-07HR4RYDDJ00", 10000, section=29)], [])
    assert sync.find_offer(sources, product) == (None, None, None)


def test_rusklimat_ne_podklyuchen(tmp_path):
    csv_file = tmp_path / "oasis.csv"
    csv_file.write_text(
        "rusklimat|R-1|BALLU|BALLU BSAGI-07HN8|x|100|100|Симферополь|5\n"
        "daichi|D-1|Kentatsu|Kentatsu KSGHA21HFRN1|x|100|0|Симферополь|5\n",
        encoding="utf-8")
    rows = sources_oasis.load(csv_file)
    assert [row["supplier"] for row in rows] == ["daichi"]


def test_korotkiy_kod_karto4ki_nahodit_stroku_trio():
    # Карточка «DAICHI SIB25» (код так записан у Техносистемса), у трио «SIB25AVQS1R/SIB25FVS1R»:
    # трио в наличии — оно должно участвовать в выборе, а не оставаться «без карточки».
    sources = build([trio_row("SIB25AVQS1R/SIB25FVS1R", 43750, section=27)], [])
    product = {"model": "DAICHI SIB25", "brand": "DAICHI", "group": "inv"}
    source, _, offer = sync.find_offer(sources, product)
    assert source == "trio" and offer["dealer"] == 43750


def test_zapasnoy_poisk_trio_ne_trogaet_krepezh():
    # «Гайка М10» на сайте — упаковка 50 шт. по реестру расходников; у трио строка «Гайка М10 ОЦ.»
    # за штуку (3 ₽). Короткий код нельзя цеплять к ней обычным поиском: цена упала бы до 5 ₽.
    sources = build([trio_row("Гайка М10 ОЦ.", 3.0, section=412)], [])
    product = {"model": "Гайка М10", "brand": "Гайка М8", "group": "rashod"}   # как в боевом каталоге
    assert sync._offer_in(sources, "trio", product) is None


def test_zapasnoy_poisk_trio_ne_ceplyaet_polnyy_kod():
    # «MIDEA MCD1-55HRFNX(GA)-B» — полный код; у трио под ним другая пара блоков и цена
    sources = build([trio_row("MCD1-55HRFNX(GA)-B/MOE30U-55HFN8-R(GA)", 186000, section=25)], [])
    product = {"model": "MIDEA MCD1-55HRFNX(GA)-B", "brand": "MIDEA", "group": "pac_inv"}
    assert sync._offer_in(sources, "trio", dict(product, model="MIDEA MCD1-55HRFNX(GA)-Z")) is None
