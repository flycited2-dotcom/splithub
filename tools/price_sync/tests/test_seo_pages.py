# -*- coding: utf-8 -*-
"""SEO-страницы брендов, sitemap и SEO-разметка главной (без сети)."""
import html
import json
import re
from pathlib import Path

from tools.price_sync import publish, seo_pages

ROOT = Path(__file__).resolve().parents[3]


def ac(pid, brand="XIGMA", model=None, price=20000, stock="in_stock", group="inv",
       series="TURBOCOOL", btu="09", **extra):
    item = {"id": pid, "sku": "sku-" + pid, "brand": brand, "model": model or "XG-" + pid,
            "price": price, "stock": stock, "group": group, "series": series, "btu": btu,
            "area": 25, "photo": "x.webp"}
    item.update(extra)
    return item


def brand(slug):
    return next(b for b in seo_pages.BRANDS if b["slug"] == slug)


def jsonld(page):
    return json.loads(re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                                page, re.S).group(1))


# ── каталог ──────────────────────────────────────────────────────────────────

def test_pravki_adminki_kak_na_vitrine():
    products = [ac("1", price=20000), ac("2"), ac("3")]
    overrides = {"sku-1": {"price": "18990", "stock": "order_7"}, "sku-2": {"active": 0}}
    custom = [ac("9", model="XG-NEW"), ac("10", model="dup")]
    custom[1]["sku"] = "sku-3"                     # дубль sku каталога — не добавляем
    result = seo_pages.apply_overrides(products, overrides, custom)
    assert [p["id"] for p in result] == ["1", "3", "9"]
    assert result[0]["price"] == 18990 and result[0]["stock"] == "order_7"


def test_stranica_brenda_tolko_ego_konditsionery():
    products = [ac("1"), ac("2", brand="xigma "), ac("3", brand="DAICHI"),
                ac("4", brand="XIGMA", group="rashod"), ac("5", price=0),
                ac("6", brand="Медная труба", group="truba", btu="-")]
    assert [p["id"] for p in seo_pages.brand_items(products, brand("xigma"))] == ["1", "2"]
    assert [p["id"] for p in seo_pages.brand_items(products, brand("mednaya-truba"))] == ["6"]


def test_poryadok_po_seriyam_i_btu():
    products = [ac("1", series="B", btu="12"), ac("2", series="A", btu="18"),
                ac("3", series="B", btu="07"), ac("4", series="A", btu="09")]
    assert [p["id"] for p in seo_pages.brand_items(products, brand("xigma"))] == ["3", "1", "4", "2"]


# ── текст ────────────────────────────────────────────────────────────────────

def test_svodka_tolko_iz_dannyh():
    items = [ac("1", price=13890, btu="07", freon="R32", compressor="GMCC"),
             ac("2", price=20990, btu="24", group="onoff", stock="order_7", color="black")]
    text = seo_pages.summary_paragraph(brand("xigma"), seo_pages.facts(items))
    assert "2 позиции XIGMA, из них 1 в наличии" in text
    assert "инверторные и On/Off" in text
    assert "от 07 до 24 BTU" in text
    assert "чёрном корпусе" in text
    assert "13 890 ₽ за комплект" in text
    assert "полупром" not in text.lower()


def test_svodka_truby():
    items = [ac("1", brand="Медная труба", group="truba", btu="-", series="Средняя 15 м.",
                model="Медная труба 1/4 · бухта 15 м", price=2490),
             ac("2", brand="Медная труба", group="truba", btu="-", series="Толстая (ГОСТ) 50 м.",
                model="Медная труба 3/8 · бухта 50 м", price=9790)]
    text = seo_pages.summary_paragraph(brand("mednaya-truba"), seo_pages.facts(items))
    assert "2 позиции медной трубы" in text
    assert "Диаметры: 1/4″, 3/8″." in text
    assert "Стенка: средняя, толстая (ГОСТ)." in text
    assert "Бухты по 15 и 50 м." in text
    assert "за бухту" in text and "BTU" not in text


def test_kompressor_s_imenem_brenda_ne_pishem():
    text = seo_pages.summary_paragraph(brand("xigma"), seo_pages.facts([ac("1", compressor="XIGMA")]))
    assert "Компрессоры" not in text


def test_pustoy_brend():
    text = seo_pages.summary_paragraph(brand("daichi"), seo_pages.facts([]))
    assert "нет" in text and seo_pages.PHONE in text


def test_brend_ne_dubliruetsya_v_nazvanii():
    assert seo_pages._title(brand("daichi"), ac("1", model="DAICHI ICE20")) == "DAICHI ICE20"
    assert seo_pages._title(brand("xigma"), ac("1", model="XG-TXE21")) == "XIGMA XG-TXE21"


# ── страница ─────────────────────────────────────────────────────────────────

def test_stranica_h1_kanonikal_knopka_i_itemlist():
    products = [ac("1", price=19490), ac("2", price=13890, stock="days_3_5",
                                          photo="xigma-placeholder.webp")]
    page = seo_pages.render_brand_page(brand("xigma"), products)
    assert page.count("<h1") == 1 and "<h1>Кондиционеры XIGMA оптом</h1>" in page
    assert '<link rel="canonical" href="https://splithub.ru/xigma/">' in page
    assert 'href="/?price=1">Получить прайс</a>' in page
    assert 'href="/articles/">Статьи</a>' in page
    graph = {node["@type"]: node for node in jsonld(page)["@graph"]}
    items = graph["ItemList"]["itemListElement"]
    assert graph["ItemList"]["numberOfItems"] == 2
    first = items[0]["item"]
    assert first["offers"]["price"] == "13890" and first["offers"]["priceCurrency"] == "RUB"
    assert first["offers"]["availability"] == "https://schema.org/BackOrder"
    assert "image" not in first                     # заглушку в разметку не отдаём
    assert items[1]["item"]["offers"]["availability"] == "https://schema.org/InStock"
    assert items[1]["item"]["image"].endswith("/assets/img/products/x.webp")


def test_html_v_dannyh_ekraniruetsya():
    page = seo_pages.render_brand_page(brand("xigma"), [ac("1", model='X"<script>', series="</script>")])
    assert "<script>X" not in page and 'X"<script>' not in page
    jsonld(page)                                    # JSON-LD по-прежнему разбирается


def test_sitemap():
    xml = seo_pages.render_sitemap(seo_pages.sitemap_urls())
    assert xml.count("<loc>") == 1 + len(seo_pages.BRANDS)
    assert "<loc>https://splithub.ru/mednaya-truba/</loc>" in xml


def test_build_pishet_vse_stranitsy(tmp_path):
    written = seo_pages.build([ac("1")], tmp_path, sitemap=True)
    names = [name for _, name in written]
    assert names == [b["slug"] + "/index.html" for b in seo_pages.BRANDS] + ["sitemap.xml"]
    assert all(path.exists() for path, _ in written)


def test_zalivaem_tolko_izmenivshiesya(tmp_path):
    same, other = tmp_path / "a.html", tmp_path / "b.html"
    same.write_text("A", encoding="utf-8")
    other.write_text("B", encoding="utf-8")
    live = {"a/index.html": "A", "b/index.html": "старое"}
    changed = publish.changed_seo_pages([(same, "a/index.html"), (other, "b/index.html")], live.get)
    assert [name for _, name in changed] == ["b/index.html"]


def test_oshibka_stranic_ne_valit_progon(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("нет сети")
    monkeypatch.setattr(seo_pages, "fetch_overrides", boom)
    monkeypatch.setattr(seo_pages, "build", boom)
    assert publish.publish_seo_pages([ac("1")]).startswith("⚠️")


# ── главная ──────────────────────────────────────────────────────────────────

def _index():
    return (ROOT / "index.html").read_text(encoding="utf-8")


def test_glavnaya_h1():
    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", _index(), re.S)
    assert h1 == ["Кондиционеры оптом для монтажников в Симферополе"]


def test_faqpage_doslovno_kak_na_stranice():
    page = _index()
    visible = [(html.unescape(q), html.unescape(a)) for q, a in re.findall(
        r'<details class="g faq-item"><summary>(.*?)</summary><div><p>(.*?)</p></div></details>', page)]
    graph = {node["@type"]: node for node in jsonld(page)["@graph"]}
    marked = [(q["name"], q["acceptedAnswer"]["text"]) for q in graph["FAQPage"]["mainEntity"]]
    assert 5 <= len(visible) <= 7
    assert marked == visible
    assert {"Organization", "Store", "WebSite"} <= set(graph)
    assert graph["Store"]["address"]["addressLocality"] == "Симферополь"


def test_u_vseh_kartinok_est_alt():
    page = _index()
    for tag in re.findall(r"<img\b[^>]*>", page):
        assert re.search(r'\salt="', tag), tag


def test_ssylki_na_brendy_i_stati():
    page = _index()
    for b in seo_pages.BRANDS:
        assert 'href="/%s/"' % b["slug"] in page
    assert 'href="/articles/">Статьи</a>' in page


# ── деплой: слияние с боевыми файлами ────────────────────────────────────────

from tools.price_sync import deploy_seo  # noqa: E402


def test_htaccess_pravilo_www_v_nachalo_boevogo():
    live = "RewriteEngine On\nRewriteCond %{HTTPS} off\nRewriteRule ^(.*)$ https://%{HTTP_HOST}/$1 [R=301,L]\n"
    merged = deploy_seo.merge_htaccess(live)
    assert merged.endswith(live)                                   # боевое не тронуто
    assert merged.index("^www\\.") < merged.index("%{HTTPS} off")  # www — первым
    assert deploy_seo.merge_htaccess(merged) == merged             # повторный запуск — без дублей


def test_htaccess_net_na_servere_berem_iz_repo():
    assert "^www\\." in deploy_seo.merge_htaccess(None)


def test_sitemap_sohranyaet_boevye_adresa():
    live = ('<urlset><url><loc>https://splithub.ru/</loc></url>'
            '<url><loc>https://splithub.ru/privacy/</loc></url>'
            '<url><loc>https://splithub.ru/articles/kak-vybrat/</loc></url></urlset>')
    locs = deploy_seo.sitemap_locs(deploy_seo.merge_sitemap(live))
    assert locs[:1 + len(seo_pages.BRANDS)] == seo_pages.sitemap_urls()
    assert locs[-2:] == ["https://splithub.ru/privacy/", "https://splithub.ru/articles/kak-vybrat/"]
    assert len(locs) == len(set(locs))


def test_baza_index_html():
    import subprocess
    try:
        base = subprocess.run(["git", "show", "05742f7:index.html"], cwd=ROOT, capture_output=True,
                              check=True).stdout.decode("utf-8")
    except Exception:
        return
    assert deploy_seo.index_digest(base) == deploy_seo.BASE_INDEX_SHA256
    assert deploy_seo.index_digest(base.replace("\n", "\r\n")) == deploy_seo.BASE_INDEX_SHA256
    assert deploy_seo.index_digest(_index()) != deploy_seo.BASE_INDEX_SHA256
