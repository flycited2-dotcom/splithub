# HANDOFF — SplitHub

Состояние проекта splithub.ru на момент передачи. Стек: PHP + SQLite + ванильный JS, фронт — SPA (`index.html` — монолит). Каталог рендерится из `products.js`.

## Что сделано в последней сессии (2026-05-24)

| Коммит | Что |
|---|---|
| `58157b6` | Модалка «Полупром» с 4 подгруппами (Кассетные/Канальные/Напольно-потолочные/Мультисплит) + поддержка `pac_inv`/`pac_onoff` в конвертере |
| `a3b5411` | Фикс: плитки «Инверторные/On-Off/Труба» (`go()`) сбрасывают активный фильтр (был «пустой каталог» на мобиле) |
| `eb863ae` | Оптимизация: иконки «Полупром» PNG→WebP с ресайзом (5.1 МБ → 75 КБ) |
| `9018faf` | Фикс из QA-отчёта: убран дубль `<script>` (ломал `PRICE_SITE`) и битый SVG-path Telegram-иконки |
| `9644fdb` / `0284bb2` | «Поделиться» карточкой товара + кнопка «Копировать ссылку» (deep-link `?p=ID`) |
| `5021d9a` | Поля имя/телефон в корзине — только для гостей (приоритет профиля над localStorage) |
| `24db6b2` | Share-кнопки MAX/Telegram/Email/Ссылка в ряд (фирменные цвета) + графитово-стеклянная строка корзины |

Все коммиты в `main`, запушены, задеплоены на splithub.ru.

## Архитектура (ключевые узлы `index.html`)
- `FILTER_MAP` / `GROUP_ORDER` / `GROUP_LABELS` — фильтры каталога.
- `goFilter(key)` — применить фильтр; `go(id)` — плитки категорий (сбрасывает фильтр перед скроллом).
- `renderD()` — корзина/drawer. Поля имя/телефон только гостю (см. `effName`/`effPhone`, приоритет `currentUser` из профиля над `savedName/savedPhone`).
- `openDetail(id)` — карточка товара + строка share (`shareProductTo('max'|'tg'|'email'|'copy')`).
- `openPolupromModal()` / `closePolupromModal()` — модалка полупрома; подгруппы фильтруют по `type` (cassette/duct/floor-ceiling) с фолбэком на regex по `series`.
- Deep-link: `?p=ID` в Init → `openDetail(ID)`.
- `products.js` (`PRODUCTS`, ~678) — генерируется конвертером, руками не править.

## Деплой
- SFTP: `141.8.192.36:22`, user `a0296626`, webroot `/home/a0296626/domains/splithub.ru/public_html`.
- Креды — в `converter/config/deploy.json` (gitignored).
- PHP локально НЕ исполняется → `api/*.php` тестировать только на проде; авторизацию локально симулировать через preview eval.
- Способ: python+paramiko `sftp.put`, перед заменой — бэкап `index.html.bak.<ts>` на сервере.
- Локальный preview: `.claude/launch.json` → "splithub-static" (`python -m http.server 8765`).
- **Правило: тестировать ДО деплоя** (preview MCP: eval/screenshot/console/network).

## Открытые вопросы / не баги
- `api/auth.php?action=profile` → 401 для гостя — это норма (шумит в консоли; при желании вернуть 200 `{authorized:false}`).
- 404 на некоторые фото товаров — отсутствующие изображения (есть `onerror`-фолбэк), вопрос данных.
- QA-автотесты `02/04/07/08` падают как ложные срабатывания: тесты рассчитаны на многостраничный магазин, а сайт — SPA (нет отдельных URL товаров).
- `api/debug.php` — диагностический файл, лежит untracked; не коммитили.

## Конвертер каталога
`splithub_master_template.xlsx` → `converter/run.bat` (или run_dryrun.bat для проверки) → `out/products.js` → `converter/deploy.bat`. `valid_groups` в `converter/config/settings.json` должен включать все группы из мастер-файла (вкл. `pac_inv`, `pac_onoff`).
