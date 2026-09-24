# -*- coding: utf-8 -*-
"""Сопоставление моделей каталога с прайсами поставщиков.

Две ловушки реальных данных:
1. Поставщики печатают ПАРУ блоков («KSGHA21HFRN1/KSRHA21HFRN1»), каталог — только
   внутренний блок («KENTATSU KSGHA21HFRN1»).
2. В моделях встречаются кириллические гомоглифы: «В-07FIR» (Ве), «-О» (О).
"""
from __future__ import annotations

import re

#: Кириллические буквы, неотличимые от латинских, → латиница.
_HOMOGLYPHS = str.maketrans("АВСЕКМНОРТХУІЁ", "ABCEKMHOPTXYIE")
_NOISE = ("ONOFF", "INVERTER", "INV", "ВНУТРЕННИЙБЛОК", "ВНЕШНИЙБЛОК")
_SPLIT = re.compile(r"[/|+.]")
_KEEP = re.compile("[^A-Z0-9А-Я/|+.]+")


def normalize(text: str) -> str:
    """Модель → сравнимый ключ: заглавные, без пробелов/дефисов и слов-шума."""
    s = text.upper().replace(chr(92), "/").translate(_HOMOGLYPHS)
    s = _KEEP.sub("", s)
    s = s.replace("ON/OFF", "")
    for word in _NOISE:
        s = s.replace(word, "")
    return s


def keys(model: str, brand: str = "") -> set[str]:
    """Все ключи, по которым позиция может совпасть с прайсом.

    Это сама строка, каждая её часть (блоки пары, хвост после точки) и пара
    «первый/второй». Точка важна для LG: у нас «H09S1D.NS1R», у поставщика — «H09S1D».
    """
    whole = normalize(model)
    prefix = normalize(brand)
    if prefix and whole.startswith(prefix):
        whole = whole[len(prefix):]
    parts = [p for p in _SPLIT.split(whole) if len(p) >= 4]
    result = {whole} | set(parts)
    if len(parts) >= 2:
        result.add(parts[0] + "/" + parts[1])
    return {k for k in result if k}


def build_index(offers, model_of):
    """Индекс «ключ → оффер». Первый оффер с данным ключом побеждает."""
    index = {}
    for offer in offers:
        for key in keys(model_of(offer)):
            index.setdefault(key, offer)
    return index


def lookup(index, model: str, brand: str = ""):
    """Найти оффер по модели каталога. Длинные ключи проверяются первыми."""
    for key in sorted(keys(model, brand), key=len, reverse=True):
        if key in index:
            return index[key]
    return None


def build_text_index(offers, text_of):
    """Список (нормализованный текст, оффер, исходный текст) для поиска вхождением."""
    return [(normalize(text_of(offer)), offer, text_of(offer)) for offer in offers]


def _whole_code(key: str, raw: str) -> bool:
    """Код стоит в названии целиком, а не началом более длинного кода.

    «…NEO Premium AS-10HW4SYDTG5 (комплект)» — да, «…BLACK CRYSTAL AS-10HW4SYDTG5B» — нет:
    нормализованный код входит в оба названия, но второе — другой товар (чёрный).
    """
    text = raw.upper().replace(chr(92), "/").translate(_HOMOGLYPHS)
    pattern = r"[\s\-_/.()]*".join(re.escape(char) for char in key)
    return re.search(r"(?<![A-Z0-9])" + pattern + r"(?![A-Z0-9])", text) is not None


def lookup_within(text_index, model: str, brand: str = "", min_length: int = 5):
    """Найти оффер, в названии которого встречается код нашей модели.

    Нужно для поставщиков с описательными названиями: у нас «ELYSIUM ELB-I07PN inv»,
    у них «Инверторные сплит-системы серии ELYSIUM Inverter ELB-I07PN». Ключи короче
    пяти символов отбрасываем — иначе «LG» поймает половину каталога.
    """
    candidates = [key for key in keys(model, brand) if len(key) >= min_length]
    ordered = sorted(candidates, key=len, reverse=True)
    # Точное совпадение сильнее вхождения: «MULT18» входит и в «MULT18/2» (наружный
    # блок), и совпадает с «MULT18» (внутренний). Без этого прохода внутреннему
    # блоку доставалась цена наружного — втрое дороже.
    for key in ordered:
        for text, offer, _ in text_index:
            if key == text:
                return offer
    for key in ordered:
        found = [(offer, raw) for text, offer, raw in text_index if key in text]
        if found:
            # Код входит и в чужой, более длинный код того же ряда — берём название,
            # где он стоит целиком; иначе NEO Premium получал цену BLACK CRYSTAL.
            whole = [offer for offer, raw in found if _whole_code(key, raw)]
            return whole[0] if whole else found[0][0]
    return None


def lookup_contained_in(text_index, model: str, brand: str = "", min_length: int = 5):
    """Обратный поиск: код поставщика — короче нашего, ищем его ВНУТРИ нашей модели.

    У Техносистемса в прайсе «ICE20», а в каталоге «DAICHI ICE20AVQS1R-2». Берём
    самое длинное совпадение, чтобы «DU-07» не победил «DU-07 inv».
    """
    mine = normalize(model)
    prefix = normalize(brand)
    if prefix and mine.startswith(prefix):
        mine = mine[len(prefix):]
    best = None
    for text, offer, _ in text_index:
        if len(text) >= min_length and text in mine:
            if best is None or len(text) > len(best[0]):
                best = (text, offer)
    return best[1] if best else None


def lookup_either(text_index, model: str, brand: str = ""):
    """Совпадение в любую сторону — код поставщика может быть и длиннее, и короче нашего.

    У Техносистемса в прайсе и «RK-07SCDG/E» (длиннее нашего «RK-07SCDG»), и «ICE20»
    (короче «DAICHI ICE20AVQS1R-2»). Одного направления не хватает.
    """
    return (lookup_within(text_index, model, brand)
            or lookup_contained_in(text_index, model, brand))
