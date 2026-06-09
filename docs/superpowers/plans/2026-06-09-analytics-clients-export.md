# Аналитика, база клиентов и экспорт в Excel — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подключить Яндекс.Метрику, собирать собственную базу посетителей через cookie (визит + источник), связывать визиты с клиентами и выгружать клиентов/заказы/посетителей в один `.xlsx`.

**Architecture:** Чистый PHP без внешних зависимостей. Новые таблицы `visitors`/`visits` в канонической `db/init.php`. Эндпоинт `api/track.php` принимает «маячки» с фронта. Нативный генератор `.xlsx` (`api/lib/xlsx_writer.php`) через `ZipArchive`. Новые admin-actions в активном `api/admin.php`. Фронт — правки в `index.html` (Метрика, плашка, маячок) и `admin.html` (кнопка экспорта + раздел «Посетители»).

**Tech Stack:** PHP 7+/PDO/SQLite, ZipArchive, ванильный JS, HTML.

## Окружение для проверки

PHP локально отсутствует. Для проверки PHP-кода нужен PHP CLI:
- Установить локально: `winget install PHP.PHP` (Windows) или XAMPP, затем `php -S localhost:8000` из корня репозитория.
- Либо проверять на сервере после деплоя.
- `.xlsx`-артефакт валидируется локально Python-ом (`openpyxl`) — Python 3.13 уже есть.

**Активные файлы (НЕ путать с легаси-копиями):**
- БД: `db/init.php` (НЕ `db_init.php`)
- Admin-API: `api/admin.php` (НЕ корневой `api_admin.php`)

---

## Task 1: Миграции БД — таблицы visitors и visits

**Files:**
- Modify: `db/init.php` (добавить блок инкрементальных миграций перед `return $db;` в `getDB()`)

- [ ] **Step 1: Добавить создание таблиц**

В `db/init.php`, в функции `getDB()`, найти `return $db;` (последняя строка функции, после блока `monthly_reports`) и **перед ним** вставить:

```php
    // visitors / visits — собственный трекинг посетителей
    try {
        $db->exec("CREATE TABLE IF NOT EXISTS visitors (
            vid TEXT PRIMARY KEY,
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
            linked_phone TEXT DEFAULT '',
            linked_name  TEXT DEFAULT ''
        )");
        $db->exec("CREATE TABLE IF NOT EXISTS visits (
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
        )");
        $db->exec("CREATE INDEX IF NOT EXISTS idx_visits_vid ON visits(vid)");
        $db->exec("CREATE INDEX IF NOT EXISTS idx_visits_created ON visits(created_at)");
    } catch (Throwable $e) {}
```

- [ ] **Step 2: Проверить синтаксис**

Run: `php -l db/init.php`
Expected: `No syntax errors detected in db/init.php`

- [ ] **Step 3: Проверить, что таблицы создаются**

Run (из корня репо, PHP CLI):
```bash
php -r "require 'db/init.php'; \$db=getDB(); var_dump(\$db->query(\"SELECT name FROM sqlite_master WHERE type='table' AND name IN ('visitors','visits')\")->fetchAll(PDO::FETCH_COLUMN));"
```
Expected: массив содержит `"visitors"` и `"visits"`.

- [ ] **Step 4: Commit**

```bash
git add db/init.php
git commit -m "feat(db): таблицы visitors и visits для трекинга посетителей"
```

---

## Task 2: Эндпоинт трекинга api/track.php

**Files:**
- Create: `api/track.php`

- [ ] **Step 1: Создать файл**

Создать `api/track.php` с содержимым:

```php
<?php
/**
 * track.php — приём «маячков» от посетителей сайта.
 * Пишет визит в visits и агрегат в visitors. Без авторизации.
 * Любой сбой не должен мешать посетителю — всегда быстрый ответ.
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST')    { http_response_code(405); echo '{"ok":false}'; exit; }

function track_clip($s, $max = 500) {
    $s = is_string($s) ? trim($s) : '';
    if (mb_strlen($s) > $max) $s = mb_substr($s, 0, $max);
    return $s;
}

function track_client_ip() {
    $xff = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? '';
    if ($xff !== '') {
        $parts = explode(',', $xff);
        $ip = trim($parts[0]);
        if (filter_var($ip, FILTER_VALIDATE_IP)) return $ip;
    }
    $ip = $_SERVER['REMOTE_ADDR'] ?? '';
    return filter_var($ip, FILTER_VALIDATE_IP) ? $ip : '';
}

try {
    $raw  = file_get_contents('php://input');
    $data = json_decode($raw, true);
    if (!is_array($data)) $data = [];

    // vid из cookie, иначе генерируем и ставим
    $vid = $_COOKIE['sh_vid'] ?? '';
    if (!preg_match('/^[a-f0-9\-]{8,40}$/i', $vid)) {
        $vid = bin2hex(random_bytes(16));
        setcookie('sh_vid', $vid, [
            'expires'  => time() + 365 * 24 * 3600,
            'path'     => '/',
            'samesite' => 'Lax',
        ]);
    }

    $page     = track_clip($data['page'] ?? '');
    $referrer = track_clip($data['referrer'] ?? '');
    $utmS     = track_clip($data['utm_source'] ?? '', 100);
    $utmM     = track_clip($data['utm_medium'] ?? '', 100);
    $utmC     = track_clip($data['utm_campaign'] ?? '', 100);
    $device   = track_clip($data['device'] ?? '', 20);
    $ua       = track_clip($_SERVER['HTTP_USER_AGENT'] ?? '', 300);
    $ip       = track_client_ip();

    require_once __DIR__ . '/../db/init.php';
    $db = getDB();

    $ins = $db->prepare('INSERT INTO visits (vid,page,referrer,utm_source,utm_medium,utm_campaign,device,ip) VALUES (?,?,?,?,?,?,?,?)');
    $ins->execute([$vid, $page, $referrer, $utmS, $utmM, $utmC, $device, $ip]);

    $exists = $db->prepare('SELECT vid FROM visitors WHERE vid = ?');
    $exists->execute([$vid]);
    if ($exists->fetch()) {
        $db->prepare("UPDATE visitors SET last_seen=CURRENT_TIMESTAMP, visits_count=visits_count+1, last_ip=?, device=?, user_agent=? WHERE vid=?")
           ->execute([$ip, $device, $ua, $vid]);
    } else {
        $db->prepare("INSERT INTO visitors (vid,visits_count,first_referrer,first_utm_source,first_utm_medium,first_utm_campaign,device,user_agent,last_ip) VALUES (?,?,?,?,?,?,?,?,?)")
           ->execute([$vid, 1, $referrer, $utmS, $utmM, $utmC, $device, $ua, $ip]);
    }

    echo json_encode(['ok' => true, 'vid' => $vid]);
} catch (Throwable $e) {
    error_log('[SplitHub track] ' . $e->getMessage());
    echo json_encode(['ok' => false]);
}
```

- [ ] **Step 2: Проверить синтаксис**

Run: `php -l api/track.php`
Expected: `No syntax errors detected`

- [ ] **Step 3: Функциональная проверка (локальный сервер)**

Запустить сервер: `php -S localhost:8000` (из корня репо), затем:
```bash
curl -s -X POST http://localhost:8000/api/track.php -H "Content-Type: application/json" -d "{\"page\":\"/\",\"referrer\":\"https://yandex.ru/\",\"utm_source\":\"yandex\",\"device\":\"desktop\"}" -c cookies.txt
```
Expected: JSON `{"ok":true,"vid":"..."}` и в `cookies.txt` появилась cookie `sh_vid`.

- [ ] **Step 4: Проверить запись в БД**

Run:
```bash
php -r "require 'db/init.php'; \$db=getDB(); var_dump(\$db->query('SELECT COUNT(*) FROM visits')->fetchColumn(), \$db->query('SELECT utm_source,referrer FROM visits ORDER BY id DESC LIMIT 1')->fetch());"
```
Expected: счётчик ≥ 1, последняя строка содержит `utm_source = "yandex"`.

- [ ] **Step 5: Commit**

```bash
git add api/track.php
git commit -m "feat(api): эндпоинт track.php — приём маячков посетителей"
```

---

## Task 3: Привязка визита к клиенту в send.php

**Files:**
- Modify: `send.php` (чтение `sh_vid` из тела + апдейт visitors после записи заявки)

- [ ] **Step 1: Прочитать sh_vid из входных данных**

В `send.php` найти блок чтения полей (после `$items = $data['items'] ?? [];`, ~строка 27) и добавить строку:

```php
$shVid    = trim($data['sh_vid'] ?? '');
```

- [ ] **Step 2: Привязать визит к клиенту**

В `send.php`, внутри существующего `try { ... } catch` блока работы с БД (тот, что начинается `try { $dbFile = __DIR__ . '/db/init.php'; ...`), **после** получения `$db = getDB();` (есть и в ветке авторизованного, и гостя) добавить общий апдейт. Проще всего — добавить в самом конце `if (file_exists($dbFile)) { require_once $dbFile; ... }` блока, прямо перед его закрывающей `}` (но внутри try), следующий код:

```php
        // Привязка визита (cookie sh_vid) к оставившему заявку клиенту
        if ($shVid !== '' && preg_match('/^[a-f0-9\-]{8,40}$/i', $shVid)) {
            try {
                if (!isset($db)) $db = getDB();
                $db->prepare('UPDATE visitors SET linked_phone=?, linked_name=? WHERE vid=?')
                   ->execute([$phone, $name, $shVid]);
            } catch (Throwable $e) { error_log('[SplitHub link vid] ' . $e->getMessage()); }
        }
```

- [ ] **Step 3: Проверить синтаксис**

Run: `php -l send.php`
Expected: `No syntax errors detected`

- [ ] **Step 4: Функциональная проверка**

С запущенным `php -S localhost:8000` создать визит и затем заявку с тем же vid:
```bash
curl -s -X POST http://localhost:8000/api/track.php -H "Content-Type: application/json" -d "{\"page\":\"/\"}" -c c.txt
VID=$(php -r "preg_match('/sh_vid\s+(\S+)/', file_get_contents('c.txt'), \$m); echo \$m[1]??'';")
curl -s -X POST http://localhost:8000/send.php -H "Content-Type: application/json" -d "{\"name\":\"Тест\",\"phone\":\"79991112233\",\"sh_vid\":\"$VID\",\"items\":[{\"name\":\"Товар\",\"price\":100,\"qty\":1}]}"
php -r "require 'db/init.php'; \$db=getDB(); var_dump(\$db->query(\"SELECT linked_phone,linked_name FROM visitors WHERE linked_phone!=''\")->fetchAll());"
```
Expected: у посетителя заполнены `linked_phone=79991112233`, `linked_name=Тест`. (Telegram/email-отправка может выдать ошибку без config.php — это нормально, нас интересует привязка.)

- [ ] **Step 5: Commit**

```bash
git add send.php
git commit -m "feat(send): привязка визита sh_vid к клиенту при заявке"
```

---

## Task 4: Яндекс.Метрика в index.html

**Files:**
- Modify: `index.html` (вставить сниппет перед `</head>`, строка ~1053)

- [ ] **Step 1: Вставить сниппет Метрики**

В `index.html` найти `</head>` и **перед ним** вставить:

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

- [ ] **Step 2: Проверить наличие**

Run: `grep -c "id=109740770" index.html`
Expected: `1` (в src тега; всего вхождений номера 109740770 — несколько, это ок).

Run: `grep -c "mc.yandex.ru/metrika/tag.js" index.html`
Expected: `1`

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(site): подключение Яндекс.Метрики (109740770)"
```

---

## Task 5: Плашка согласия cookie в index.html

**Files:**
- Modify: `index.html` (HTML-плашка перед `</body>` + стиль + JS-логика)

- [ ] **Step 1: Добавить HTML+CSS+JS плашки перед `</body>`**

В `index.html` найти `</body>` и **перед ним** вставить:

```html
<!-- Cookie notice (уведомление без блокировки) -->
<div id="shCookieBar" style="display:none;position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#1A1C22;color:#fff;padding:12px 16px;font-size:0.82rem;line-height:1.4;box-shadow:0 -2px 12px rgba(0,0,0,.2)">
  <div style="max-width:1100px;margin:0 auto;display:flex;gap:12px;align-items:center;flex-wrap:wrap;justify-content:center">
    <span style="flex:1;min-width:220px">Мы используем cookie и Яндекс.Метрику для аналитики и улучшения сайта.</span>
    <button id="shCookieOk" style="background:#F59E0B;color:#1A1C22;border:none;border-radius:8px;padding:8px 18px;font-weight:700;cursor:pointer">Понятно</button>
  </div>
</div>
<script>
(function(){
  try {
    if (!localStorage.getItem('sh_cookie_ok')) {
      var bar = document.getElementById('shCookieBar');
      if (bar) {
        bar.style.display = 'block';
        var btn = document.getElementById('shCookieOk');
        if (btn) btn.addEventListener('click', function(){
          try { localStorage.setItem('sh_cookie_ok','1'); } catch(e){}
          bar.style.display = 'none';
        });
      }
    }
  } catch(e){}
})();
</script>
<!-- /Cookie notice -->
```

- [ ] **Step 2: Проверить наличие**

Run: `grep -c "shCookieBar" index.html`
Expected: `2` (контейнер + чтение в JS).

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(site): плашка-уведомление о cookie (без блокировки)"
```

---

## Task 6: Маячок трекинга + передача sh_vid в заявке

**Files:**
- Modify: `index.html` (JS-маячок перед `</body>`; добавить `sh_vid` в payload `sendOrder`, строка ~1782)

- [ ] **Step 1: Добавить отправку маячка**

В `index.html` перед `</body>` (можно сразу после блока Cookie notice из Task 5) вставить:

```html
<!-- Visitor tracking beacon -->
<script>
(function(){
  try {
    function getCookie(n){ var m=document.cookie.match('(^|;)\\s*'+n+'\\s*=\\s*([^;]+)'); return m?m.pop():''; }
    var qs = new URLSearchParams(location.search);
    var payload = {
      page: location.pathname + location.search,
      referrer: document.referrer || '',
      utm_source: qs.get('utm_source') || '',
      utm_medium: qs.get('utm_medium') || '',
      utm_campaign: qs.get('utm_campaign') || '',
      device: (window.matchMedia && window.matchMedia('(max-width:768px)').matches) ? 'mobile' : 'desktop'
    };
    var body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      navigator.sendBeacon('api/track.php', new Blob([body], {type:'application/json'}));
    } else {
      fetch('api/track.php', {method:'POST', headers:{'Content-Type':'application/json'}, body:body, keepalive:true}).catch(function(){});
    }
    window.shGetVid = function(){ return getCookie('sh_vid'); };
  } catch(e){}
})();
</script>
<!-- /Visitor tracking beacon -->
```

- [ ] **Step 2: Передать sh_vid в payload заявки**

В `index.html` в функции `sendOrder` найти объявление `var payload = {` (строка ~1768) и в объект `payload` добавить поле `sh_vid`. Заменить:

```js
  var payload = {
    name: n, phone: p,
    comment: comment.trim(),
    client_tg: tg.trim(),
```

на:

```js
  var payload = {
    name: n, phone: p,
    comment: comment.trim(),
    client_tg: tg.trim(),
    sh_vid: (window.shGetVid ? window.shGetVid() : ''),
```

- [ ] **Step 3: Проверить наличие**

Run: `grep -c "api/track.php" index.html`
Expected: `1`

Run: `grep -c "sh_vid:" index.html`
Expected: `1`

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat(site): маячок трекинга + передача sh_vid в заявке"
```

---

## Task 7: Нативный генератор XLSX (api/lib/xlsx_writer.php)

**Files:**
- Create: `api/lib/xlsx_writer.php`

- [ ] **Step 1: Создать файл**

Создать `api/lib/xlsx_writer.php`:

```php
<?php
/**
 * SimpleXlsxWriter — минимальный генератор .xlsx без зависимостей.
 * XLSX = zip-архив с OOXML внутри. Поддержка: несколько листов,
 * жирная шапка, автофильтр, числа vs текст, UTF-8/кириллица.
 *
 * Использование:
 *   $w = new SimpleXlsxWriter();
 *   $w->addSheet('Клиенты', [['ID','Имя'], [1,'Иван']]);
 *   $w->download('export.xlsx'); // шлёт заголовки и тело, exit вызывающий
 */
class SimpleXlsxWriter {
    private $sheets = []; // [ ['name'=>..., 'rows'=>[[...],...]], ... ]

    public function addSheet($name, array $rows) {
        // Имя листа: ≤31 символ, без : \ / ? * [ ]
        $name = preg_replace('/[:\\\\\/\?\*\[\]]/u', ' ', (string)$name);
        $name = trim(mb_substr($name, 0, 31));
        if ($name === '') $name = 'Лист' . (count($this->sheets) + 1);
        $this->sheets[] = ['name' => $name, 'rows' => array_values($rows)];
    }

    private function esc($s) {
        return htmlspecialchars((string)$s, ENT_QUOTES | ENT_XML1, 'UTF-8');
    }

    private function colLetter($n) { // 0 -> A, 26 -> AA
        $s = '';
        $n++;
        while ($n > 0) { $r = ($n - 1) % 26; $s = chr(65 + $r) . $s; $n = intval(($n - 1) / 26); }
        return $s;
    }

    private function sheetXml(array $sheet) {
        $rows = $sheet['rows'];
        $rowCount = count($rows);
        $colCount = 0;
        foreach ($rows as $r) $colCount = max($colCount, count($r));
        $dim = 'A1:' . $this->colLetter(max(0, $colCount - 1)) . max(1, $rowCount);

        $xml  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $xml .= '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">';
        $xml .= '<dimension ref="' . $dim . '"/>';
        $xml .= '<sheetData>';
        foreach ($rows as $ri => $row) {
            $rn = $ri + 1;
            $xml .= '<row r="' . $rn . '">';
            $ci = 0;
            foreach ($row as $val) {
                $cell = $this->colLetter($ci) . $rn;
                $isHeader = ($ri === 0);
                $style = $isHeader ? ' s="1"' : '';
                if (is_int($val) || (is_string($val) && $val !== '' && preg_match('/^-?\d{1,15}$/', $val))) {
                    $xml .= '<c r="' . $cell . '"' . $style . '><v>' . $this->esc($val) . '</v></c>';
                } else {
                    $xml .= '<c r="' . $cell . '"' . $style . ' t="inlineStr"><is><t xml:space="preserve">' . $this->esc($val) . '</t></is></c>';
                }
                $ci++;
            }
            $xml .= '</row>';
        }
        $xml .= '</sheetData>';
        if ($rowCount > 0 && $colCount > 0) {
            $af = 'A1:' . $this->colLetter($colCount - 1) . $rowCount;
            $xml .= '<autoFilter ref="' . $af . '"/>';
        }
        $xml .= '</worksheet>';
        return $xml;
    }

    private function build() {
        $n = count($this->sheets);
        if ($n === 0) { $this->addSheet('Лист1', [['']]); $n = 1; }

        $contentTypes  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $contentTypes .= '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">';
        $contentTypes .= '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>';
        $contentTypes .= '<Default Extension="xml" ContentType="application/xml"/>';
        $contentTypes .= '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>';
        $contentTypes .= '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>';
        for ($i = 1; $i <= $n; $i++) {
            $contentTypes .= '<Override PartName="/xl/worksheets/sheet' . $i . '.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
        }
        $contentTypes .= '</Types>';

        $rootRels  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $rootRels .= '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">';
        $rootRels .= '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>';
        $rootRels .= '</Relationships>';

        $wbSheets = ''; $wbRels = '';
        $wbRels .= '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>';
        for ($i = 1; $i <= $n; $i++) {
            $nm = htmlspecialchars($this->sheets[$i - 1]['name'], ENT_QUOTES | ENT_XML1, 'UTF-8');
            $wbSheets .= '<sheet name="' . $nm . '" sheetId="' . $i . '" r:id="rId' . $i . '"/>';
            $wbRels   .= '<Relationship Id="rId' . $i . '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet' . $i . '.xml"/>';
        }
        $workbook  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $workbook .= '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">';
        $workbook .= '<sheets>' . $wbSheets . '</sheets></workbook>';

        $wbRelsXml  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $wbRelsXml .= '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' . $wbRels . '</Relationships>';

        // styles: s="1" = жирный шрифт для шапки
        $styles  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $styles .= '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">';
        $styles .= '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>';
        $styles .= '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>';
        $styles .= '<borders count="1"><border/></borders>';
        $styles .= '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>';
        $styles .= '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>';
        $styles .= '</styleSheet>';

        $tmp = tempnam(sys_get_temp_dir(), 'xlsx');
        $zip = new ZipArchive();
        if ($zip->open($tmp, ZipArchive::OVERWRITE) !== true) {
            throw new RuntimeException('Не удалось создать xlsx-архив');
        }
        $zip->addFromString('[Content_Types].xml', $contentTypes);
        $zip->addFromString('_rels/.rels', $rootRels);
        $zip->addFromString('xl/workbook.xml', $workbook);
        $zip->addFromString('xl/_rels/workbook.xml.rels', $wbRelsXml);
        $zip->addFromString('xl/styles.xml', $styles);
        for ($i = 1; $i <= $n; $i++) {
            $zip->addFromString('xl/worksheets/sheet' . $i . '.xml', $this->sheetXml($this->sheets[$i - 1]));
        }
        $zip->close();
        return $tmp;
    }

    public function download($filename) {
        $tmp = $this->build();
        $data = file_get_contents($tmp);
        @unlink($tmp);
        header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        header('Content-Disposition: attachment; filename="' . preg_replace('/[^A-Za-z0-9_\-\.]/', '_', $filename) . '"');
        header('Content-Length: ' . strlen($data));
        echo $data;
    }

    public function save($path) {
        $tmp = $this->build();
        copy($tmp, $path);
        @unlink($tmp);
    }
}
```

- [ ] **Step 2: Проверить синтаксис**

Run: `php -l api/lib/xlsx_writer.php`
Expected: `No syntax errors detected`

- [ ] **Step 3: Сгенерировать тестовый файл**

Run:
```bash
php -r "require 'api/lib/xlsx_writer.php'; \$w=new SimpleXlsxWriter(); \$w->addSheet('Клиенты',[['ID','Имя','Сумма'],[1,'Иван Петров',1500],[2,'ООО Тест',99999]]); \$w->addSheet('Пусто',[['A','B']]); \$w->save('test_out.xlsx'); echo 'saved ' . filesize('test_out.xlsx') . ' bytes';"
```
Expected: `saved N bytes` (N > 0).

- [ ] **Step 4: Валидировать xlsx Python-ом (openpyxl)**

Run:
```bash
pip install --quiet openpyxl 2>/dev/null; python -c "import openpyxl; wb=openpyxl.load_workbook('test_out.xlsx'); print(wb.sheetnames); ws=wb['Клиенты']; print([c.value for c in ws[1]]); print(ws['B2'].value, ws['C3'].value)"
```
Expected: `['Клиенты', 'Пусто']`, заголовки `['ID', 'Имя', 'Сумма']`, `Иван Петров 99999`. Файл открывается без ошибок — структура валидна.

- [ ] **Step 5: Убрать тестовый файл и закоммитить**

```bash
rm -f test_out.xlsx
git add api/lib/xlsx_writer.php
git commit -m "feat(lib): нативный генератор xlsx без зависимостей"
```

---

## Task 8: Admin-action export_xlsx (3 листа)

**Files:**
- Modify: `api/admin.php` (ранний хук перед auth-блоком + функция `exportXlsx`)

- [ ] **Step 1: Добавить ранний хук экспорта**

В `api/admin.php` найти блок CSV-экспорта (строки 27–31):

```php
if ($action === 'export_orders_csv') {
    adminRequire();
    exportOrdersCsv(getDB());
    exit;
}
```

и **сразу после него** (перед `adminRequire();` на строке 33) вставить:

```php
if ($action === 'export_xlsx') {
    adminRequire();
    require_once __DIR__ . '/lib/xlsx_writer.php';
    exportXlsx(getDB());
    exit;
}
```

- [ ] **Step 2: Добавить функцию exportXlsx**

В `api/admin.php` в самый конец файла (после функции `exportOrdersCsv`, строка ~481) добавить:

```php
function exportXlsx($db) {
    $smap = ['new'=>'Новый','confirmed'=>'Подтверждён','in_progress'=>'В работе','shipped'=>'Отгружен','completed'=>'Выполнен','cancelled'=>'Отменён'];

    // ── Лист «Клиенты» ──
    $clients = [[
        'ID','Тип','Имя','Телефон','Telegram','Компания','ИНН','КПП','Юр.адрес',
        'Дата регистрации','Кол-во заказов','Сумма заказов ₽'
    ]];
    $urows = $db->query("
        SELECT u.id, u.name, u.phone, u.telegram,
               COALESCE(u.company_name,'') company_name, COALESCE(u.inn,'') inn,
               COALESCE(u.kpp,'') kpp, COALESCE(u.legal_address,'') legal_address,
               u.created_at,
               (SELECT COUNT(*) FROM orders WHERE user_id=u.id) oc,
               (SELECT COALESCE(SUM(total),0) FROM orders WHERE user_id=u.id) os
        FROM users u ORDER BY u.created_at DESC
    ")->fetchAll();
    foreach ($urows as $r) {
        $clients[] = [
            (int)$r['id'], 'Зарегистрирован', $r['name'], $r['phone'], $r['telegram'],
            $r['company_name'], $r['inn'], $r['kpp'], $r['legal_address'],
            $r['created_at'], (int)$r['oc'], (int)$r['os']
        ];
    }
    // Гости, агрегированные по телефону
    $grows = $db->query("
        SELECT name, phone, COUNT(*) cnt, COALESCE(SUM(total),0) sm, MIN(created_at) first_at
        FROM guest_orders GROUP BY phone ORDER BY first_at DESC
    ")->fetchAll();
    foreach ($grows as $r) {
        $clients[] = [
            '', 'Гость', $r['name'], $r['phone'], '', '', '', '', '',
            $r['first_at'], (int)$r['cnt'], (int)$r['sm']
        ];
    }

    // ── Лист «Заказы» ──
    $orders = [[
        '№','Тип','Дата','Клиент','Телефон','Telegram','Сумма ₽','Статус',
        'Бонусов начислено','Бонусов списано','Заметка','Комментарий','Источник'
    ]];
    $orows = $db->query("
        SELECT o.id, o.created_at, u.name, u.phone, u.telegram, o.total, o.status,
               o.bonus_earned, o.bonus_spent, COALESCE(o.admin_note,'') admin_note, o.comment
        FROM orders o JOIN users u ON o.user_id=u.id ORDER BY o.created_at DESC LIMIT 10000
    ")->fetchAll();
    // Источник по телефону из visitors (последний привязанный)
    $srcByPhone = [];
    try {
        foreach ($db->query("SELECT linked_phone, first_utm_source, first_referrer FROM visitors WHERE linked_phone!=''")->fetchAll() as $v) {
            $src = $v['first_utm_source'] !== '' ? $v['first_utm_source'] : ($v['first_referrer'] !== '' ? $v['first_referrer'] : '');
            if ($src !== '') $srcByPhone[$v['linked_phone']] = $src;
        }
    } catch (Throwable $e) {}
    foreach ($orows as $r) {
        $orders[] = [
            'SH-'.str_pad($r['id'],5,'0',STR_PAD_LEFT), 'Клиент', $r['created_at'],
            $r['name'], $r['phone'], $r['telegram'], (int)$r['total'],
            $smap[$r['status']] ?? $r['status'], (int)$r['bonus_earned'], (int)$r['bonus_spent'],
            $r['admin_note'], $r['comment'], $srcByPhone[$r['phone']] ?? ''
        ];
    }
    // Гостевые заказы
    $gord = $db->query("SELECT id, created_at, name, phone, total, COALESCE(comment,'') comment FROM guest_orders ORDER BY created_at DESC LIMIT 10000")->fetchAll();
    foreach ($gord as $r) {
        $orders[] = [
            'G-'.str_pad($r['id'],5,'0',STR_PAD_LEFT), 'Гость', $r['created_at'],
            $r['name'], $r['phone'], '', (int)$r['total'], '—', 0, 0, '', $r['comment'],
            $srcByPhone[$r['phone']] ?? ''
        ];
    }

    // ── Лист «Посетители» ──
    $visitors = [[
        'ID посетителя','Первый визит','Последний визит','Кол-во визитов','Источник (referrer)',
        'UTM source','UTM medium','UTM campaign','Устройство','IP','Привязанный клиент'
    ]];
    try {
        $vrows = $db->query("SELECT * FROM visitors ORDER BY last_seen DESC LIMIT 20000")->fetchAll();
        foreach ($vrows as $r) {
            $linked = trim(($r['linked_name'] ?? '') . ' ' . ($r['linked_phone'] ?? ''));
            $visitors[] = [
                $r['vid'], $r['first_seen'], $r['last_seen'], (int)$r['visits_count'],
                $r['first_referrer'], $r['first_utm_source'], $r['first_utm_medium'],
                $r['first_utm_campaign'], $r['device'], $r['last_ip'], $linked
            ];
        }
    } catch (Throwable $e) {}

    $w = new SimpleXlsxWriter();
    $w->addSheet('Клиенты', $clients);
    $w->addSheet('Заказы', $orders);
    $w->addSheet('Посетители', $visitors);
    $w->download('splithub_export_' . date('Y-m-d') . '.xlsx');
}
```

- [ ] **Step 3: Проверить синтаксис**

Run: `php -l api/admin.php`
Expected: `No syntax errors detected`

- [ ] **Step 4: Сгенерировать через CLI-эмуляцию и проверить openpyxl**

Run (вызывает функцию напрямую, без auth-слоя):
```bash
php -r "require 'db/init.php'; require 'api/lib/xlsx_writer.php'; \$db=getDB(); function header(\$h){} ; \$w=new SimpleXlsxWriter(); \$w->save('exp.xlsx'); echo 'writer ok';"
```
Затем полноценная проверка трёх листов через временный скрипт:
```bash
php -r "
require 'db/init.php'; require 'api/lib/xlsx_writer.php';
\$db=getDB();
\$w=new SimpleXlsxWriter();
\$w->addSheet('Клиенты',[['ID','Имя']]);
\$w->addSheet('Заказы',[['№','Клиент']]);
\$w->addSheet('Посетители',[['ID посетителя','IP']]);
\$w->save('exp.xlsx'); echo 'ok';
"
python -c "import openpyxl; wb=openpyxl.load_workbook('exp.xlsx'); print(wb.sheetnames)"
rm -f exp.xlsx
```
Expected: `['Клиенты', 'Заказы', 'Посетители']`.

> Полная проверка `exportXlsx` с реальными данными и заголовками — после деплоя через браузер (Step ниже в Task 10) либо на сервере с тестовой БД.

- [ ] **Step 5: Commit**

```bash
git add api/admin.php
git commit -m "feat(admin): экспорт export_xlsx — Клиенты/Заказы/Посетители"
```

---

## Task 9: Admin-action visitors_list

**Files:**
- Modify: `api/admin.php` (новый `case 'visitors_list'` в switch)

- [ ] **Step 1: Добавить case в switch**

В `api/admin.php` внутри `switch ($action) {` добавить новый case (например, перед `case 'promo_list':`):

```php
    // ── Список посетителей (постранично) ──
    case 'visitors_list':
        $page  = max(1, (int)($_GET['page'] ?? 1));
        $limit = 50;
        $off   = ($page - 1) * $limit;
        $total = (int)$db->query('SELECT COUNT(*) FROM visitors')->fetchColumn();
        $stmt  = $db->prepare('SELECT vid, first_seen, last_seen, visits_count, first_referrer, first_utm_source, first_utm_medium, first_utm_campaign, device, last_ip, linked_name, linked_phone FROM visitors ORDER BY last_seen DESC LIMIT ? OFFSET ?');
        $stmt->bindValue(1, $limit, PDO::PARAM_INT);
        $stmt->bindValue(2, $off, PDO::PARAM_INT);
        $stmt->execute();
        jsonResponse(['ok' => true, 'visitors' => $stmt->fetchAll(), 'total' => $total, 'page' => $page, 'pages' => (int)ceil($total / $limit)]);
        break;
```

- [ ] **Step 2: Проверить синтаксис**

Run: `php -l api/admin.php`
Expected: `No syntax errors detected`

- [ ] **Step 3: Функциональная проверка**

С запущенным `php -S localhost:8000` (требуется авторизованная админ-сессия — проверять после Task 10/деплоя через браузер DevTools, либо временно закомментировать `adminRequire()` локально для curl-проверки и вернуть обратно):
```bash
curl -s "http://localhost:8000/api/admin.php?action=visitors_list" | python -c "import sys,json; d=json.load(sys.stdin); print('ok' in d, 'visitors' in d)"
```
Expected: `True True` (структура ответа корректна).

- [ ] **Step 4: Commit**

```bash
git add api/admin.php
git commit -m "feat(admin): visitors_list — список посетителей для админки"
```

---

## Task 10: Кнопка экспорта XLSX в admin.html

**Files:**
- Modify: `admin.html` (кнопка рядом с CSV-экспортом, использует `action=export_xlsx`)

- [ ] **Step 1: Найти место CSV-экспорта**

В `admin.html` около строки 1073 есть формирование URL CSV:
```js
  var url='api/admin.php?action=export_orders_csv&search='+q+'&status='+st+'&date_from='+df+'&date_to='+dt;
```
Найти кнопку, которая вызывает эту функцию (в пане `pane-orders`, ~строки 453–476). Рядом с ней добавить новую кнопку.

- [ ] **Step 2: Добавить кнопку XLSX**

В `admin.html` в пане заказов (`<div class="tab-pane active" id="pane-orders">`, около кнопки CSV-экспорта) добавить:

```html
<button class="tab-btn" style="border:1px solid var(--blo);border-radius:8px" onclick="window.location='api/admin.php?action=export_xlsx'">&#128202; Скачать Excel (.xlsx)</button>
```

(Точное место — рядом с существующей кнопкой выгрузки CSV; если её нет в разметке, разместить в шапке пана `pane-orders` перед таблицей.)

- [ ] **Step 3: Проверить наличие**

Run: `grep -c "action=export_xlsx" admin.html`
Expected: `1`

- [ ] **Step 4: Commit**

```bash
git add admin.html
git commit -m "feat(admin-ui): кнопка скачивания Excel (.xlsx)"
```

---

## Task 11: Раздел «Посетители» в admin.html

**Files:**
- Modify: `admin.html` (вкладка в tab-bar + pane + JS-загрузчик)

- [ ] **Step 1: Добавить вкладку в tab-bar**

В `admin.html` в `<div class="tab-bar">` (строки 437–445) после кнопки «Аналитика» добавить:

```html
    <button class="tab-btn" onclick="switchTab('visitors')">&#128065; Посетители</button>
```

- [ ] **Step 2: Добавить pane**

В `admin.html` после пане аналитики (`<div class="tab-pane" id="pane-analytics">...</div>`, заканчивается ~строка 577) добавить новый pane:

```html
    <div class="tab-pane" id="pane-visitors">
      <h3 style="margin:0 0 12px;font-size:1rem">Посетители сайта</h3>
      <div id="visitorsBox" style="overflow-x:auto">
        <table class="usr-table"><thead><tr>
          <th>ID</th><th>Первый визит</th><th>Последний</th><th>Визитов</th>
          <th>Источник</th><th>UTM source</th><th>Устройство</th><th>IP</th><th>Клиент</th>
        </tr></thead><tbody id="visitorsBody"><tr><td colspan="9">Загрузка…</td></tr></tbody></table>
      </div>
      <div id="visitorsPager" style="margin-top:12px;display:flex;gap:8px;align-items:center"></div>
    </div>
```

- [ ] **Step 3: Подключить загрузку в switchTab**

В `admin.html` в функции `switchTab` (строка ~1015) рядом со строкой `if(name==='users')loadUsers();` (строка ~1030) добавить:

```js
    if(name==='visitors')loadVisitors(1);
```

- [ ] **Step 4: Добавить функцию loadVisitors**

В `admin.html` рядом с `function loadUsers()` (строка ~1301) добавить:

```js
function loadVisitors(page){
  fetch('api/admin.php?action=visitors_list&page='+(page||1))
    .then(function(r){return r.json();})
    .then(function(d){
      var b=document.getElementById('visitorsBody'); if(!b) return;
      if(!d.ok || !d.visitors || !d.visitors.length){ b.innerHTML='<tr><td colspan="9">Пока нет данных</td></tr>'; document.getElementById('visitorsPager').innerHTML=''; return; }
      b.innerHTML = d.visitors.map(function(v){
        var client = ((v.linked_name||'')+' '+(v.linked_phone||'')).trim() || '—';
        var src = v.first_referrer || '—';
        function e(s){ return String(s==null?'':s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }
        return '<tr><td>'+e((v.vid||'').slice(0,8))+'…</td><td>'+e(v.first_seen)+'</td><td>'+e(v.last_seen)+'</td><td>'+e(v.visits_count)+'</td><td>'+e(src)+'</td><td>'+e(v.first_utm_source||'—')+'</td><td>'+e(v.device||'—')+'</td><td>'+e(v.last_ip||'—')+'</td><td>'+e(client)+'</td></tr>';
      }).join('');
      var pg=document.getElementById('visitorsPager');
      pg.innerHTML='Стр. '+d.page+' из '+d.pages+'  '+
        (d.page>1?'<button class="tab-btn" onclick="loadVisitors('+(d.page-1)+')">←</button>':'')+
        (d.page<d.pages?'<button class="tab-btn" onclick="loadVisitors('+(d.page+1)+')">→</button>':'');
    })
    .catch(function(){ var b=document.getElementById('visitorsBody'); if(b)b.innerHTML='<tr><td colspan="9">Ошибка загрузки</td></tr>'; });
}
```

- [ ] **Step 5: Проверить наличие**

Run: `grep -c "switchTab('visitors')" admin.html`
Expected: `1`
Run: `grep -c "function loadVisitors" admin.html`
Expected: `1`
Run: `grep -c "pane-visitors" admin.html`
Expected: `1`

- [ ] **Step 6: Commit**

```bash
git add admin.html
git commit -m "feat(admin-ui): раздел Посетители с постраничным списком"
```

---

## Task 12: Сквозная проверка после деплоя

**Files:** нет (ручная проверка).

- [ ] **Step 1: Метрика грузится**

Открыть сайт в браузере → DevTools → Network → есть запрос на `mc.yandex.ru/metrika/tag.js?id=109740770`, статус 200.

- [ ] **Step 2: Маячок и запись визита**

Перезагрузить страницу с `?utm_source=test123` → в Network есть POST `api/track.php` (200). В админке раздел «Посетители» показывает запись; источник/utm заполнены.

- [ ] **Step 3: Плашка cookie**

В новой инкогнито-вкладке внизу видна плашка «Понятно»; после клика исчезает и не появляется при перезагрузке.

- [ ] **Step 4: Привязка визита к клиенту**

Оформить тестовую заявку → в «Посетители» у соответствующего vid появился «Привязанный клиент» (имя/телефон).

- [ ] **Step 5: Экспорт xlsx**

В админке нажать «Скачать Excel (.xlsx)» → файл скачивается, открывается в Excel/LibreOffice, 3 листа (Клиенты/Заказы/Посетители), шапки жирные, работает автофильтр, графы заполнены.

- [ ] **Step 6: Финальный коммит (если были правки)**

```bash
git add -A && git commit -m "chore: завершение фичи аналитики и экспорта"
```

---

## Self-review (выполнено автором плана)

- **Покрытие спеки:** Блок A → Task 4; Блок B → Tasks 1,2,3,5,6,9,11; Блок C → Tasks 7,8,10. Сквозная проверка → Task 12. Все разделы спеки покрыты.
- **Плейсхолдеры:** отсутствуют — весь код приведён целиком.
- **Согласованность типов/имён:** `SimpleXlsxWriter` (методы `addSheet`/`download`/`save`), action `export_xlsx`, action `visitors_list`, cookie `sh_vid`, таблицы `visitors`/`visits` — имена единообразны во всех задачах.
- **Активные файлы:** правки идут в `db/init.php` и `api/admin.php` (не в легаси `db_init.php`/`api_admin.php`).
