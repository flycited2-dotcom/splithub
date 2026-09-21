# -*- coding: utf-8 -*-
"""Прайс поставщика трио.рус (Bitrix, server-rendered, без авторизации).

Страницы отдаются обычным GET. В таблице `table.main-container-table`: модель +
наличие (`span.product_available|product_no|product_zakaz|product_wait`) и цена
(`div.price`; при акции — `div.old_price` + `div.price_promotion`).
"""
from __future__ import annotations

import re
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://xn--h1ameh.xn--p1acf"

#: Раздел → список SECTION_ID (None = страница без параметра).
#: Подразделы взяты из меню самих страниц: без них отдаётся только первый бренд.
PAGES = {
    "bytovye-kondicionery": [22, 25, 24, 27, 26, 29, 32, 34],
    "polupromyshlennye-kondicionery": [35, 36, 42, 508, 37, 40, 41, 38, 39],
    "multisplit-sistemy": [43, 44, 45, 46, 199, 200],
    "raskhodnye-materialy": [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 407],
    "ventilyatory-kanalnye-osevye": [None],
    "krepezh": [412],
}

#: CSS-класс наличия → наш код наличия. Сверено с живой разметкой трио 21.09.2026:
#: у них пять состояний и пять цветов строки — есть (зелёный), нет (красный),
#: ожидается (синий), под заказ / по запросу (серый), Мск (фиолетовый).
AVAILABILITY = {
    "product_available": "есть",
    "product_no": "нет",
    "product_zakaz": "под заказ",
    "product_expected": "ожидается",
    "product_msk": "мск",
}

#: Запасной путь — по видимой подписи. Поменяет трио имя класса — состояние
#: всё равно узнаем, а не уроним молча в «под заказ», как было с «ожидается».
AVAILABILITY_BY_TEXT = {
    "есть": "есть",
    "нет": "нет",
    "под заказ": "под заказ",
    "по запросу": "под заказ",
    "ожидается": "ожидается",
    "мск": "мск",
}


def _availability(marker) -> str:
    """Наличие по span-метке. «?» — метка есть, но мы её не узнали."""
    by_class = AVAILABILITY.get(" ".join(marker.get("class") or []))
    if by_class:
        return by_class
    return AVAILABILITY_BY_TEXT.get(marker.get_text(strip=True).lower(), "?")

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _money(text: str):
    cleaned = text.replace("\xa0", " ").replace(" ", "").replace(",", ".")
    found = _NUMBER.search(cleaned)
    return float(found.group(0)) if found else None


def _series_of(table):
    node = table
    for _ in range(6):
        node = node.find_previous(["h1", "h2", "h3", "h4"])
        if node is None:
            return ""
        if node.get_text(strip=True):
            return node.get_text(" ", strip=True)
    return ""


def parse(html: str, page: str, section) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for table in soup.select("table.main-container-table"):
        series = _series_of(table)
        for tr in table.select("tr.line_tr, tr.line_tr_price"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 2:
                continue
            marker = cells[0].find("span")
            availability = ""
            if marker is not None:
                availability = _availability(marker)
                marker.extract()
            model = cells[0].get_text(" ", strip=True)
            old, promo = cells[1].select_one(".old_price"), cells[1].select_one(".price_promotion")
            if old is not None and promo is not None:
                dealer = _money(old.get_text())
                promo_price = _money(promo.get_text(" ", strip=True).replace("Акция", ""))
            else:
                plain = cells[1].select_one(".price")
                dealer = _money(plain.get_text()) if plain else None
                promo_price = None
            if not model or dealer is None:
                continue
            rows.append({
                "source": "trio", "page": page, "section": section, "series": series,
                "model": model, "availability": availability,
                "dealer": dealer, "promo": promo_price,
            })
    return rows


def fetch(pause: float = 0.4) -> list[dict]:
    """Собрать все разделы прайса. Дубли (страница по умолчанию = SECTION_ID 22) исключены."""
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (splithub price-sync)"
    rows, seen = [], set()
    for page, sections in PAGES.items():
        for section in sections:
            url = BASE_URL + "/catalog/" + page + ("?SECTION_ID=%s" % section if section else "")
            response = session.get(url, timeout=40)
            response.raise_for_status()
            for row in parse(response.text, page, section):
                identity = (row["model"], row["dealer"], page)
                if identity in seen:
                    continue
                seen.add(identity)
                rows.append(row)
            time.sleep(pause)
    return rows


def cost_of(offer: dict) -> float:
    """Закупка: акционная цена, если акция идёт, иначе стандартная дилерская.

    В прайс трио в поле акции попадает мусор: у металлопластиковой трубы там цена
    за бухту (44 → «акция» 3800), у части кронштейнов — «акция 1,00». Поэтому
    акцией считаем только скидку в пределах половины дилерской цены.
    """
    dealer, promo = offer["dealer"], offer.get("promo")
    if promo and dealer / 2 <= promo <= dealer:
        return promo
    return dealer


#: Наличие поставщика → (stock, stockLabel) каталога. Витрина повторяет цвета трио:
#: в наличии — зелёный, нет — красный, ожидается — синий, под заказ — серый,
#: Мск (склад в Москве, привезут за несколько дней) — фиолетовый.
STOCK_MAP = {
    "есть": ("in_stock", "В наличии"),
    "нет": ("out", "Нет в наличии"),
    "ожидается": ("wait", "Ожидается"),
    "под заказ": ("order_7", "Под заказ 7 дней"),
    "мск": ("days_3_5", "3–5 дней"),
}

#: Неизвестное или пустое состояние — честное «под заказ», а не «в наличии».
UNKNOWN_STOCK = ("order_7", "Под заказ 7 дней")


def stock_of(offer: dict) -> tuple[str, str]:
    return STOCK_MAP.get(offer.get("availability", ""), UNKNOWN_STOCK)
