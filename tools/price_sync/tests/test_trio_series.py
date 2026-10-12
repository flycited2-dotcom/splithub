# -*- coding: utf-8 -*-
"""Серия и фото серии у трио: блоки title-section / image-section перед таблицей."""
from tools.price_sync import sources_trio

PAGE = """
<div class="main">
  <div class="title-section">Сплит-системы Midea PRIMARY On/off</div>
  <div class="image-section"><img class="image" src="/upload/iblock/147/a.png"/></div>
  <div class="main_container"><table class="main-container-table">
    <tr class="line_tr"><td><p>MSAG3-07HRN8-I/MSAG3-07HRN8-О <span class="product_available">есть</span></p></td>
    <td><div class="price">18 615,00</div></td></tr></table></div>
  <div class="title-section">Сплит-системы Midea BREEZELESS E (MSFE) Inverter (обогрев -20)</div>
  <div class="image-section"><img class="image" src="/upload/iblock/695/b.png"/></div>
  <div class="main_container"><table class="main-container-table">
    <tr class="line_tr"><td><p>MSFE1S-12FRN8G1-I/MOFE1-12FRN8G1-O <span class="product_available">есть</span></p></td>
    <td><div class="price">38 165,00</div></td></tr></table></div>
</div>
"""


def test_seriya_beretsya_iz_bloka_nad_tablicey():
    rows = sources_trio.parse(PAGE, "bytovye-kondicionery", 25)
    assert [r["series"] for r in rows] == [
        "Сплит-системы Midea PRIMARY On/off",
        "Сплит-системы Midea BREEZELESS E (MSFE) Inverter (обогрев -20)",
    ]


def test_foto_serii_polnym_adresom():
    rows = sources_trio.parse(PAGE, "bytovye-kondicionery", 25)
    assert rows[1]["image"] == sources_trio.BASE_URL + "/upload/iblock/695/b.png"
