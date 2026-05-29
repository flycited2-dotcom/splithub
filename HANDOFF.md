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
| `0b7633a` | Десктоп (≥820px): горизонтальная карточка товара — фото слева, инфо справа (CSS Grid) |
| `91baac1` | Десктоп-карточка шире (1160px), преимущества в 2 колонки (`columns:2`), бренд крупнее (1rem), лайтбокс фото (клик → на весь экран) |
| `216c88e` | Десктоп: share-кнопки горизонтальные/компактнее (50→34px) |
| `e9bc9de` | Фикс: лимит высоты фото `max-height:62vh` — карточка влезает без прокрутки на всех товарах |

Все коммиты в `main`, запушены, задеплоены на splithub.ru.

## Сессия 2026-05-29 (закрытие хвостов)
- `7ce39f0` Фикс: `api/auth.php?action=profile` отдаёт гостю 200 `{ok:false,authorized:false}` вместо 401 — пропал красный шум в консоли на каждой загрузке. Фронт уже глотал не-ok ответ, менять не пришлось. Проверено на проде (urllib: 200). Бэкап на сервере `auth.php.bak.<ts>`.
- Удалён временный `api/debug.php` (был untracked, на проде отсутствовал — 404; диагностику свою отработал).

## Архитектура (ключевые узлы `index.html`)
- `FILTER_MAP` / `GROUP_ORDER` / `GROUP_LABELS` — фильтры каталога.
- `goFilter(key)` — применить фильтр; `go(id)` — плитки категорий (сбрасывает фильтр перед скроллом).
- `renderD()` — корзина/drawer. Поля имя/телефон только гостю (см. `effName`/`effPhone`, приоритет `currentUser` из профиля над `savedName/savedPhone`).
- `openDetail(id)` — карточка товара. Структура: `.pd-close` (абсолютно), `.pd-scroll` с прямыми блоками `.pd-head`/`.pd-media`/`.pd-action-row`/`.pd-specs-row`/`.pd-features-block`/`.pd-share-row`. **Мобайл** — вертикальный bottom-sheet (порядок блоков в DOM). **Десктоп ≥820px** — CSS Grid (`grid-template-areas`): фото слева, инфо справа; преимущества в 2 колонки (`.pd-features-list{columns:2}`); фото ограничено `max-height:62vh` (иначе высокое фото растягивает модалку и появляется прокрутка).
- Строка share: `shareProductTo('max'|'tg'|'email'|'copy')`. MAX → `https://max.ru/:share?text=`, TG → `t.me/share/url`, email → `mailto:`, copy → clipboard. Лайтбокс: `openImgLightbox(src)`/`closeImgLightbox()` (клик по фото → на весь экран, Escape закрывает).
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

## ⚠️ Важные грабли (проверено на практике)
- **Локально фото товаров отдают 404** — в `assets/img/products/` всего ~8 файлов, остальные на проде. Поэтому при тестировании раскладки, зависящей от высоты фото (карточка товара), картинка не грузится → высота меньше реальной → ложный вывод «прокрутки нет». **Тестируй с реально загруженным фото**: подставь в eval `img.src='assets/img/products/eurohoff-astrid.webp'` (квадрат 1024×1024 — самый «высокий» кейс) и дождись `onload`. Проверяй на жёстком viewport (720px высоты).
- Высота модалки товара на десктопе определяется БО́льшим из: высота фото vs высота правой колонки. Фото ограничено `max-height:62vh`, чтобы не растягивало окно.
- Em-dash в JS-строках записан как литерал `—` (Edit-инструмент спотыкается — матчи делать без участка с тире, или править через Python с `chr(92)`).
- SSH иногда роняет "banner" — просто повторить с `banner_timeout=30`.

## Инструкция для следующей сессии
1. Прочитать этот HANDOFF + память (`project_splithub.md`).
2. Запустить preview: MCP `preview_start` "splithub-static" (или через `.claude/launch.json`).
3. Правки — в `index.html` (монолит). Тестировать в preview: `preview_resize` (mobile 375 / desktop 1280) → `preview_eval`/`preview_screenshot` → `preview_console_logs` (0 ошибок).
4. Для карточки товара ОБЯЗАТЕЛЬНО проверить с загруженным квадратным фото (см. грабли выше) и на мобиле, и на десктопе.
5. Деплой (только после теста): python+paramiko `sftp.put` index.html (+изменённые ассеты), бэкап `index.html.bak.<ts>`. Креды — `converter/config/deploy.json`.
6. `git add` → `commit` → `push origin main`. Затем верификация прода через `urllib` (наличие маркеров в HTML).

## Открытые вопросы / не баги
- 404 на некоторые фото товаров — отсутствующие изображения (есть `onerror`-фолбэк), вопрос данных.
- QA-автотесты `02/04/07/08` падают как ложные срабатывания: тесты рассчитаны на многостраничный магазин, а сайт — SPA (нет отдельных URL товаров).

## Конвертер каталога
`splithub_master_template.xlsx` → `converter/run.bat` (или run_dryrun.bat для проверки) → `out/products.js` → `converter/deploy.bat`. `valid_groups` в `converter/config/settings.json` должен включать все группы из мастер-файла (вкл. `pac_inv`, `pac_onoff`).
