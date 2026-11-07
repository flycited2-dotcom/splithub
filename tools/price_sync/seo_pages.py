#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SEO-страницы брендов СплитХаб и sitemap.xml — статикой из каталога.

Витрина splithub.ru — одностраничник: каталог рисует JS из products.js, поисковик
видит одну страницу. Здесь из того же каталога собираются отдельные страницы
(/ultima-comfort/, /xigma/, /eurohoff/, /daichi/, /mednaya-truba/): H1, текст, список
позиций с ценой и наличием, JSON-LD ItemList с Offer (цены на сайте публичные),
кнопка «Получить прайс».

Цены и наличие меняются каждую ночь, поэтому страницы перегенерирует publish.py
сразу после заливки каталога. Правки владельца из админки (products_overrides_public)
применяются так же, как на витрине, — страница не расходится с карточкой товара.

    python -m tools.price_sync.seo_pages                          # из products.js в корень сайта
    python -m tools.price_sync.seo_pages --catalog out/x.js --out /tmp/site
    python -m tools.price_sync.seo_pages --sitemap                # ещё и sitemap.xml

sitemap.xml ночью НЕ перезаливается: состав страниц меняется редко, а в него
дописывает свои адреса робот статей (/articles/). Пересобрать — флагом --sitemap
и выложить вручную.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

SITE = "https://splithub.ru"
SITE_ROOT = Path(__file__).resolve().parents[2]
OVERRIDES_URL = SITE + "/api/admin.php?action=products_overrides_public"

PHONE = "+7 978 599-13-69"
PHONE_TEL = "+79785991369"
EMAIL = "info@splithub.ru"
TELEGRAM = "Byttehnikaopt"
HOURS = "Пн–Вс 6:00–23:00"

#: Страницы брендов в порядке меню. match — по полю brand (без регистра) или group.
BRANDS = [
    {
        "slug": "ultima-comfort", "name": "ULTIMA COMFORT", "brand": "ULTIMA COMFORT",
        "h1": "Кондиционеры ULTIMA COMFORT оптом",
        "about": "ULTIMA COMFORT — бытовые настенные сплит-системы для квартир, офисов "
                 "и небольших коммерческих помещений.",
    },
    {
        "slug": "xigma", "name": "XIGMA", "brand": "XIGMA",
        "h1": "Кондиционеры XIGMA оптом",
        "about": "XIGMA — бытовые настенные сплит-системы для квартир и офисов.",
    },
    {
        "slug": "eurohoff", "name": "Eurohoff", "brand": "EUROHOFF",
        "h1": "Кондиционеры Eurohoff оптом",
        "about": "Eurohoff — бытовые и полупромышленные сплит-системы: от настенных "
                 "моделей для квартиры до кассетных и напольно-потолочных для магазинов, "
                 "кафе и офисов.",
    },
    {
        "slug": "daichi", "name": "DAICHI", "brand": "DAICHI",
        "h1": "Кондиционеры DAICHI оптом",
        "about": "DAICHI — сплит-системы бытового и полупромышленного класса.",
    },
    {
        "slug": "mednaya-truba", "name": "Медная труба", "group": "truba",
        "genitive": "медной трубы",
        "h1": "Медная труба для кондиционеров оптом",
        "about": "Медная труба для монтажа сплит-систем — в бухтах, для фреоновых трасс "
                 "между внутренним и наружным блоком.",
    },
]

GROUP_LABEL = {"inv": "Инвертор", "onoff": "On/Off", "pac_inv": "Полупром, инвертор",
               "pac_onoff": "Полупром", "truba": "", "rashod": ""}

STOCK_LABEL = {"in_stock": "В наличии", "days_1_2": "1–2 дня", "days_3_5": "3–5 дней",
               "days_7": "7 дней", "order_7": "Под заказ 7 дней", "wait": "Ожидается",
               "out": "Нет в наличии"}

SCHEMA_AVAILABILITY = {"in_stock": "https://schema.org/InStock",
                       "out": "https://schema.org/OutOfStock"}

#: Поля, которые админка может переопределить (как applyProductOverride в index.html).
OVERRIDE_FIELDS = ("brandCode", "brand", "series", "model", "group", "type", "factory",
                   "color", "btu", "area", "price", "stock", "stockLabel", "descShort",
                   "cardBenef", "benefits", "compressor", "freon", "photo", "photos",
                   "description", "badge", "badge_label")


# ── каталог ──────────────────────────────────────────────────────────────────

def load_catalog(path: Path) -> list[dict]:
    """products.js (var PRODUCTS = [...];) или products.json."""
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text[text.index("["):text.rindex("]") + 1])


def _inactive(value) -> bool:
    return value == 0 or value == "0"


def apply_overrides(products: list[dict], overrides: dict | None,
                    custom: list[dict] | None = None) -> list[dict]:
    """Каталог глазами витрины: правки админки поверх products.js, скрытые — убрать."""
    overrides = overrides or {}
    result, seen = [], set()
    for product in products:
        item = dict(product)
        override = overrides.get(item.get("sku")) or {}
        for field in OVERRIDE_FIELDS:
            if field in override:
                item[field] = override[field]
        seen.add(item.get("sku"))
        if _inactive(override.get("active")) or _inactive(item.get("active")):
            continue
        result.append(item)
    for product in custom or []:
        item = dict(product)
        if not item.get("sku") or item["sku"] in seen or _inactive(item.get("active")):
            continue
        result.append(item)
    for item in result:
        item["price"] = _number(item.get("price"))
        item["area"] = _number(item.get("area"))
    return result


def fetch_overrides(session=None, timeout: int = 30) -> tuple[dict, list]:
    """Правки админки с сайта. Не вышло — пустые: страницы соберутся по каталогу."""
    import requests
    getter = session or requests
    data = getter.get(OVERRIDES_URL, timeout=timeout).json()
    if not data.get("ok"):
        return {}, []
    return data.get("overrides") or {}, data.get("custom_products") or []


def _number(value) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def brand_items(products: list[dict], brand: dict) -> list[dict]:
    """Позиции страницы бренда с ценой, по сериям в порядке каталога, внутри — по BTU."""
    if "group" in brand:
        items = [p for p in products if p.get("group") == brand["group"]]
    else:
        wanted = brand["brand"].casefold()
        items = [p for p in products if str(p.get("brand", "")).strip().casefold() == wanted
                 and p.get("group") not in ("truba", "rashod")]
    items = [p for p in items if p.get("price", 0) > 0]
    order = {}
    for p in items:
        order.setdefault(p.get("series", ""), len(order))
    return sorted(items, key=lambda p: (order[p.get("series", "")], _btu(p), p["price"]))


def _btu(product: dict) -> int:
    match = re.match(r"\s*(\d+)", str(product.get("btu", "")))
    return int(match.group(1)) if match else 0


def _unique(values) -> list:
    seen = []
    for value in values:
        value = str(value or "").strip()
        if value and value != "-" and value not in seen:
            seen.append(value)
    return seen


def _rub(value: int) -> str:
    return "{:,}".format(int(value)).replace(",", " ")


def _join(words: list[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " и " + words[-1]


def facts(items: list[dict]) -> dict:
    """Сводка по позициям бренда — для текста страницы, всегда по живым данным."""
    btus = [b for b in (_btu(p) for p in items) if b]
    pipes = _unique(m.group(1) for p in items
                    for m in [re.search(r"(\d/\d)", str(p.get("model", "")))] if m)
    return {
        "count": len(items),
        "in_stock": sum(1 for p in items if p.get("stock") == "in_stock"),
        "min_price": min((p["price"] for p in items), default=0),
        "series": _unique(p.get("series") for p in items),
        "btu_min": min(btus, default=0), "btu_max": max(btus, default=0),
        "inverter": any(p.get("group") == "inv" for p in items),
        "onoff": any(p.get("group") == "onoff" for p in items),
        "poluprom": any(str(p.get("group", "")).startswith("pac") for p in items),
        "black": any(p.get("color") == "black" for p in items),
        "compressors": _unique(p.get("compressor") for p in items),
        "freon": _unique(p.get("freon") for p in items),
        "pipes": pipes,
        "walls": _unique(re.sub(r"\s*\d+\s*м\.?\s*$", "", str(p.get("series", "")))
                         for p in items if p.get("group") == "truba"),
        "coils": _unique(m.group(1) for p in items if p.get("group") == "truba"
                         for m in [re.search(r"бухта\s*(\d+)\s*м", str(p.get("model", "")))] if m),
    }


def summary_paragraph(brand: dict, f: dict) -> str:
    """Абзац «что сейчас в прайсе» — только из данных, без выдумки."""
    if not f["count"]:
        return ("Сейчас позиций %s в прайсе нет — уточните у менеджера по телефону %s."
                % (brand["name"], PHONE))
    head = "Сейчас в оптовом прайсе СплитХаб — %d %s %s" % (
        f["count"], _plural(f["count"], "позиция", "позиции", "позиций"),
        brand.get("genitive", brand["name"]))
    if f["in_stock"]:
        head += ", из них %d в наличии" % f["in_stock"]
    sentences = [head + "."]
    if f["series"] and not brand.get("group"):
        sentences.append("Серии: %s." % ", ".join(f["series"]))
    kinds = []
    if f["inverter"]:
        kinds.append("инверторные")
    if f["onoff"]:
        kinds.append("On/Off")
    if kinds:
        sentences.append("Настенные сплит-системы — %s." % _join(kinds))
    if f["poluprom"]:
        sentences.append("Есть полупромышленные модели.")
    if f["black"]:
        sentences.append("Есть модели в чёрном корпусе.")
    if f["btu_min"] and f["btu_max"]:
        if f["btu_min"] == f["btu_max"]:
            sentences.append("Мощность — %02d BTU." % f["btu_min"])
        else:
            sentences.append("Мощность — от %02d до %02d BTU." % (f["btu_min"], f["btu_max"]))
    compressors = [c for c in f["compressors"] if c.casefold() != brand["name"].casefold()]
    if compressors:
        sentences.append("Компрессоры: %s." % ", ".join(compressors))
    if f["freon"]:
        sentences.append("Хладагент: %s." % ", ".join(f["freon"]))
    if f["pipes"]:
        sentences.append("Диаметры: %s." % ", ".join(p + "″" for p in f["pipes"]))
    if f["walls"]:
        sentences.append("Стенка: %s." % ", ".join(w[:1].lower() + w[1:] for w in f["walls"]))
    if f["coils"]:
        sentences.append("Бухты по %s м." % _join(f["coils"]))
    unit = "бухту" if brand.get("group") == "truba" else "комплект"
    sentences.append("Цены — от %s ₽ за %s." % (_rub(f["min_price"]), unit))
    return " ".join(sentences)


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


# ── разметка ─────────────────────────────────────────────────────────────────

def _e(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _photo_url(product: dict) -> str:
    photo = str(product.get("photo") or "")
    if not photo or "placeholder" in photo:
        return ""
    if photo.startswith(("http://", "https://")):
        return photo
    if photo.startswith("/"):
        return SITE + photo
    if photo.startswith("assets/"):
        return SITE + "/" + photo
    return SITE + "/assets/img/products/" + photo


def product_url(product: dict) -> str:
    return "%s/?p=%s" % (SITE, product["id"])


def item_list_jsonld(brand: dict, items: list[dict]) -> dict:
    url = "%s/%s/" % (SITE, brand["slug"])
    elements = []
    for position, p in enumerate(items, 1):
        name = _title(brand, p)
        product = {
            "@type": "Product",
            "name": name,
            "sku": str(p.get("sku") or p["id"]),
            "url": product_url(p),
            "offers": {
                "@type": "Offer",
                "price": str(p["price"]),
                "priceCurrency": "RUB",
                "availability": SCHEMA_AVAILABILITY.get(p.get("stock"),
                                                        "https://schema.org/BackOrder"),
                "url": product_url(p),
                "seller": {"@id": SITE + "/#org"},
            },
        }
        if not brand.get("group"):
            product["brand"] = {"@type": "Brand", "name": brand["name"]}
        if p.get("descShort"):
            product["description"] = p["descShort"]
        image = _photo_url(p)
        if image:
            product["image"] = image
        elements.append({"@type": "ListItem", "position": position, "item": product})
    return {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "@id": SITE + "/#org", "name": "СплитХаб", "url": SITE + "/"},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "СплитХаб", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": brand["h1"], "item": url}]},
            {"@type": "ItemList", "@id": url + "#list", "name": brand["h1"], "url": url,
             "numberOfItems": len(items), "itemListElement": elements},
        ],
    }


def _menu(active: str) -> str:
    links = ['<a href="/">Каталог</a>']
    for brand in BRANDS:
        if brand["slug"] == active:
            links.append('<a href="/%s/" aria-current="page">%s</a>' % (brand["slug"], _e(brand["name"])))
        else:
            links.append('<a href="/%s/">%s</a>' % (brand["slug"], _e(brand["name"])))
    links.append('<a href="/articles/">Статьи</a>')
    return "\n    ".join(links)


def _title(brand: dict, p: dict) -> str:
    """Наименование с брендом впереди (в model его часто нет)."""
    title = str(p.get("model", "")).strip()
    if not brand.get("group") and brand["name"].casefold() not in title.casefold():
        title = "%s %s" % (brand["name"], title)
    return title


def _row(brand: dict, p: dict) -> str:
    meta = []
    if p.get("series"):
        meta.append(_e(p["series"]))
    kind = GROUP_LABEL.get(p.get("group"), "")
    if kind and not str(p.get("series", "")).lower().startswith(kind.lower()):
        meta.append(kind)
    if _btu(p):
        power = "%02d BTU" % _btu(p)
        if p.get("area"):
            power += " · до %d м²" % p["area"]
        meta.append(power)
    title = _title(brand, p)
    stock = p.get("stock", "")
    label = p.get("stockLabel") or STOCK_LABEL.get(stock, "")
    css = "in" if stock == "in_stock" else ("out" if stock == "out" else "wait")
    return (
        '<li class="row" data-sku="%s">\n'
        '      <a class="row-main" href="/?p=%s"><span class="row-name">%s</span>'
        '<span class="row-meta">%s</span></a>\n'
        '      <div class="row-side"><span class="row-price"><span data-price>%s</span>&nbsp;₽</span>'
        '<span class="row-stock %s" data-stock>%s</span></div>\n'
        '    </li>' % (_e(p.get("sku", "")), _e(p["id"]), _e(title), " · ".join(meta),
                       _rub(p["price"]), css, _e(label)))


CSS = """
:root{--bg:#F0F2F5;--card:#fff;--text:#1A1C22;--text2:#5A5F6E;--text3:#9298A8;--amber:#F59E0B;--amber-d:#B45309;--green:#047857;--line:rgba(150,160,180,.35);--tg:#229ED9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#14161B;--card:#1E2128;--text:#F1F3F7;--text2:#B4BAC7;--text3:#8A91A0;--amber:#F59E0B;--amber-d:#FBBF24;--green:#34D399;--line:rgba(120,130,150,.35)}}
:root[data-theme="dark"]{--bg:#14161B;--card:#1E2128;--text:#F1F3F7;--text2:#B4BAC7;--text3:#8A91A0;--amber:#F59E0B;--amber-d:#FBBF24;--green:#34D399;--line:rgba(120,130,150,.35)}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.55;overflow-x:hidden}
a{color:inherit}
.wrap{max-width:960px;margin:0 auto;padding:0 16px}
header{border-bottom:1px solid var(--line);background:var(--card)}
.top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 0}
.logo{font-family:'Unbounded',sans-serif;font-weight:700;font-size:1rem;letter-spacing:-.03em;text-decoration:none}
.logo em{font-style:normal;color:var(--amber)}
.top-ph{font-size:.82rem;font-weight:600;text-decoration:none;white-space:nowrap}
.menu{display:flex;gap:6px;overflow-x:auto;padding:0 0 12px;scrollbar-width:none}
.menu::-webkit-scrollbar{display:none}
.menu a{flex:0 0 auto;font-size:.78rem;font-weight:600;text-decoration:none;padding:6px 12px;border:1px solid var(--line);border-radius:999px;color:var(--text2)}
.menu a[aria-current]{background:var(--amber);border-color:var(--amber);color:#1A1C22}
.crumbs{font-size:.72rem;color:var(--text3);padding:16px 0 6px}
.crumbs a{color:var(--text2)}
h1{font-family:'Unbounded',sans-serif;font-size:clamp(1.3rem,4.6vw,1.9rem);line-height:1.2;letter-spacing:-.03em;margin:0 0 12px}
h2{font-family:'Unbounded',sans-serif;font-size:1.05rem;letter-spacing:-.02em;margin:28px 0 10px}
p{color:var(--text2);font-size:.92rem;margin:0 0 10px;max-width:72ch}
.cta{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 4px}
.btn{display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:.88rem;padding:12px 20px;border-radius:12px;text-decoration:none;border:1.5px solid var(--amber)}
.btn-main{background:var(--amber);color:#1A1C22}
.btn-ghost{color:var(--amber-d)}
.rows{list-style:none;display:flex;flex-direction:column;gap:6px;margin:6px 0 0}
.row{display:flex;align-items:center;justify-content:space-between;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px}
.row-main{display:flex;flex-direction:column;min-width:0;text-decoration:none}
.row-name{font-weight:600;font-size:.88rem;overflow-wrap:anywhere}
.row-main:hover .row-name{color:var(--amber-d)}
.row-meta{font-size:.74rem;color:var(--text3)}
.row-side{display:flex;flex-direction:column;align-items:flex-end;flex:0 0 auto;text-align:right}
.row-price{font-weight:700;font-size:.92rem;white-space:nowrap}
.row-stock{font-size:.7rem;font-weight:600;white-space:nowrap}
.row-stock.in{color:var(--green)}
.row-stock.wait{color:var(--amber-d)}
.row-stock.out{color:var(--text3)}
.note{font-size:.75rem;color:var(--text3);margin-top:8px}
.contacts{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:28px 0 0}
.contacts p{margin-bottom:6px}
.contacts a{font-weight:600}
footer{border-top:1px solid var(--line);margin-top:36px;padding:16px 0 28px;font-size:.75rem;color:var(--text3)}
footer nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin-bottom:8px}
footer a{color:var(--text2)}
@media (max-width:420px){.row{padding:10px 12px}.row-name{font-size:.84rem}}
"""

PATCH_JS = """
(function(){
  try{
    fetch('/api/admin.php?action=products_overrides_public').then(function(r){return r.json();}).then(function(d){
      if(!d||!d.ok||!d.overrides) return;
      document.querySelectorAll('.row[data-sku]').forEach(function(row){
        var ov=d.overrides[row.getAttribute('data-sku')];
        if(!ov) return;
        if(ov.active===0||ov.active==='0'){ row.style.display='none'; return; }
        if(ov.price){ row.querySelector('[data-price]').textContent=Number(ov.price).toLocaleString('ru-RU'); }
        if(ov.stockLabel){ row.querySelector('[data-stock]').textContent=ov.stockLabel; }
      });
    }).catch(function(){});
  }catch(e){}
})();
"""

METRIKA = """<!-- Yandex.Metrika counter -->
<script type="text/javascript">
    (function(m,e,t,r,i,k,a){
        m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
        m[i].l=1*new Date();
        for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
        k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
    })(window, document,'script','https://mc.yandex.ru/metrika/tag.js?id=109740770', 'ym');

    ym(109740770, 'init', {ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", referrer: document.referrer, url: location.href, accurateTrackBounce:true, trackLinks:true});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/109740770" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
<!-- /Yandex.Metrika counter -->"""


def render_brand_page(brand: dict, products: list[dict]) -> str:
    items = brand_items(products, brand)
    f = facts(items)
    url = "%s/%s/" % (SITE, brand["slug"])
    if brand.get("group"):
        title = "%s в Симферополе — цены, наличие | СплитХаб" % brand["h1"]
    else:
        title = "%s в Симферополе — прайс для монтажников | СплитХаб" % brand["h1"]
    description = "%s в Симферополе и по Крыму: %d %s, цены от %s ₽, наличие на складе. Оптовый прайс для монтажников и B2B." % (
        brand["h1"], f["count"], _plural(f["count"], "позиция", "позиции", "позиций"),
        _rub(f["min_price"]).replace(" ", " "))
    rows = "\n    ".join(_row(brand, p) for p in items)
    jsonld = json.dumps(item_list_jsonld(brand, items), ensure_ascii=False, indent=1)
    jsonld = jsonld.replace("</", "<\\/")
    return """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{h1} — СплитХаб">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{site}/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/icons/favicon-32x32.png">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@600;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>{css}</style>
<script type="application/ld+json">
{jsonld}
</script>
{metrika}
</head>
<body>
<header>
  <div class="wrap">
    <div class="top">
      <a class="logo" href="/">Сплит<em>Хаб</em></a>
      <a class="top-ph" href="tel:{tel}">&#128222; {phone}</a>
    </div>
    <nav class="menu" aria-label="Бренды и разделы">
    {menu}
    </nav>
  </div>
</header>
<main class="wrap">
  <div class="crumbs"><a href="/">СплитХаб</a> / {name}</div>
  <h1>{h1}</h1>
  <p>{about}</p>
  <p>{summary}</p>
  <div class="cta">
    <a class="btn btn-main" href="/?price=1">Получить прайс</a>
    <a class="btn btn-ghost" href="https://t.me/{telegram}" target="_blank" rel="noopener">Написать в Telegram</a>
  </div>
  <h2>Позиции {genitive} в прайсе</h2>
  <ul class="rows">
    {rows}
  </ul>
  <p class="note">Цены оптовые, за {unit}. Нажмите на позицию, чтобы открыть карточку в каталоге и добавить её в заявку.</p>
  <h2>Как заказать</h2>
  <p>Цены на странице — оптовые, для монтажников и B2B-клиентов; цены и наличие обновляются каждый день. Откройте позицию в каталоге и добавьте её в заявку — менеджер перезвонит в течение 15 минут. Полный прайс всех брендов в Excel или PDF — по кнопке «Получить прайс».</p>
  <div class="contacts">
    <p><b>Менеджер СплитХаб</b> · {hours} · Симферополь, работаем по всему Крыму</p>
    <p><a href="tel:{tel}">{phone}</a> · <a href="https://t.me/{telegram}" target="_blank" rel="noopener">Telegram @{telegram}</a> · <a href="mailto:{email}">{email}</a></p>
  </div>
</main>
<footer>
  <div class="wrap">
    <nav aria-label="Разделы сайта">
    {menu}
    </nav>
    <div>&copy; 2026 СплитХаб · Опт · Симферополь · <a href="/privacy/">Политика конфиденциальности</a></div>
  </div>
</footer>
<script>{patch}</script>
</body>
</html>
""".format(title=_e(title), description=_e(description), url=url, site=SITE, h1=_e(brand["h1"]),
           css=CSS.strip(), jsonld=jsonld, metrika=METRIKA, tel=PHONE_TEL, phone=PHONE,
           menu=_menu(brand["slug"]), name=_e(brand["name"]),
           genitive=_e(brand.get("genitive", brand["name"])), about=_e(brand["about"]),
           summary=_e(summary_paragraph(brand, f)), telegram=TELEGRAM, rows=rows,
           unit="бухту" if brand.get("group") == "truba" else "комплект",
           hours=HOURS, email=EMAIL, patch=PATCH_JS.strip())


def sitemap_urls() -> list[str]:
    return [SITE + "/"] + ["%s/%s/" % (SITE, brand["slug"]) for brand in BRANDS]


def render_sitemap(urls: list[str]) -> str:
    body = "\n".join("  <url><loc>%s</loc></url>" % html.escape(url) for url in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % body)


def build(products: list[dict], out_dir: Path, sitemap: bool = False) -> list[tuple[Path, str]]:
    """Записать страницы в out_dir/<slug>/index.html. Возвращает (файл, путь на сайте)."""
    written = []
    for brand in BRANDS:
        name = "%s/index.html" % brand["slug"]
        target = Path(out_dir) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_brand_page(brand, products), encoding="utf-8")
        written.append((target, name))
    if sitemap:
        target = Path(out_dir) / "sitemap.xml"
        target.write_text(render_sitemap(sitemap_urls()), encoding="utf-8")
        written.append((target, "sitemap.xml"))
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Страницы брендов и sitemap.xml СплитХаб")
    parser.add_argument("--catalog", default=str(SITE_ROOT / "products.js"),
                        help="products.js или products.json (по умолчанию — из корня сайта)")
    parser.add_argument("--out", default=str(SITE_ROOT), help="куда писать (корень сайта)")
    parser.add_argument("--sitemap", action="store_true", help="пересобрать и sitemap.xml")
    parser.add_argument("--live-overrides", action="store_true",
                        help="применить правки админки с splithub.ru")
    args = parser.parse_args(argv)
    products = load_catalog(Path(args.catalog))
    overrides, custom = fetch_overrides() if args.live_overrides else ({}, [])
    for path, name in build(apply_overrides(products, overrides, custom), Path(args.out), args.sitemap):
        print("собрано: %s" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
