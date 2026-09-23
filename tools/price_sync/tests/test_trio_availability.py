# -*- coding: utf-8 -*-
"""Наличие у трио.рус и как оно показывается у нас.

Формат владельца (23.09.2026): есть → «В наличии»; МСК → «7 дней»; под заказ →
«Под заказ · от 7 дней»; нет → «Нет в наличии». «Ожидается» — тоже под заказ.

Раньше парсер знал три класса, а для «ожидается» имя класса было угадано
(product_wait вместо настоящего product_expected), МСК не учитывался вовсе —
69 позиций молча уходили в «Под заказ».
"""
import pytest

from tools.price_sync import sources_trio

ROW = """
<table class="main-container-table"><tr class="line_tr">
  <td class="{cell}"><p>MSAG1-09HRN8-I/MSAG1-09HRN8-O <span class="{span}">{text}</span></p></td>
  <td class="line_tr {cell}"><div class="price">20 315,00</div></td>
</tr></table>
"""


def parse_one(span, text, cell):
    rows = sources_trio.parse(ROW.format(span=span, text=text, cell=cell), "bytovye-kondicionery", 25)
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize("span, text, cell, stock", [
    ("product_available", "есть",       "background_y", "in_stock"),   # зелёный
    ("product_no",        "нет",        "background_n", "out"),        # красный
    ("product_expected",  "ожидается",  "background_m", "order_7"),    # под заказ
    ("product_zakaz",     "под заказ",  "background_z", "order_7"),    # под заказ, от 7 дней
    ("product_zakaz",     "по запросу", "background_z", "order_7"),
    ("product_msk",       "Мск",        "background_w", "days_7"),     # склад Москвы → 7 дней
])
def test_pyat_sostoyaniy_trio(span, text, cell, stock):
    offer = parse_one(span, text, cell)
    assert sources_trio.stock_of(offer)[0] == stock


def test_model_ne_zahvatyvaet_tekst_nalichiya():
    offer = parse_one("product_msk", "Мск", "background_w")
    assert offer["model"] == "MSAG1-09HRN8-I/MSAG1-09HRN8-O"


def test_neznakomyy_klass_uznaetsya_po_tekstu():
    # Трио поменяет имя класса — состояние всё равно узнаётся по видимой подписи.
    offer = parse_one("product_whatever_new", "Мск", "background_w")
    assert sources_trio.stock_of(offer)[0] == "days_7"


def test_sovsem_neznakomoe_sostoyanie_ne_vydaetsya_za_nalichie():
    offer = parse_one("product_mystery", "загадка", "background_q")
    assert offer["availability"] == "?"
    assert sources_trio.stock_of(offer)[0] == "order_7"


def test_podpisi_kak_velel_vladelec():
    assert sources_trio.STOCK_MAP["мск"] == ("days_7", "7 дней")
    assert sources_trio.STOCK_MAP["под заказ"] == ("order_7", "Под заказ от 7 дней")
    assert sources_trio.STOCK_MAP["есть"] == ("in_stock", "В наличии")
    assert sources_trio.STOCK_MAP["нет"] == ("out", "Нет в наличии")
