# Сверка цен и наличия СплитХаб (по расписанию раз в сутки): обновляет остатки JAC,
# пересчитывает каталог по прайсам поставщиков, заливает на сайт через предохранитель
# (publish.py — скачки цены больше 25% не льёт) и присылает владельцу итог в Telegram.
# Упал шаг — повторяем; не вышло — сообщение о сбое, сайт при этом не трогаем.
#
#     .\run_sync.ps1              # полный прогон
#     .\run_sync.ps1 -SkipJac     # без перезапуска скрапера JAC

param([switch]$SkipJac, [switch]$SkipOasis)

$ErrorActionPreference = "Stop"
# Вывод python читаем как UTF-8, иначе в логе вместо кириллицы каракули.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# Вложенные скрипты запускаем тем же движком, что и нас. Жёстко прописанный
# powershell.exe — это Windows PowerShell 5.1: он теряет кавычки при передаче
# аргументов в ssh, и выгрузка SplitHome падала с «role root does not exist».
$engine = (Get-Process -Id $PID).Path
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

Write-Log ("=== Сверка цен " + (Get-Date -Format "dd.MM.yyyy HH:mm") + " ===")

if (-not $SkipJac) {
    $scraper = Join-Path $jacRoot "run_scrape.ps1"
    if (Test-Path $scraper) {
        Write-Log "Обновляю остатки JAC..."
        try {
            & $engine -NoProfile -ExecutionPolicy Bypass -File $scraper 2>&1 | Tee-Object -Variable jacOut | Out-Null
            Write-Log ($jacOut | Select-Object -Last 5 | Out-String).Trim()
        } catch {
            Write-Log ("JAC-скрапер упал, беру прошлый срез: " + $_.Exception.Message)
        }
    } else {
        Write-Log "JAC-скрапер не найден, беру прошлый срез jac_stock_latest.json"
    }
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
