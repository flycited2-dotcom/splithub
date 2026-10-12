# -*- coding: utf-8 -*-
"""Сведение каталога: проверка не должна пропускать битые карточки на сайт."""
import json

from tools.price_sync import merge, sync


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


def test_sborka_beryot_tekst_rashodnikov_iz_reestra(tmp_path):
    # у кронштейнов в боевом каталоге «400-420-1,6» и «400-420-1,7» — растянутые ячейки Excel
    old = card(id="1064", sku="kronshtein-400-420-1,5", model="Кронштейн-400-420-1,5",
               cardBenef="400-420-1,6", benefits=["400-420-1,7"], photo="kronshtein.webp")
    (tmp_path / "products.js").write_text(sync.render_products_js([old]), encoding="utf-8")
    registry = {"kronshtein-400-420-1,5": {
        "sku": "kronshtein-400-420-1,5", "section": 48, "trio": "Кронштейны 400x420, S=1,50мм",
        "card": {"model": "Кронштейны 400×420, 1,5 мм", "cardBenef": "Крашеные · 400×420 · 1,5 мм",
                 "benefits": ["Размер 400×420 мм", "Толщина металла 1,5 мм"]}}}
    result = merge.build(tmp_path, tmp_path / "assets", registry)
    assert result["written"] and result["rashod_text"] == 1
    built = sync.parse_products_js((tmp_path / "catalog" / "products.js").read_text(encoding="utf-8"))
    assert built[0]["model"] == "Кронштейны 400×420, 1,5 мм"
    assert built[0]["benefits"] == ["Размер 400×420 мм", "Толщина металла 1,5 мм"]
    assert built[0]["price"] == 100


def test_foto_iz_boevogo_kataloga_schitaetsya_suschestvuyuschim(tmp_path):
    base = [card(id="100", sku="old-1", photo="eurohoff-callisto.webp")]
    merged = base + [card(id="200", sku="new-1", photo="eurohoff-callisto.webp")]
    assert merge.missing_photos(merged, base, tmp_path) == []


def test_novoe_foto_popadaet_v_spisok_na_syomku(tmp_path):
    base = [card(id="100", sku="old-1", photo="eurohoff-callisto.webp")]
    merged = base + [card(id="200", sku="new-1", photo="denko-tcl-on-off.webp")]
    assert merge.missing_photos(merged, base, tmp_path) == ["denko-tcl-on-off.webp"]


def test_bez_napolneniya_otkladyvaetsya():
    # Карточка без описания на сайт не идёт: пустая карточка хуже, чем никакой.
    merged, skipped = merge.merge(EXISTING, [card(id="200", sku="new-1", cardBenef="")])
    assert len(merged) == 1 and skipped[0]["reason"] == "нет наполнения"


def test_bez_foto_otkladyvaetsya_kogda_izvesten_spisok_foto():
    merged, skipped = merge.merge(EXISTING, [card(id="200", sku="new-1", photo="novoe.webp")],
                                  photos={"est.webp"})
    assert len(merged) == 1 and skipped[0]["reason"] == "нет фото"
    merged, skipped = merge.merge(EXISTING, [card(id="200", sku="new-1", photo="est.webp")],
                                  photos={"est.webp"})
    assert len(merged) == 2 and not skipped


def test_na_servere_foto_proveryaetsya_na_sayte(tmp_path, monkeypatch):
    # На сервере сверки папки assets нет: новая карточка идёт на сайт, только если её
    # снимок уже лежит на splithub.ru, иначе покупатель увидит битое фото.
    (tmp_path / "products.js").write_text(sync.render_products_js(EXISTING), encoding="utf-8")
    new = [card(id="200", sku="new-1", photo="est.webp"),
           card(id="201", sku="new-2", photo="net.webp")]
    (tmp_path / "new_cards_draft.json").write_text(
        json.dumps(new, ensure_ascii=False), encoding="utf-8")
    asked = []

    class Answer:
        def __init__(self, code):
            self.status_code = code

    def head(url, timeout, allow_redirects):
        asked.append(url)
        return Answer(200 if url.endswith("/est.webp") else 404)

    monkeypatch.setattr(merge.requests, "head", head)
    result = merge.build(tmp_path, "https://splithub.ru/assets/img/products/", {})
    assert result["written"]
    assert [c["sku"] for c in result["merged"]] == ["old-1", "new-1"]
    assert result["skipped"][0]["reason"] == "нет фото"
    assert result["photos"] == ["net.webp"]
    assert sorted(asked) == ["https://splithub.ru/assets/img/products/est.webp",
                             "https://splithub.ru/assets/img/products/net.webp"]
