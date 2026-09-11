# -*- coding: utf-8 -*-
"""Сведение каталога: проверка не должна пропускать битые карточки на сайт."""
from tools.price_sync import merge


def card(**overrides):
    base = {field: "x" for field in merge.REQUIRED_FIELDS}
    base.update({"id": "1", "sku": "a", "price": 100, "benefits": [], "area": 20,
                 "brand": "DENKO", "model": "DENKO DU-09"})
    base.update(overrides)
    return base


EXISTING = [card(id="100", sku="old-1", model="БИРЮСА B-09")]


def test_novaya_kartochka_dobavlyaetsya():
    merged, skipped = merge.merge(EXISTING, [card(id="200", sku="new-1")])
    assert len(merged) == 2 and not skipped


def test_bez_ceny_otkladyvaetsya():
    merged, skipped = merge.merge(EXISTING, [card(id="200", sku="new-1", price=0)])
    assert len(merged) == 1
    assert skipped[0]["reason"] == "нет цены в прайсе"


def test_zanyatyy_id_otkladyvaetsya():
    merged, skipped = merge.merge(EXISTING, [card(id="100", sku="new-1")])
    assert len(merged) == 1 and skipped[0]["reason"] == "id уже занят"


def test_zanyatyy_sku_otkladyvaetsya():
    merged, skipped = merge.merge(EXISTING, [card(id="200", sku="old-1")])
    assert len(merged) == 1 and skipped[0]["reason"] == "sku уже занят"


def test_povtornoe_svedenie_ne_dublit():
    once, _ = merge.merge(EXISTING, [card(id="200", sku="new-1")])
    twice, skipped = merge.merge(once, [card(id="200", sku="new-1")])
    assert len(twice) == 2 and len(skipped) == 1


def test_validaciya_lovit_dubli_id():
    problems = merge.validate([card(id="1", sku="a"), card(id="1", sku="b")])
    assert any("повторяются id" in p for p in problems)


def test_validaciya_lovit_nulevuyu_cenu():
    assert any("некорректная цена" in p for p in merge.validate([card(price=0)]))


def test_validaciya_lovit_nehvatku_polya():
    broken = card()
    del broken["freon"]
    assert any("нет полей freon" in p for p in merge.validate([broken]))


def test_validaciya_lovit_ne_spisok_benefits():
    assert any("benefits должен быть списком" in p for p in merge.validate([card(benefits="нет")]))


def test_chistyy_katalog_bez_zamechaniy():
    assert merge.validate([card(id="1", sku="a"), card(id="2", sku="b")]) == []


def test_foto_iz_boevogo_kataloga_schitaetsya_suschestvuyuschim(tmp_path):
    base = [card(id="100", sku="old-1", photo="eurohoff-callisto.webp")]
    merged = base + [card(id="200", sku="new-1", photo="eurohoff-callisto.webp")]
    assert merge.missing_photos(merged, base, tmp_path) == []


def test_novoe_foto_popadaet_v_spisok_na_syomku(tmp_path):
    base = [card(id="100", sku="old-1", photo="eurohoff-callisto.webp")]
    merged = base + [card(id="200", sku="new-1", photo="denko-tcl-on-off.webp")]
    assert merge.missing_photos(merged, base, tmp_path) == ["denko-tcl-on-off.webp"]
