# Реквизиты юр.лица в кабинете — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать залогиненному клиенту в личном кабинете вкладку «Реквизиты» для ввода и повторного редактирования реквизитов юр.лица (Наименование/ИНН/КПП/Юр.адрес), сохраняемых в его профиль.

**Architecture:** Бэкенд — `api/auth.php`: `profile` и `login` начинают возвращать 4 поля реквизитов, плюс новое действие `update_requisites` (POST, под авторизацией, с валидацией). Фронт — `index.html`: новая вкладка «Реквизиты» в `renderDashTab`, форма с предзаполнением из `currentUser` и функция `saveRequisites()`. Колонки в `users` и Excel-экспорт уже готовы.

**Tech Stack:** PHP 7+/PDO/SQLite, ванильный JS, HTML.

## Окружение для проверки

- Активные файлы: `api/auth.php`, `index.html`. БД-колонки уже есть.
- PHP (портативный) из Bash:
  `PHP=/c/Users/TLT-1/php-portable/php.exe; INI=/c/Users/TLT-1/php-portable/php.ini`
  bash-путь для `php -l <file>`; Windows-путь (C:/...) внутри php-кода (require).
- Тестовый конфиг для запуска send/auth не нужен: `auth.php` НЕ требует внешний config.php
  (в отличие от send.php). Для серверных тестов задаём временную БД через `SPLITHUB_DB_PATH`.
- Bash working dir — родительская папка; используем абсолютные пути.

---

## Task 1: Бэкенд — auth.php (profile/login возвращают реквизиты + update_requisites)

**Files:**
- Modify: `api/auth.php`

- [ ] **Step 1: profile возвращает реквизиты**

В `api/auth.php`, в `case 'profile':`, заменить строку:

```php
        $stmt = $db->prepare('SELECT id, name, phone, telegram, role, created_at FROM users WHERE id = ?');
```

на:

```php
        $stmt = $db->prepare("SELECT id, name, phone, telegram, role, created_at, COALESCE(company_name,'') company_name, COALESCE(inn,'') inn, COALESCE(kpp,'') kpp, COALESCE(legal_address,'') legal_address FROM users WHERE id = ?");
```

- [ ] **Step 2: login возвращает реквизиты**

В `case 'login':` заменить блок ответа:

```php
        jsonResponse(['ok' => true, 'user' => [
            'id'   => (int)$user['id'],
            'name' => $user['name'],
            'phone' => $user['phone'],
            'role'  => $user['role']
        ]]);
```

на:

```php
        jsonResponse(['ok' => true, 'user' => [
            'id'    => (int)$user['id'],
            'name'  => $user['name'],
            'phone' => $user['phone'],
            'role'  => $user['role'],
            'company_name'  => $user['company_name'] ?? '',
            'inn'           => $user['inn'] ?? '',
            'kpp'           => $user['kpp'] ?? '',
            'legal_address' => $user['legal_address'] ?? ''
        ]]);
```

- [ ] **Step 3: новое действие update_requisites**

В `api/auth.php` добавить новый case (например, сразу после `case 'profile': ... break;`):

```php
    // ── Обновление реквизитов юр.лица (self-service в кабинете) ──
    case 'update_requisites':
        $uid = authRequire();
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        if (!is_array($raw)) $raw = [];
        $company = mb_substr(trim($raw['company_name'] ?? ''), 0, 255);
        $inn     = trim($raw['inn'] ?? '');
        $kpp     = trim($raw['kpp'] ?? '');
        $addr    = mb_substr(trim($raw['legal_address'] ?? ''), 0, 500);
        if ($inn !== '' && !preg_match('/^\d{10}(\d{2})?$/', $inn)) {
            jsonResponse(['ok' => false, 'error' => 'ИНН должен содержать 10 или 12 цифр'], 422);
        }
        if ($kpp !== '' && !preg_match('/^\d{9}$/', $kpp)) {
            jsonResponse(['ok' => false, 'error' => 'КПП должен содержать 9 цифр'], 422);
        }
        $db = getDB();
        $db->prepare('UPDATE users SET company_name = ?, inn = ?, kpp = ?, legal_address = ? WHERE id = ?')
           ->execute([$company, $inn, $kpp, $addr, $uid]);
        jsonResponse(['ok' => true, 'requisites' => [
            'company_name'  => $company,
            'inn'           => $inn,
            'kpp'           => $kpp,
            'legal_address' => $addr
        ]]);
        break;
```

(`authRequire`, `getDB`, `jsonResponse`, `$method` уже определены в проекте.)

- [ ] **Step 4: Проверить синтаксис**

Run: `"$PHP" -c "$INI" -l /c/Users/TLT-1/Documents/GitHub/site_splithub_08_06/splithub/api/auth.php`
Expected: `No syntax errors detected`.

- [ ] **Step 5: Функциональный тест (временная БД + встроенный сервер)**

```bash
PHP=/c/Users/TLT-1/php-portable/php.exe; INI=/c/Users/TLT-1/php-portable/php.ini; WREPO='C:/Users/TLT-1/Documents/GitHub/site_splithub_08_06/splithub'
export SPLITHUB_DB_PATH="$TEMP/sh_req_$$.sqlite"
# seed: пользователь с паролем
"$PHP" -c "$INI" -r "require '$WREPO/db/init.php'; \$d=getDB(); \$d->prepare('INSERT INTO users (name,phone,password_hash,role) VALUES (?,?,?,?)')->execute(['Иван','79991112233',password_hash('x1234',PASSWORD_BCRYPT),'client']);"
"$PHP" -c "$INI" -S 127.0.0.1:8021 -t "$WREPO" >/dev/null 2>&1 &
SRV=$!
for i in $(seq 1 25); do curl -s -o /dev/null "http://127.0.0.1:8021/api/auth.php?action=profile" && break; done
printf '{"phone":"79991112233","password":"x1234"}' > "$TEMP/lg.json"
curl -s -X POST "http://127.0.0.1:8021/api/auth.php?action=login" -H "Content-Type: application/json" --data-binary @"$TEMP/lg.json" -c "$TEMP/ck.txt" >/dev/null
# валидный сейв
printf '{"company_name":"ООО Ромашка","inn":"7701234567","kpp":"770101001","legal_address":"г. Москва"}' > "$TEMP/req.json"
echo "SAVE:"; curl -s -X POST "http://127.0.0.1:8021/api/auth.php?action=update_requisites" -H "Content-Type: application/json" --data-binary @"$TEMP/req.json" -b "$TEMP/ck.txt"
echo; echo "PROFILE:"; curl -s "http://127.0.0.1:8021/api/auth.php?action=profile" -b "$TEMP/ck.txt"
# невалидный ИНН -> 422
echo; printf '{"inn":"123"}' > "$TEMP/bad.json"
echo "BAD INN code:"; curl -s -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:8021/api/auth.php?action=update_requisites" -H "Content-Type: application/json" --data-binary @"$TEMP/bad.json" -b "$TEMP/ck.txt"
# гость -> 401
echo; echo "GUEST code:"; curl -s -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:8021/api/auth.php?action=update_requisites" -H "Content-Type: application/json" --data-binary @"$TEMP/req.json"
kill $SRV 2>/dev/null; rm -f "$SPLITHUB_DB_PATH"* "$TEMP/lg.json" "$TEMP/ck.txt" "$TEMP/req.json" "$TEMP/bad.json"
```
Expected: SAVE → `{"ok":true,"requisites":{...}}`; PROFILE → user содержит `company_name":"ООО Ромашка","inn":"7701234567"`; BAD INN code → `422`; GUEST code → `401`.

- [ ] **Step 6: Commit**

```bash
git -C /c/Users/TLT-1/Documents/GitHub/site_splithub_08_06/splithub add api/auth.php
git -C /c/Users/TLT-1/Documents/GitHub/site_splithub_08_06/splithub commit -m "feat(auth): реквизиты в profile/login + действие update_requisites"
```

---

## Task 2: Фронтенд — index.html (вкладка «Реквизиты» + форма + сохранение)

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Добавить вкладку «Реквизиты» в строку вкладок**

В `index.html`, в функции `renderDashTab`, заменить блок построения `tabs`:

```js
  var tabs = '<div class="dash-tabs">'
    + '<div class="dash-tab' + (tab==='orders'?' active':'') + '" onclick="renderDashTab(\'orders\')">Заказы</div>'
    + '<div class="dash-tab' + (tab==='profile'?' active':'') + '" onclick="renderDashTab(\'profile\')">Профиль</div>'
    + '</div>';
```

на:

```js
  var tabs = '<div class="dash-tabs">'
    + '<div class="dash-tab' + (tab==='orders'?' active':'') + '" onclick="renderDashTab(\'orders\')">Заказы</div>'
    + '<div class="dash-tab' + (tab==='profile'?' active':'') + '" onclick="renderDashTab(\'profile\')">Профиль</div>'
    + '<div class="dash-tab' + (tab==='requisites'?' active':'') + '" onclick="renderDashTab(\'requisites\')">Реквизиты</div>'
    + '</div>';
```

- [ ] **Step 2: Добавить ветку рендера вкладки «Реквизиты»**

В `renderDashTab`, найти конец ветки профиля:

```js
      + '<button class="auth-btn" style="background:#EF4444;box-shadow:0 3px 14px rgba(239,68,68,.3);margin-top:12px" onclick="doLogout()">Выйти из аккаунта</button>';
  }
}
```

и заменить на (добавляется `else if` перед закрывающими скобками):

```js
      + '<button class="auth-btn" style="background:#EF4444;box-shadow:0 3px 14px rgba(239,68,68,.3);margin-top:12px" onclick="doLogout()">Выйти из аккаунта</button>';

  } else if (tab === 'requisites') {
    var u = currentUser || {};
    function rq(v){ return String(v==null?'':v).replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
    body.innerHTML = tabs
      + '<div style="font-size:.78rem;line-height:1.5;color:var(--text2);background:rgba(245,158,11,.10);border:1px solid rgba(245,158,11,.30);border-radius:10px;padding:10px 12px;margin-bottom:14px">'
      + 'Заполните, если вы <b>юридическое лицо</b> — реквизиты сохранятся в вашем профиле для выставления счетов. Физлицам заполнять не нужно. Можно изменить в любой момент.'
      + '</div>'
      + '<div style="margin-bottom:11px"><label style="display:block;font-size:.68rem;font-weight:700;color:var(--text3);text-transform:uppercase;margin-bottom:5px">Наименование организации</label>'
      + '<input class="inp" id="rqCompany" type="text" placeholder="ООО Компания" value="' + rq(u.company_name) + '"></div>'
      + '<div style="display:flex;gap:10px">'
      + '<div style="flex:1"><label style="display:block;font-size:.68rem;font-weight:700;color:var(--text3);text-transform:uppercase;margin-bottom:5px">ИНН</label>'
      + '<input class="inp" id="rqInn" type="text" inputmode="numeric" placeholder="10 или 12 цифр" value="' + rq(u.inn) + '"></div>'
      + '<div style="flex:1"><label style="display:block;font-size:.68rem;font-weight:700;color:var(--text3);text-transform:uppercase;margin-bottom:5px">КПП</label>'
      + '<input class="inp" id="rqKpp" type="text" inputmode="numeric" placeholder="9 цифр" value="' + rq(u.kpp) + '"></div>'
      + '</div>'
      + '<label style="display:block;font-size:.68rem;font-weight:700;color:var(--text3);text-transform:uppercase;margin-bottom:5px">Юридический адрес</label>'
      + '<input class="inp" id="rqAddr" type="text" placeholder="г. Москва, ул. ..." value="' + rq(u.legal_address) + '">'
      + '<button class="auth-btn" id="rqSaveBtn" onclick="saveRequisites()">Сохранить реквизиты</button>'
      + '<div id="rqMsg" style="margin-top:10px;font-size:.8rem;text-align:center"></div>';
  }
}
```

(Класс `inp` — существующий стиль поля ввода на сайте, строка 383 в index.html: width:100%, фокус-обводка amber.)

- [ ] **Step 3: Добавить функцию saveRequisites**

В `index.html` сразу ПЕРЕД функцией `function renderDashTab(` добавить:

```js
function saveRequisites(){
  var btn = document.getElementById('rqSaveBtn');
  var msg = document.getElementById('rqMsg');
  var payload = {
    company_name: (document.getElementById('rqCompany')||{}).value || '',
    inn:          (document.getElementById('rqInn')||{}).value || '',
    kpp:          (document.getElementById('rqKpp')||{}).value || '',
    legal_address:(document.getElementById('rqAddr')||{}).value || ''
  };
  if (btn) { btn.disabled = true; btn.textContent = 'Сохранение...'; }
  fetch('api/auth.php?action=update_requisites', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)})
  .then(function(r){ return r.json(); })
  .then(function(d){
    if (btn) { btn.disabled = false; btn.textContent = 'Сохранить реквизиты'; }
    if (d.ok) {
      if (currentUser) {
        currentUser.company_name = d.requisites.company_name;
        currentUser.inn = d.requisites.inn;
        currentUser.kpp = d.requisites.kpp;
        currentUser.legal_address = d.requisites.legal_address;
      }
      if (msg) { msg.style.color = 'var(--green)'; msg.textContent = '✓ Реквизиты сохранены'; }
    } else {
      if (msg) { msg.style.color = '#EF4444'; msg.textContent = d.error || 'Ошибка сохранения'; }
    }
  })
  .catch(function(){
    if (btn) { btn.disabled = false; btn.textContent = 'Сохранить реквизиты'; }
    if (msg) { msg.style.color = '#EF4444'; msg.textContent = 'Ошибка сети'; }
  });
}
```

- [ ] **Step 4: Проверить наличие (grep)**

```bash
REPO=/c/Users/TLT-1/Documents/GitHub/site_splithub_08_06/splithub
grep -c "renderDashTab('requisites')" "$REPO/index.html"   # ожидание: 1
grep -c "function saveRequisites" "$REPO/index.html"        # 1
grep -c "action=update_requisites" "$REPO/index.html"       # 1
grep -c "rqCompany\|rqInn\|rqKpp\|rqAddr" "$REPO/index.html" # >= 8 (объявления + чтение)
grep -c "</body>" "$REPO/index.html"                        # 1 (структура цела)
```

- [ ] **Step 5: Подтвердить класс inp существует**

```bash
grep -c "^\.inp{" /c/Users/TLT-1/Documents/GitHub/site_splithub_08_06/splithub/index.html
```
Expected: 1 (базовый стиль поля ввода, строка 383). Форма использует этот класс.

- [ ] **Step 6: Визуальная проверка (опц., если поднят preview)**

Открыть кабинет → вкладка «Реквизиты»: поля предзаполнены, кнопка активна, после «Сохранить» — «✓ Реквизиты сохранены».

- [ ] **Step 7: Commit**

```bash
git -C /c/Users/TLT-1/Documents/GitHub/site_splithub_08_06/splithub add index.html
git -C /c/Users/TLT-1/Documents/GitHub/site_splithub_08_06/splithub commit -m "feat(cabinet): вкладка Реквизиты с редактируемой формой юр.лица"
```

---

## Task 3: Сквозная проверка (после деплоя)

- [ ] Залогиниться на сайте → ЛК → «Реквизиты»: поля пустые у нового клиента.
- [ ] Заполнить, сохранить → «✓ Реквизиты сохранены».
- [ ] Закрыть и снова открыть вкладку → поля предзаполнены сохранённым (редактируемость/persist).
- [ ] Изменить значение, сохранить → перезаписалось; очистить поле, сохранить → пусто.
- [ ] Неверный ИНН → сообщение об ошибке, без сохранения.
- [ ] В админке экспорт Excel → лист «Клиенты» содержит реквизиты этого клиента.

---

## Self-review

- **Покрытие спеки:** вкладка «Реквизиты» → Task 2; profile/login возвращают поля → Task 1 ш.1-2;
  update_requisites + валидация ИНН/КПП → Task 1 ш.3; редактируемость (предзаполнение из
  currentUser + перезапись) → Task 1 ш.1-2 (profile/login) + Task 2 ш.2-3; 401/422 → Task 1 ш.5;
  попадание в экспорт → Task 3 (экспорт уже читает колонки). Все пункты покрыты.
- **Плейсхолдеры:** нет — весь код приведён.
- **Согласованность имён:** действие `update_requisites`; поля `company_name/inn/kpp/legal_address`;
  id полей формы `rqCompany/rqInn/rqKpp/rqAddr`; функция `saveRequisites`; вкладка `requisites` —
  единообразны во всех задачах и совпадают с колонками БД и запросами экспорта.
- **Класс CSS:** форма использует существующий `inp` (проверено: строка 383 index.html); Task 2 ш.5 подтверждает наличие.
