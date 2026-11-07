#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Деплой SEO-правок splithub.ru одной командой — с предохранителями и откатом.

    python -m tools.price_sync.deploy_seo              # залить, проверить, тестовая заявка
    python -m tools.price_sync.deploy_seo --dry-run    # всё проверить и собрать, ничего не лить
    python -m tools.price_sync.deploy_seo --no-smoke-order   # без тестовой заявки

Что делает:
  1. Сверяет боевой index.html с версией, от которой делались SEO-правки. Прод
     расходится с git — index.html НЕ заливается, скрипт останавливается и сохраняет
     боевую копию в out/deploy_seo/ для сведения (иначе затрём чужие правки).
  2. Собирает страницы брендов из БОЕВОГО каталога (products.json с сервера) с
     правками админки — свежее, чем снимок в git.
  3. sitemap.xml — сливает с боевым: адреса, которые там уже есть (privacy, статьи),
     сохраняются, добавляются главная и страницы брендов.
  4. .htaccess — НЕ перезаписывает: в начало боевого дописывает только правило
     301 с www (если его там ещё нет). Правило http→https и прочее остаются.
  5. Заливает с датированными бэкапами (страницы брендов — новые, без бэкапа).
  6. Проверяет по HTTPS: главная 200 и новый H1, страницы брендов, sitemap, 301 с www,
     products.js. Главная или каталог сломались — автоматический откат из бэкапов.
  7. Смоук-тест приёма заявки (правило AGENTS.md): POST send.php → {"ok": true}.
     Заявка помечена «ТЕСТ деплой SEO — не обрабатывать».
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from tools.price_sync import seo_pages
from tools.price_sync.deploy_file import CONFIG, SITE_ROOT, remote_dir
from tools.price_sync.sync import DEFAULT_OUT

#: sha256 index.html, от которого делались SEO-правки (коммит 05742f7), переводы строк — LF.
BASE_INDEX_SHA256 = "efd4c2f65000b6f931713f01095fa2778a4a540196b49051266bcc6cf7944ef6"

WWW_MARKER = r"RewriteCond %{HTTP_HOST} ^www\.(.+)$ [NC]"
WWW_BLOCK = """# SEO: одно зеркало — https://splithub.ru (без www). www.splithub.ru/<путь>?<запрос>
# → 301 сразу на https://splithub.ru/<путь>?<запрос>, одним прыжком. Стоит ПЕРВЫМ.
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{HTTP_HOST} ^www\\.(.+)$ [NC]
    RewriteRule ^(.*)$ https://%1/$1 [R=301,L]
</IfModule>
"""

H1 = "Кондиционеры оптом для монтажников в Симферополе"
WORK = DEFAULT_OUT / "deploy_seo"


# ── чистые функции (покрыты тестами) ─────────────────────────────────────────

def index_digest(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").strip().encode("utf-8")).hexdigest()


def merge_htaccess(live: str | None) -> str:
    """Правило www → в начало боевого .htaccess; уже есть — файл как был."""
    if live is None:
        return (SITE_ROOT / ".htaccess").read_text(encoding="utf-8")
    if "^www\\." in live and "HTTP_HOST" in live:
        return live
    return WWW_BLOCK + "\n" + live


def sitemap_locs(xml: str | None) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml or "")


def merge_sitemap(live: str | None) -> str:
    """Наши адреса + всё, что уже было в боевом sitemap (без дублей, порядок сохранён)."""
    urls = []
    for url in seo_pages.sitemap_urls() + [u.replace("&amp;", "&") for u in sitemap_locs(live)]:
        if url not in urls:
            urls.append(url)
    return seo_pages.render_sitemap(urls)


# ── сервер ───────────────────────────────────────────────────────────────────

class Server:
    def __init__(self):
        import paramiko
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.site = remote_dir(cfg)
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(cfg["host"], port=cfg["port"], username=cfg["username"],
                         password=cfg["password"], timeout=cfg.get("timeout", 15))
        self.sftp = self.ssh.open_sftp()
        self.stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backups: list[tuple[str, str | None]] = []     # (путь, бэкап или None=файла не было)

    def run(self, command: str) -> int:
        _, out, _ = self.ssh.exec_command(command)
        return out.channel.recv_exit_status()

    def read(self, name: str) -> str | None:
        try:
            with self.sftp.open(self.site + "/" + name, "r") as handle:
                return handle.read().decode("utf-8")
        except IOError:
            return None

    def put(self, local: Path, name: str, backup: bool = True) -> None:
        target = self.site + "/" + name
        if "/" in name:
            self.run('mkdir -p "%s"' % target.rsplit("/", 1)[0])
        existed = self.run('test -f "%s"' % target) == 0
        copy = None
        if existed and backup:
            copy = "%s.bak.%s" % (target, self.stamp)
            if self.run('cp -p "%s" "%s"' % (target, copy)) != 0:
                raise RuntimeError("не удалось снять бэкап " + target)
        self.backups.append((target, copy if existed else None))
        self.sftp.put(str(local), target)
        print("  залито: %s%s" % (name, (", бэкап " + copy.rsplit("/", 1)[-1]) if copy else ""))

    def rollback(self, names: tuple[str, ...]) -> None:
        for target, copy in reversed(self.backups):
            if not target.endswith(names):
                continue
            if copy:
                self.run('cp -p "%s" "%s"' % (copy, target))
                print("  откат: " + target.rsplit("/", 1)[-1])

    def close(self) -> None:
        self.sftp.close()
        self.ssh.close()


# ── проверки по HTTPS ────────────────────────────────────────────────────────

def _get(url, **kwargs):
    import requests
    kwargs.setdefault("timeout", 30)
    kwargs.setdefault("params", {"t": int(datetime.now().timestamp())})
    response = requests.get(url, **kwargs)
    response.encoding = "utf-8"
    return response


def check_core() -> list[str]:
    """Сайт жив: главная с новым H1 и каталог. Пусто — всё хорошо."""
    problems = []
    home = _get(seo_pages.SITE + "/")
    if home.status_code != 200:
        problems.append("главная: HTTP %d" % home.status_code)
    elif H1 not in home.text:
        problems.append("главная: нет нового H1")
    catalog = _get(seo_pages.SITE + "/products.js")
    if catalog.status_code != 200 or "PRODUCTS" not in catalog.text:
        problems.append("products.js: HTTP %d" % catalog.status_code)
    return problems


def check_seo() -> list[str]:
    problems = []
    for brand in seo_pages.BRANDS:
        page = _get("%s/%s/" % (seo_pages.SITE, brand["slug"]))
        if page.status_code != 200 or brand["h1"] not in page.text:
            problems.append("/%s/: HTTP %d" % (brand["slug"], page.status_code))
    sitemap = _get(seo_pages.SITE + "/sitemap.xml")
    count = len(sitemap_locs(sitemap.text)) if sitemap.status_code == 200 else 0
    print("  sitemap.xml: %d адресов" % count)
    if count <= 3:
        problems.append("sitemap.xml: %d адресов" % count)
    www = _get("https://www.splithub.ru/xigma/?a=1", allow_redirects=False)
    location = www.headers.get("Location", "")
    print("  www: HTTP %d → %s" % (www.status_code, location or "—"))
    if www.status_code != 301 or not location.startswith("https://splithub.ru/xigma/"):
        problems.append("www: HTTP %d, Location %r" % (www.status_code, location))
    return problems


def smoke_order(products: list[dict]) -> str:
    import requests
    item = next(p for p in products if p.get("group") == "inv" and p.get("stock") != "out")
    payload = {
        "name": "ТЕСТ деплой SEO — не обрабатывать", "phone": "+79785991369",
        "comment": "Смоук-тест после выкладки SEO-правок (AGENTS.md). Не обрабатывать.",
        "client_tg": "", "sh_vid": "",
        "items": [{"id": item["id"], "name": item["model"], "brand": item.get("brand", ""),
                   "price": item["price"], "qty": 1, "group": item.get("group", "")}],
    }
    response = requests.post(seo_pages.SITE + "/send.php", json=payload, timeout=60)
    return response.text.strip()[:300]


# ── прогон ───────────────────────────────────────────────────────────────────

def run(dry_run: bool, smoke: bool) -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    seo_problems: list[str] = []
    local_index = (SITE_ROOT / "index.html").read_text(encoding="utf-8")
    server = Server()
    try:
        print("1. Сверка боевого index.html")
        live_index = server.read("index.html") or ""
        (WORK / "live_index.html").write_text(live_index, encoding="utf-8")
        live_digest = index_digest(live_index)
        if live_digest == index_digest(local_index):
            print("  уже залит — пропускаю")
            send_index = False
        elif live_digest == BASE_INDEX_SHA256:
            print("  совпадает с базой SEO-правок — можно лить")
            send_index = True
        else:
            print("  ⛔ боевой index.html отличается от git — НЕ заливаю, чтобы не затереть "
                  "чужие правки. Копия: %s. Сведите её с git и запустите снова."
                  % (WORK / "live_index.html"))
            return 1

        print("2. Страницы брендов из боевого каталога")
        products = json.loads(server.read("products.json") or "[]")
        if not products:
            print("  ⛔ не прочитал products.json с сервера")
            return 1
        try:
            overrides, custom = seo_pages.fetch_overrides()
        except Exception as error:
            print("  правки админки не получены (%s) — по каталогу" % error)
            overrides, custom = {}, []
        pages = seo_pages.build(seo_pages.apply_overrides(products, overrides, custom), WORK)
        print("  собрано страниц: %d (позиций в каталоге: %d)" % (len(pages), len(products)))

        print("3. sitemap.xml и .htaccess — слияние с боевыми")
        live_sitemap = server.read("sitemap.xml")
        (WORK / "sitemap.xml").write_text(merge_sitemap(live_sitemap), encoding="utf-8")
        print("  sitemap: было %d адресов, станет %d" % (
            len(sitemap_locs(live_sitemap)), len(sitemap_locs(merge_sitemap(live_sitemap)))))
        live_htaccess = server.read(".htaccess")
        if live_htaccess is not None:
            (WORK / "live.htaccess").write_text(live_htaccess, encoding="utf-8")
        merged_htaccess = merge_htaccess(live_htaccess)
        (WORK / ".htaccess").write_text(merged_htaccess, encoding="utf-8")
        send_htaccess = merged_htaccess != live_htaccess
        print("  .htaccess: %s" % ("дописываю правило www" if send_htaccess else "правило уже есть"))

        if dry_run:
            print("\n--dry-run: ничего не залито. Собранное — в %s" % WORK)
            return 0

        print("4. Заливка")
        for local, name in pages:
            server.put(local, name, backup=False)
        server.put(WORK / "sitemap.xml", "sitemap.xml")
        if send_index:
            server.put(SITE_ROOT / "index.html", "index.html")
        if send_htaccess:
            server.put(WORK / ".htaccess", ".htaccess")

        print("5. Проверка сайта")
        problems = check_core()
        if problems:
            print("  ⛔ " + "; ".join(problems) + " — ОТКАТ")
            server.rollback(("index.html", ".htaccess", "sitemap.xml"))
            print("  после отката: " + ("; ".join(check_core()) or "главная и каталог в порядке"))
            return 1
        print("  главная и каталог в порядке, H1 новый")
        seo_problems = check_seo()
        if any(p.startswith("www") for p in seo_problems) and send_htaccess:
            print("  ⚠️ 301 с www не сработал — откатываю .htaccess (сайт не трогаю)")
            server.rollback((".htaccess",))
        for problem in seo_problems:
            print("  ⚠️ " + problem)
        if not seo_problems:
            print("  страницы брендов, sitemap и 301 с www — в порядке")
    finally:
        server.close()

    if smoke:
        print("6. Смоук-тест заявки")
        answer = smoke_order(products)
        print("  send.php → " + answer)
        if '"ok":true' not in answer.replace(" ", ""):
            print("  ⛔ заявка не принята — проверьте send.php (index.html можно откатить из бэкапа)")
            return 1
    print("\n✅ Деплой SEO завершён.")
    return 1 if seo_problems else 0


def main(argv=None) -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Деплой SEO-правок splithub.ru")
    parser.add_argument("--dry-run", action="store_true", help="проверить и собрать, не заливать")
    parser.add_argument("--no-smoke-order", action="store_true", help="без тестовой заявки")
    args = parser.parse_args(argv)
    return run(args.dry_run, not args.no_smoke_order)


if __name__ == "__main__":
    raise SystemExit(main())
