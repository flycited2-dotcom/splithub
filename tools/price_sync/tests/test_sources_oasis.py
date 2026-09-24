# -*- coding: utf-8 -*-
import io

from tools.price_sync import sources_oasis

EXPORT = "\n".join([
    "rusklimat|NC-1|ULTIMA COMFORT|ELYSIUM ELB-I07PN|ELYSIUM|24900|16100|Симферополь|3",
    "daichi|NC-2|DAICHI|DAICHI ICE20AVQS1R-2|ICE|25900|0|Симферополь|5",
    "breez|NC-3|XIGMA|XIGMA XG-TX21RHA|TX|31000|0|Шерризон|4",
    "rusklimat|NC-4|LG|LG P07SP2|STANDARD|29900|19800||0",
]) + "\n"


def write(tmp_path):
    target = tmp_path / "oasis_stock.csv"
    io.open(target, "w", encoding="utf-8").write(EXPORT)
    return target


def test_chitaet_vygruzku(tmp_path):
    rows = sources_oasis.load(write(tmp_path))
    assert len(rows) == 4
    assert sources_oasis.model_of(rows[0]) == "ELYSIUM ELB-I07PN"


def test_net_faila_ne_padaet(tmp_path):
    assert sources_oasis.load(tmp_path / "нет-такого.csv") == []


def test_rusklimat_beret_price_base(tmp_path):
    rows = sources_oasis.load(write(tmp_path))
    assert sources_oasis.cost_of(rows[0]) == 16100.0     # не 24900 (это розница)


def test_daichi_beret_price_wholesale(tmp_path):
    rows = sources_oasis.load(write(tmp_path))
    assert sources_oasis.cost_of(rows[1]) == 25900.0


def test_breez_bez_klyucha_ceny_ne_daet(tmp_path):
    # в БД у Бриза розница — наценку на неё накладывать нельзя
    rows = sources_oasis.load(write(tmp_path))
    assert sources_oasis.cost_of(rows[2]) == 0.0


def test_nalichie_krym_i_materik(tmp_path):
    rows = sources_oasis.load(write(tmp_path))
    assert sources_oasis.stock_of(rows[0]) == ("in_stock", "В наличии")
    # склад Бриза вне Крыма — «Под заказ 7 дней» (владелец 24.09.2026), но остаток реальный
    assert sources_oasis.stock_of(rows[2]) == ("order_7", "Под заказ 7 дней")
    assert sources_oasis.stock_rank(rows[2]) == 2
    assert sources_oasis.stock_of(rows[3]) == ("order_7", "Под заказ 7 дней")
    assert sources_oasis.stock_rank(rows[3]) == 4


BREEZ_JSON = """{"NC-3": {"nc": "NC-3", "price": [{"base": 21500}, {"ric": 31000}]}}"""


def test_breez_beret_opt_iz_api(tmp_path):
    io.open(tmp_path / "breez_base.json", "w", encoding="utf-8").write(BREEZ_JSON)
    rows = sources_oasis.load(write(tmp_path), tmp_path / "breez_base.json")
    assert sources_oasis.cost_of(rows[2]) == 21500.0    # опт из API, не розница 31000


def test_breez_bez_vygruzki_ostaetsya_nulem(tmp_path):
    rows = sources_oasis.load(write(tmp_path), tmp_path / "нет.json")
    assert sources_oasis.cost_of(rows[2]) == 0.0
