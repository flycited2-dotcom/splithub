# Сверка цен и наличия СплитХаб (по расписанию каждую ночь): обновляет остатки JAC,
# пересчитывает каталог по прайсам поставщиков, заливает на сайт через предохранитель
# (publish.py — скачки цены больше 25% не льёт) и присылает владельцу итог в Telegram.
# Упал шаг — повторяем; не вышло — сообщение о сбое, сайт при этом не трогаем.
#
#     .\run_sync.ps1              # полный прогон
#     .\run_sync.ps1 -SkipJac     # без перезапуска скрапера JAC

#     .\run_sync.ps1 -JacOnly     # только собрать остатки JAC и отправить на сервер
#
# Когда сверку ведёт сервер (tools/price_sync/server/run_sync.sh, 04:00), компьютер
# запускается с -JacOnly: портал JAC серверным адресам отдаёт неполные данные, поэтому
# остатки JAC собираются здесь, а на сервер уезжает готовый файл.

param([switch]$SkipJac, [switch]$SkipOasis, [switch]$JacOnly)

$ErrorActionPreference = "Stop"
# Вывод python читаем как UTF-8, иначе в логе вместо кириллицы каракули.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# Вложенные скрипты запускаем тем же движком, что и нас. Жёстко прописанный
# powershell.exe — это Windows PowerShell 5.1: он теряет кавычки при передаче
# аргументов в ssh, и выгрузка SplitHome падала с «role root does not exist».
$engine = (Get-Process -Id $PID).Path

# Ночной прогон будит спящий компьютер таймером планировщика, и через пару минут
# без пользователя Windows усыпила бы его снова — посреди сверки. Просим систему не
# засыпать, пока идёт прогон (ES_CONTINUOUS | ES_SYSTEM_REQUIRED); запрос снимается
# сам, когда процесс завершится. Не вышло — не беда, сверка важнее.
try {
    Add-Type -Namespace SplitHub -Name Power -MemberDefinition `
        '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
    [SplitHub.Power]::SetThreadExecutionState([uint32]"0x80000001") | Out-Null
} catch { }

$syncRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$siteRoot = Split-Path -Parent (Split-Path -Parent $syncRoot)
$jacRoot  = "C:\Users\TLT-1\Documents\GitHub\osatakti_mdv_b2b"
$logDir   = Join-Path $syncRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("sync_" + (Get-Date -Format "yyyyMMdd_HHmm") + ".log")

function Write-Log([string]$text) {
    # Write-Host, а не Write-Output: вывод функции в PowerShell становится её
    # результатом, и Invoke-Step вернул бы массив строк лога — всегда «истинный»,
    # так что сообщение о сбое не ушло бы никогда.
    Write-Host $text
    Add-Content -Path $log -Value $text -Encoding UTF8
}

function Send-JacToServer {
    # Свежий срез JAC — на сервер: туда, откуда его берёт ночная сверка цен, и боту
    # остатков (его собственная доставка upload_to_vps.py с 31.08 падает на ключе).
    # Везём только полный срез — те же пороги, что у upload_to_vps.py: от 300 позиций,
    # у 100+ есть бренд. На сервере — через временный файл и mv, полуфайл не прочитают.
    $dir = Join-Path $jacRoot "data"
    try {
        $rows = @(Get-Content (Join-Path $dir "jac_stock_latest.json") -Raw -Encoding UTF8 | ConvertFrom-Json)
        $branded = @($rows | Where-Object { "$($_.brand)".Trim() }).Count
        if ($rows.Count -lt 300 -or $branded -lt 100) {
            Write-Log "Остатки JAC на сервер не отправляю: срез неполный ($($rows.Count) поз., с брендом $branded)"
            return
        }
        # Имя без диска: «C:\...» scp принял бы за адрес хоста «C».
        Push-Location $dir
        try {
            # -p и cp -p: время файла = время сбора, по нему сервер судит о свежести.
            scp -q -p "jac_stock_latest.json" "sprintbox-itp:/tmp/jac_stock_latest.json"
            if ($LASTEXITCODE -ne 0) { throw "scp вернул $LASTEXITCODE" }
        } finally {
            Pop-Location
        }
        $place = "set -e; for d in /opt/splithub-price-sync/jac/data /opt/splithub_api_telegram/data; do " +
            "mkdir -p `$d; cp -p /tmp/jac_stock_latest.json `$d/.jac_stock_latest.part; " +
            "chmod 644 `$d/.jac_stock_latest.part; mv -f `$d/.jac_stock_latest.part `$d/jac_stock_latest.json; done; " +
            "rm -f /tmp/jac_stock_latest.json; echo ok"
        $answer = ssh sprintbox-itp $place
        if ($LASTEXITCODE -ne 0 -or "$answer" -notmatch "ok") { throw "на сервере: $answer" }
        Write-Log "Остатки JAC отправлены на сервер: $($rows.Count) поз."
    } catch {
        Write-Log ("Остатки JAC на сервер не ушли: " + $_.Exception.Message)
    }
}

Write-Log ("=== Сверка цен " + (Get-Date -Format "dd.MM.yyyy HH:mm") + " ===")

if (-not $SkipJac) {
    $jacPy = Join-Path $jacRoot ".venv\Scripts\python.exe"
    if (Test-Path $jacPy) {
        Write-Log "Обновляю остатки JAC..."
        # Сам скрапер, без обёртки run_scrape.ps1: её шаг upload_to_vps.py с 31.08 падает
        # на ключе и каждый вечер слал в Telegram «сбой доставки». На сервер остатки везёт
        # Send-JacToServer, а повторы неполного сбора давно живут внутри скрапера.
        $saved = @{ PYTHONUTF8 = $env:PYTHONUTF8; NO_PROXY = $env:NO_PROXY }
        $env:PYTHONUTF8 = "1"
        $env:NO_PROXY = "*"   # портал — напрямую, мимо системного SOCKS-прокси
        Push-Location $jacRoot
        try {
            & $jacPy -m jac_scraper scrape 2>&1 | Tee-Object -Variable jacOut | Out-Null
            Write-Log ("JAC: код $LASTEXITCODE; " + ($jacOut | Select-Object -Last 2 | Out-String).Trim())
        } catch {
            Write-Log ("JAC-скрапер упал, беру прошлый срез: " + $_.Exception.Message)
        } finally {
            Pop-Location
            $env:PYTHONUTF8 = $saved.PYTHONUTF8
            $env:NO_PROXY = $saved.NO_PROXY
        }
    } else {
        Write-Log "JAC-скрапер не найден, беру прошлый срез jac_stock_latest.json"
    }
    Send-JacToServer
}

if ($JacOnly) {
    Write-Log "Готово: сверку цен и заливку ведёт сервер (04:00), отсюда — только остатки JAC."
    exit 0
}

if (-not $SkipOasis) {
    Write-Log "Выгружаю каталог SplitHome (Русклимат / Daichi / Бриз)..."
    try {
        & $engine -NoProfile -ExecutionPolicy Bypass -File (Join-Path $syncRoot "export_oasis.ps1") 2>&1 |
            Tee-Object -Variable oasisOut | Out-Null
        Write-Log ($oasisOut | Select-Object -Last 3 | Out-String).Trim()
    } catch {
        Write-Log ("Выгрузка SplitHome не удалась, беру прошлую: " + $_.Exception.Message)
    }
    # Опт Бриза (FUNAI, Royal Clima, Hisense, Ultima, XIGMA…) есть только в его API —
    # без этого шага цены этих брендов застывали на дате последнего ручного запроса
    # (так и было: с 11.09 по 24.09 опт Бриза не обновлялся).
    Write-Log "Запрашиваю опт-цены Бриза..."
    try {
        & $engine -NoProfile -ExecutionPolicy Bypass -File (Join-Path $syncRoot "export_breez.ps1") 2>&1 |
            Tee-Object -Variable breezOut | Out-Null
        Write-Log ($breezOut | Select-Object -Last 1 | Out-String).Trim()
    } catch {
        Write-Log ("Опт-цены Бриза не обновились, беру прошлые: " + $_.Exception.Message)
    }
}

function Invoke-Step([string]$title, [string]$module, [int]$attempts = 2) {
    # Шаг на python с повтором: сеть до поставщиков иногда рвётся на минуту-другую.
    Push-Location $siteRoot
    try {
        $env:PYTHONIOENCODING = "utf-8"
        for ($i = 1; $i -le $attempts; $i++) {
            $out = & python -m $module 2>&1
            $code = $LASTEXITCODE
            Write-Log ($out | Out-String).Trim()
            if ($code -eq 0) { return $true }
            if ($i -lt $attempts) {
                Write-Log "$title — попытка $i не удалась (код $code), повтор через 5 минут..."
                Start-Sleep -Seconds 300
            }
        }
        return $false
    } finally {
        Pop-Location
    }
}

function Stop-WithAlert([string]$step) {
    $text = "⚠️ СплитХаб " + (Get-Date -Format "dd.MM HH:mm") + ": сверка упала на шаге «$step». Сайт не тронут. Лог: " + (Split-Path -Leaf $log)
    Write-Log $text
    Push-Location $siteRoot
    try { & python -m tools.price_sync.notify $text | Out-Null } finally { Pop-Location }
    exit 1
}

Write-Log "Пересчитываю каталог по прайсам..."
if (-not (Invoke-Step "Пересчёт цен" "tools.price_sync.sync")) { Stop-WithAlert "пересчёт цен" }

Write-Log "Обновляю карточки новых товаров и собираю каталог..."
if (-not (Invoke-Step "Карточки" "tools.price_sync.new_cards" 1)) { Stop-WithAlert "карточки новых товаров" }
if (-not (Invoke-Step "Сборка каталога" "tools.price_sync.merge" 1)) { Stop-WithAlert "сборка каталога" }

Write-Log "Заливаю на сайт через предохранитель и отправляю итог в Telegram..."
if (-not (Invoke-Step "Заливка" "tools.price_sync.publish")) { exit 1 }   # publish сам шлёт причину

Write-Log ""
Write-Log "Готово. Дифф: $syncRoot\out\price_diff.csv"
