# Сверка цен СплитХаб (по расписанию раз в 3 дня): обновляет остатки JAC, пересчитывает каталог
# по прайсам поставщиков и кладёт результат в tools\price_sync\out.
# НИЧЕГО НЕ ДЕПЛОИТ — заливка на сайт только руками, после просмотра price_diff.csv.
#
#     .\run_sync.ps1              # полный прогон
#     .\run_sync.ps1 -SkipJac     # без перезапуска скрапера JAC

param([switch]$SkipJac, [switch]$SkipOasis)

$ErrorActionPreference = "Stop"
$syncRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$siteRoot = Split-Path -Parent (Split-Path -Parent $syncRoot)
$jacRoot  = "C:\Users\TLT-1\Documents\GitHub\osatakti_mdv_b2b"
$logDir   = Join-Path $syncRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("sync_" + (Get-Date -Format "yyyyMMdd_HHmm") + ".log")

function Write-Log([string]$text) {
    Write-Output $text
    Add-Content -Path $log -Value $text -Encoding UTF8
}

Write-Log ("=== Сверка цен " + (Get-Date -Format "dd.MM.yyyy HH:mm") + " ===")

if (-not $SkipJac) {
    $scraper = Join-Path $jacRoot "run_scrape.ps1"
    if (Test-Path $scraper) {
        Write-Log "Обновляю остатки JAC..."
        try {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $scraper 2>&1 | Tee-Object -Variable jacOut | Out-Null
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
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $syncRoot "export_oasis.ps1") 2>&1 |
            Tee-Object -Variable oasisOut | Out-Null
        Write-Log ($oasisOut | Select-Object -Last 3 | Out-String).Trim()
    } catch {
        Write-Log ("Выгрузка SplitHome не удалась, беру прошлую: " + $_.Exception.Message)
    }
}

Write-Log "Пересчитываю каталог по прайсам..."
Push-Location $siteRoot
try {
    $env:PYTHONIOENCODING = "utf-8"
    $result = & python -m tools.price_sync.sync 2>&1
    Write-Log ($result | Out-String).Trim()
} finally {
    Pop-Location
}

Write-Log "Обновляю карточки новых товаров и собираю каталог..."
Push-Location $siteRoot
try {
    $env:PYTHONIOENCODING = "utf-8"
    $cards = & python -m tools.price_sync.new_cards 2>&1
    Write-Log ($cards | Out-String).Trim()
    $catalog = & python -m tools.price_sync.merge 2>&1
    Write-Log ($catalog | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { Write-Log "ВНИМАНИЕ: каталог не собран, см. замечания выше." }
} finally {
    Pop-Location
}

Write-Log ""
Write-Log "Готово. Смотри дифф: $syncRoot\out\price_diff.csv"
Write-Log "Готовый каталог: $syncRoot\out\catalog\"
Write-Log "Заливка на сайт — отдельно и вручную, после проверки диффа."
