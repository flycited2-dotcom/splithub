# Аналитика посетителей, база клиентов и экспорт в Excel — дизайн

Дата: 2026-06-09
Проект: СплитХаб (splithub.ru)

## Цель

Дать владельцу сайта полную картину по клиентам и посетителям:
1. Подключить Яндекс.Метрику (счётчик 109740770).
2. Собирать собственную базу посетителей через cookie (визит + источник).
3. Выгружать клиентов в Excel.
4. Сделать настоящий `.xlsx` с заполненными графами и автофильтром (вместо только CSV).

## Решения (зафиксированы с заказчиком)

- **Метрика:** счётчик `109740770`, полный сниппет с webvisor/clickmap/ecommerce, ID вставляется напрямую.
- **Глубина трекинга:** базово — визит + источник (без покликового поведения).
- **Согласие:** плашка-уведомление о cookie без блокировки сбора.
- **Экспорт Excel:** один файл `.xlsx` с тремя листами — Клиенты, Заказы, Посетители.
- **IP:** хранить чистый IP-адрес.

## Контекст кодовой базы

- Канонический модуль БД — `db/init.php` (функция `getDB()`, инкрементальные миграции на каждом
  запросе). Его подключают `api_admin.php` и `send.php`. Корневой `db_init.php` — устаревшая
  неиспользуемая копия; **не трогаем**.
- БД — SQLite (`db/splithub.sqlite`), таблицы: `users`, `orders`, `order_items`, `guest_orders`,
  `bonus_log`, `promo_rules`, `app_settings`, `monthly_reports`, `product_overrides`.
- Заявки обрабатывает `send.php`: авторизованный → `orders`/`order_items`, гость → `guest_orders`,
  плюс отправка в Telegram и на email.
- Админ-API — `api_admin.php` (роутинг по `?action=`), уже есть CSV-экспорт заказов
  (`export_orders_csv`).
- Фронт — `index.html` (использует `localStorage`: `sh_name`, `sh_phone`).
- Composer/сторонних библиотек в проекте нет — новые возможности без внешних зависимостей.

---

## Блок A. Яндекс.Метрика

Вставить стандартный сниппет Метрики со счётчиком `109740770` (webvisor, clickmap, ecommerce,
trackLinks, accurateTrackBounce) перед `</head>` в `index.html`. Только на сайте для посетителей,
в `admin.html` не добавляем.

Точный код (предоставлен заказчиком):

```html
<!-- Yandex.Metrika counter -->
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
<!-- /Yandex.Metrika counter -->
```

---

## Блок B. Свой сбор посетителей (cookie)

### Поток данных

1. При первом заходе сервер/фронт ставит first-party cookie `sh_vid` — случайный UUID
   посетителя, срок жизни 1 год, `SameSite=Lax`.
2. На каждой загрузке страницы фронт отправляет «маячок» через `navigator.sendBeacon`
   (fallback — `fetch` с `keepalive`) на новый эндпоинт `POST api/track.php`.
3. Эндпоинт пишет один визит в `visits` и обновляет агрегат в `visitors`.
4. Плашка cookie показывается один раз; факт показа хранится в `localStorage` (`sh_cookie_ok`).
   Сбор идёт независимо от клика (уведомление без блокировки).

### Что собираем (базово: визит + источник)

Параметры визита: дата/время, путь страницы, `referrer`, UTM-метки
(`utm_source/medium/campaign`), тип устройства (mobile/desktop из user-agent), user-agent, IP.

### Схема БД (новые таблицы в `db/init.php`)

```sql
CREATE TABLE IF NOT EXISTS visitors (
    vid TEXT PRIMARY KEY,            -- UUID из cookie sh_vid
    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen  TEXT DEFAULT CURRENT_TIMESTAMP,
    visits_count INTEGER DEFAULT 0,
    first_referrer TEXT DEFAULT '',
    first_utm_source TEXT DEFAULT '',
    first_utm_medium TEXT DEFAULT '',
    first_utm_campaign TEXT DEFAULT '',
    device TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    last_ip TEXT DEFAULT '',
    linked_phone TEXT DEFAULT '',    -- заполняется при оформлении заявки
    linked_name  TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vid TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    page TEXT DEFAULT '',
    referrer TEXT DEFAULT '',
    utm_source TEXT DEFAULT '',
    utm_medium TEXT DEFAULT '',
    utm_campaign TEXT DEFAULT '',
    device TEXT DEFAULT '',
    ip TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_visits_vid ON visits(vid);
CREATE INDEX IF NOT EXISTS idx_visits_created ON visits(created_at);
```

При первом визите для `vid` заполняются `first_*`; при последующих обновляются `last_seen`,
`last_ip`, `visits_count`.

### Эндпоинт `api/track.php`

- Метод `POST`, тело JSON: `{ page, referrer, utm_source, utm_medium, utm_campaign, device }`.
- Читает/ставит cookie `sh_vid`; если нет — генерирует UUID и ставит `Set-Cookie`.
- Пишет строку в `visits`, апсертит `visitors`.
- IP берётся из `REMOTE_ADDR` (с учётом `X-Forwarded-For`, если за прокси).
- Без авторизации. Возвращает `{ok:true}`. Защита от мусора: ограничение длины полей,
  только разрешённый Content-Type.

### Мостик к базе клиентов

В `send.php` фронт дополнительно передаёт `sh_vid`. После успешной записи заявки сервер
обновляет в `visitors` поля `linked_phone`/`linked_name` для этого `vid`. Так в отчёте видно,
из какого источника пришёл оформивший заявку клиент.

### Плашка cookie

Фиксированная полоса внизу `index.html`: «Мы используем cookie и Яндекс.Метрику для аналитики.
[Понятно]». Клик скрывает плашку и пишет `localStorage.sh_cookie_ok=1`. Сбор не блокируется.

---

## Блок C. Экспорт в Excel (.xlsx)

### Техническое решение

Нативный генератор `.xlsx` на чистом PHP через `ZipArchive` (xlsx = zip с OOXML внутри).
Без Composer и сторонних библиотек. Новый помощник `api/lib/xlsx_writer.php`:

- API: добавление листа с именем, массив строк (первая — заголовки), запись в поток на скачивание.
- Возможности: жирная шапка, автофильтр по шапке, корректное экранирование (XML, числа vs текст),
  поддержка кириллицы (UTF-8). Несколько листов в одном файле.
- Намеренно минимальный, без формул/стилей сверх необходимого (YAGNI).

### Новый admin-action `export_xlsx`

В `api_admin.php` добавляется ветка `export_xlsx` (по аналогии с `export_orders_csv`: правильные
заголовки Content-Type до проверки auth, но с `adminRequire()`). Формирует файл
`splithub_export_YYYY-MM-DD.xlsx` с тремя листами:

**Лист «Клиенты»** — объединение `users` и гостей из `guest_orders`:
- Колонки: ID, Тип (Зарегистрирован/Гость), Имя, Телефон, Telegram, Компания, ИНН, КПП,
  Юр.адрес, Дата регистрации, Кол-во заказов, Сумма заказов ₽.
- Гости агрегируются по телефону (кол-во и сумма из `guest_orders`).

**Лист «Заказы»** — `orders` + `guest_orders`:
- Колонки: №, Тип (Клиент/Гость), Дата, Клиент, Телефон, Telegram, Сумма ₽, Статус,
  Бонусов начислено, Бонусов списано, Заметка, Комментарий, Источник (из `visitors`, если связан).

**Лист «Посетители»** — `visitors`:
- Колонки: ID посетителя, Первый визит, Последний визит, Кол-во визитов, Источник (referrer),
  UTM source/medium/campaign, Устройство, IP, Привязанный клиент (имя/телефон).

Существующий CSV-экспорт (`export_orders_csv`) остаётся без изменений.

### UI в админке

В `admin.html`:
- Кнопка «Скачать Excel (.xlsx)» (рядом с существующим экспортом) → `api_admin.php?action=export_xlsx`.
- Новая вкладка/раздел «Посетители» — таблица из нового action `visitors_list` (постранично),
  по аналогии с существующими списками (`orders`, `guest_orders`).

---

## Затрагиваемые файлы

**Новые:**
- `api/track.php` — приём маячков, запись визитов.
- `api/lib/xlsx_writer.php` — генератор xlsx.

**Изменяемые:**
- `db/init.php` — миграции: таблицы `visitors`, `visits` + индексы.
- `index.html` — сниппет Метрики, плашка cookie, JS-маячок, передача `sh_vid` в `send.php`.
- `send.php` — приём `sh_vid`, привязка визита к клиенту (`linked_phone/name`).
- `api_admin.php` — action `export_xlsx`, action `visitors_list`.
- `admin.html` — кнопка экспорта xlsx, раздел «Посетители».

**Не трогаем:** `db_init.php` (устаревшая копия).

## Обработка ошибок

- `track.php`: любой сбой не должен влиять на посетителя — оборачиваем в try/catch, всегда
  отвечаем быстро; беспривязочный маячок не ломает страницу.
- `xlsx_writer`: ошибки записи → 500 с JSON, не отдаём битый файл.
- `send.php`: привязка `sh_vid` во вторичном try/catch (как существующая запись в БД) —
  сбой не влияет на отправку заявки.

## Критерии готовности (проверяемые)

1. На страницах сайта грузится Метрика (виден запрос на `mc.yandex.ru`, счётчик 109740770).
2. После захода в `visits` появляется строка с источником; в `visitors` — агрегат с `sh_vid`.
3. Плашка cookie показывается один раз, после «Понятно» не появляется снова.
4. После оформления заявки у соответствующего `vid` заполнены `linked_phone/name`.
5. Кнопка в админке отдаёт корректный `.xlsx`, открывается в Excel/LibreOffice, 3 листа
   заполнены, шапки жирные, работает автофильтр.
6. Раздел «Посетители» в админке показывает собранные данные.

## Вне рамок (YAGNI)

- Покликовое поведение/тепловые карты своими силами (для этого есть Метрика-вебвизор).
- Геолокация по IP (требует внешнего сервиса).
- Согласие с блокировкой сбора (выбрано уведомление без блокировки).
- Экспорт в форматах помимо xlsx/существующего CSV.
