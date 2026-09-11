# -*- coding: utf-8 -*-
"""Дюбели, болты и гайки с прессшайбой от трио идут с наценкой 100%.

Остальная мелочёвка — глухари, шайбы, обычные гайки, кронштейны — на общих 10%.
"""
import pytest

from tools.price_sync import pricing, sync


def product(brand, model):
    return {"brand": brand, "model": model, "group": "rashod"}


@pytest.mark.parametrize("brand, model", [
    ("Дюбель 6х40", "Дюбель 6х40"),
    ("Дюбель", "Дюбель распорн KPO 12х80(50шт)"),
    ("Болт 8-25", "Болт 8-25"),
    ("Болт 8-35", "Болт 8-35"),
    ("Гайка М8-пресшайба", "Гайка М8-пресшайба"),
])
def test_sto_procentov(brand, model):
    assert sync.price_source("trio", product(brand, model)) == "trio_krepezh"


@pytest.mark.parametrize("brand, model", [
    ("Глухарь", "Глухарь 8-100мм(50шт)"),
    ("шайба м8 увеличенная", "шайба м8 увеличенная"),
    ("Гайка М8", "Гайка М10"),
    ("Кронштейны", "Кронштейн-400-420-1,5"),
    ("Медная труба", "Медная труба 1/4 · бухта 15 м"),
])
def test_ostayutsya_na_desyati(brand, model):
    assert sync.price_source("trio", product(brand, model)) == "trio_rashod"


def test_tehnika_ne_zadeta():
    split = {"brand": "БИРЮСА", "model": "БИРЮСА B-09FPR/B-09FPQ on/off", "group": "onoff"}
    assert sync.price_source("trio", split) == "trio"


def test_nacenka_sto_procentov():
    assert pricing.MARKUP["trio_krepezh"] == 1.00
    assert pricing.compute_price(170, "trio_krepezh") == 340     # болт 8-25, упаковка 50 шт
    assert pricing.compute_price(100, "trio_krepezh") == 200     # гайка М8-прессшайба
