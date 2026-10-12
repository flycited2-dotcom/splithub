# -*- coding: utf-8 -*-
"""Прайс Техносистемса без ручной правки (владелец 12.10.2026: «через токен»).

Источники: их Google-таблица (прайс + складские остатки) и посты их Telegram-канала,
которые читает личный Telegram владельца. Строки ниже — живые, из таблицы и постов.
"""
from tools.price_sync import techno_live

SHEET = """Марка,Модель,Цена,НАЛИЧИЕ
DAICHI ICE -15С INVERTOR,ICE20AVQS1R2,25 900 ₽,В наличии
,ICE50AVQS1R2,55 700 ₽,В наличии
,Модель,,-
DANTEX   on|off          завод GREE   ,RK-07SCDG/07SCDGE,18650 /  17850,В наличии
DANTEX завод GREE concord inverter,RK-07SCDGI/07SCDGIE,29 000 ₽,В наличии
DANTEX завод GREE серия concord,RK-07SCDG/07SCDGE,,В наличии
DANTEX завод TCL Advance invertor,RK-12SATI PLUS/12SATIE,31 100 / 27 100 ₽,В наличии
EUROHOFF,Серия Astrid (Мidea),,-
,Eurohoff AVE-07M,15500 / 14 300,В наличии
,Eurohoff EM -07I,23300 / 20 700,В наличии
,Denko DU-07,14 200 / 12 700 ₽,В наличии
,Denko DU-07 inverter,20 000 / 18800 ₽,-
,Denko QW-07inv,18000 ₽,В наличии
MARSA,завод TСL,,-
,RK-12MTA4/RK-12MTA4E,22100 / 18 600,В наличии
,DAICHI DA70BLHS1R1/DF70BLS1R1 кан inv,72000 (GREE),В наличии
,Eurohoff EV-NP 36M нап пот,77 400,В наличии
,DENKO MULT-18/2 нар блок,43 300 39 200,-
,DENKO MULT-07 внут блок,10 000 9500,В наличии
,YEL-07 IN/YEL-07 OUT,11200 / 10900,В наличии
"""

STOCK = """,
Остатки товаров на складах,
06.10.26,
Товар,1 Основной склад
,Остаток
DAICHI,
ICE20AVQS1R/ICE20FVS1R 2inv (шт.),6
ICE20AVQS1R1-1 вн.блок мульти (шт.),2
ICE50AVQS1R/ICE50FVS1R 2inv (шт.),1
DENKO,
Denko DU-07 (шт.),6
Denko MULT-07 внут блок (шт.),7
EUROHOFF,
Eurohoff EM -07i inv (шт.),5
RK-07SAT/07SATE (шт.),
"""

CSV_ROWS = [
    {"brand": "DAICHI", "series": "ICE (-15°C inverter)", "model": "ICE20", "category": "настенный"},
    {"brand": "DAICHI", "series": "ICE (-15°C inverter)", "model": "ICE50", "category": "настенный"},
    {"brand": "DANTEX", "series": "Gree on/off", "model": "RK-07SCDG/E", "category": "настенный"},
    {"brand": "DANTEX", "series": "CONCORD inverter (Gree)", "model": "RK-07SCDGI/E", "category": "настенный"},
    {"brand": "EUROHOFF", "series": "CALLISTO inverter (Midea)", "model": "EM-07I", "category": "настенный"},
    {"brand": "DENKO", "series": "TCL on/off", "model": "DU-07", "category": "настенный"},
    {"brand": "DENKO", "series": "TCL inverter", "model": "DU-07 inv", "category": "настенный"},
    {"brand": "DENKO", "series": "Мультисплит внутренние блоки", "model": "MULT-07",
     "category": "мультисплит внутренний"},
    {"brand": "MARSA", "series": "TCL", "model": "12MTA3/E", "category": "настенный"},
]


def rows():
    names = {"brand": "бренд", "series": "серия", "model": "модель", "category": "категория"}
    return [dict({names[k]: v for k, v in row.items()},
                 **{"цена_1": "", "цена_2": "", "наличие": "", "примечание": ""}) for row in CSV_ROWS]


def test_ceny_iz_tablicy():
    entries = techno_live.parse_sheet(SHEET)
    by = {}
    for e in entries:
        by.setdefault(e["model"], e)
    assert by["ICE20AVQS1R2"]["prices"] == [25900.0]
    assert by["RK-07SCDG/07SCDGE"]["prices"] == [18650.0, 17850.0]
    assert by["DENKO MULT-18/2 нар блок"]["prices"] == [43300.0, 39200.0]
    assert by["DENKO MULT-07 внут блок"]["prices"] == [10000.0, 9500.0]
    assert by["DAICHI DA70BLHS1R1/DF70BLS1R1 кан inv"]["prices"] == [72000.0]
    # подзаголовки и строки «Модель» — не товары
    assert "Серия Astrid (Мidea)" not in by and "Модель" not in by


def test_ostatki_s_datoy():
    date, stock = techno_live.parse_stock(STOCK)
    assert date == "2026-10-06"
    assert any(s["qty"] == 6 for s in stock)


def test_klyuch_modeli():
    k = techno_live.model_key
    assert k("Denko DU-07 inverter") == ("DU07", True)
    assert k("DU-07 inv") == ("DU07", True)
    assert k("Denko QW-07inv") == ("QW07", True)
    assert k("Eurohoff EM -07I") == ("EM07I", False)
    assert k("RK-07SCDG/07SCDGE") == ("RK07SCDG", False)
    assert k("YEL-07 IN/YEL-07 OUT") == ("YEL07", False)
    assert k("Eurohoff EV-NP 36M нап пот") == ("EVNP36M", False)
    assert k("EUD100W1/T1") != k("Eurohoff EUD100W1/ZD1 inv нап пот")
    assert k("YEL-07IN/OUT")[0] == k("YEL-07 IN/YEL-07 OUT")[0] == "YEL07"
    assert k("Denko DNP-36A- I нап-пот. invert") == ("DNP36AI", True)


def test_obnovlenie_cen_i_nalichiya():
    sheet = techno_live.parse_sheet(SHEET)
    _, stock = techno_live.parse_stock(STOCK)
    result, report = techno_live.refresh(rows(), sheet, stock)
    by = {r["модель"]: r for r in result}
    assert by["ICE50"]["цена_1"] == "55700" and by["ICE50"]["наличие"] == "есть"
    # точное совпадение важнее вхождения: on/off не берёт цену concord inverter
    assert by["RK-07SCDG/E"]["цена_1"] == "18650"
    assert by["RK-07SCDGI/E"]["цена_1"] == "29000"
    # остаток по складу: DU-07 6 шт. — есть, DU-07 inv в остатках нет — под заказ
    assert by["DU-07"]["наличие"] == "есть"
    assert by["DU-07 inv"]["наличие"] == "под заказ"
    assert by["DU-07 inv"]["цена_1"] == "20000"
    # мультисплит внутренний блок не путается с настенным ICE20…-1 «вн.блок мульти»
    assert by["MULT-07"]["наличие"] == "есть"
    assert by["ICE20"]["наличие"] == "есть"
    assert by["EM-07I"]["наличие"] == "есть"
    # новая ревизия MARSA (MTA4) — в отчёт как новая позиция, старая строка без цены
    assert by["12MTA3/E"]["цена_1"] == ""
    assert any("RK-12MTA4" in n["model"] for n in report["new"])


def test_invertor_bez_metki_v_ostatkah_esli_net_dvoynika():
    # «Eurohoff EUD100W1/T1 касс» в остатках без «inv», а в реестре — кассетный инвертор
    rows_ = [{"бренд": "EUROHOFF", "серия": "Кассетные inverter (Gree)", "модель": "EUD100W1/T1",
              "категория": "кассета", "цена_1": "", "цена_2": "", "наличие": "", "примечание": ""}]
    stock = [{"model": "Eurohoff EUD100W1/T1 касс", "qty": 2}]
    result, _ = techno_live.refresh(rows_, [], stock)
    assert result[0]["наличие"] == "есть"


def test_novaya_poziciya_dobavlyaetsya_v_reestr():
    sheet = techno_live.parse_sheet(SHEET)
    result, report = techno_live.refresh(rows(), sheet, [])
    added = [r for r in result if r["модель"] == "RK-12MTA4/RK-12MTA4E"]
    assert added and added[0]["бренд"] == "MARSA" and added[0]["категория"] == "настенный"
    assert added[0]["цена_1"] == "22100"


POST = """🔥 ПРАЙС НА КОНДИЦИОНЕРЫ
❄️ DAICHI ICE (-15°C Inv)
ICE20 — 25 900 ₽ ✅ | ICE25 — 28 450 ₽ ✅
ICE35 — 31 650 ₽ ✅ | ICE50 — 57 650 ₽ ✅
🔹 DENKO (TCL) Inv
DU-07 inv — 20 000 / 18 800 ₽
DU-09 inv — 21 400 / 20 000 ₽ ✅
DNP-36A..60A — уточняйте
DKN-36A — под заказ
"""


def test_razbor_posta():
    entries = techno_live.parse_post(POST)
    by = {e["model"]: e for e in entries}
    assert by["ICE50"]["prices"] == [57650.0] and by["ICE50"]["in_stock"] is True
    assert by["DU-07 inv"]["prices"] == [20000.0, 18800.0] and by["DU-07 inv"]["in_stock"] is False
    assert by["DKN-36A"]["prices"] == []
    assert "DNP-36A..60A" not in by


def test_svezhiy_post_perebivaet_tablicu():
    sheet = techno_live.parse_sheet(SHEET)
    post = techno_live.parse_post(POST)
    result, _ = techno_live.refresh(rows(), sheet, [], overrides=post)
    by = {r["модель"]: r for r in result}
    assert by["ICE50"]["цена_1"] == "57650"


def test_novye_posty_kanala():
    state = {"tg_last_id": 255, "overrides": []}
    posts = [{"id": 255, "date": "2026-08-31T15:33:41+00:00", "text": POST},
             {"id": 270, "date": "2026-10-20T09:00:00+00:00", "text": POST},
             {"id": 271, "date": "2026-10-20T09:01:00+00:00", "text": "", "media": "photo"}]
    overrides, notes = techno_live.read_posts(state, posts, "2026-10-20T10:00:00+00:00")
    assert state["tg_last_id"] == 271
    assert any(o["model"] == "ICE50" for o in overrides)
    assert len(notes) == 2 and "прайс" in notes[0] and "картинку" in notes[1]
    # повторный прогон тех же постов ничего не добавляет
    _, again = techno_live.read_posts(state, posts, "2026-10-21T10:00:00+00:00")
    assert again == []


def test_bukva_versii_v_ostatkah():
    rows_ = [{"бренд": "MARSA", "серия": "TCL", "модель": "RK-12MTA4/RK-12MTA4E", "категория": "настенный",
              "цена_1": "", "цена_2": "", "наличие": "", "примечание": ""},
             {"бренд": "DANTEX", "серия": "Gree on/off", "модель": "RK-07SCDG/E", "категория": "настенный",
              "цена_1": "", "цена_2": "", "наличие": "", "примечание": ""}]
    stock = [{"model": "MARSA RK-12MTA4G/RK-12MTA4EG", "qty": 67},
             {"model": "RK-07SCDGI/07SCDGIEinv", "qty": 4}]
    result, _ = techno_live.refresh(rows_, [], stock)
    assert result[0]["наличие"] == "есть"
    assert result[1]["наличие"] == "под заказ"     # «I» — инвертор, это другой товар
