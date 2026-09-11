# -*- coding: utf-8 -*-
import io

from tools.price_sync import sources_techno

PRICE = "\n".join([
    "бренд;серия;модель;категория;цена_1;цена_2;наличие;примечание",
    "EUROHOFF;ASTRID (Midea);AVE-07M;настенный;15500;14300;есть;",
    "EUROHOFF;CALLISTO inverter (Midea);EM-24I;настенный;54000;;есть;",
    "DENKO;Канальные on/off (TCL);DKN-36A;канальный;;;под заказ;цена не указана",
    "YUETU;GMCC on/off;YEL-07IN/OUT;настенный;11200;10900;есть;",
]) + "\n"


def price_file(tmp_path):
    target = tmp_path / "technosystems_price.csv"
    io.open(target, "w", encoding="utf-8-sig").write(PRICE)
    return target


def test_chitaet_prays(tmp_path):
    rows = sources_techno.load(price_file(tmp_path))
    assert len(rows) == 4
    assert sources_techno.model_of(rows[0]) == "AVE-07M"


def test_beret_bolshuyu_iz_dvuh_cen(tmp_path):
    # правило владельца: из «15 500 / 14 300» основой служит 15 500
    rows = sources_techno.load(price_file(tmp_path))
    assert sources_techno.cost_of(rows[0]) == 15500.0


def test_odna_cena_beretsya_kak_est(tmp_path):
    rows = sources_techno.load(price_file(tmp_path))
    assert sources_techno.cost_of(rows[1]) == 54000.0


def test_utochnyayte_bez_ceny(tmp_path):
    rows = sources_techno.load(price_file(tmp_path))
    assert sources_techno.cost_of(rows[2]) == 0.0


def test_slesh_v_modeli_ne_cena(tmp_path):
    # «YEL-07IN/OUT» — это внутренний/наружный блок, а не две цены
    rows = sources_techno.load(price_file(tmp_path))
    assert rows[3]["model"] == "YEL-07IN/OUT"
    assert sources_techno.cost_of(rows[3]) == 11200.0


def test_nalichie(tmp_path):
    rows = sources_techno.load(price_file(tmp_path))
    assert sources_techno.stock_of(rows[0]) == ("in_stock", "В наличии")
    assert sources_techno.stock_of(rows[2]) == ("order_7", "Под заказ 7 дней")


def test_net_faila_ne_padaet(tmp_path):
    assert sources_techno.load(tmp_path / "нет.csv") == []


def test_boevoy_prays_chitaetsya():
    rows = sources_techno.load()
    assert len(rows) > 50
    assert all(row["brand"] for row in rows)
    assert all(sources_techno.cost_of(row) >= 0 for row in rows)
