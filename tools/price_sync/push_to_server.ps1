# Выкладывает сверку цен на сервер (sprintbox-itp, /opt/splithub-price-sync), где она
# идёт каждую ночь по cron. Запускать после любой правки кода или реестров
# (card_content, series_map, rashod_map, прайс Техносистемса): иначе ночью сервер
# посчитает по старым.
#
#     .\push_to_server.ps1                 # код и данные
#     .\push_to_server.ps1 -WithSecrets    # + доступ к хостингу — сервер начинает заливать
#
# -WithSecrets везёт пароль хостинга (converter/config/deploy.json; на сервере его видит
# только root) и переводит задачу компьютера в режим «только остатки JAC»: цены с этого
# момента считает и заливает сервер, двойной заливки нет.

param([switch]$WithSecrets)

$ErrorActionPreference = "Stop"
$syncRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$siteRoot = Split-Path -Parent (Split-Path -Parent $syncRoot)
$remote   = "/opt/splithub-price-sync"

$stage = Join-Path $env:TEMP ("splithub-push-" + (Get-Date -Format "yyyyMMdd_HHmmss"))
$app = Join-Path $stage "app"

function Add-Files([string]$from, [string]$to, [string[]]$patterns) {
    New-Item -ItemType Directory -Force -Path $to | Out-Null
    foreach ($pattern in $patterns) {
        Get-ChildItem -Path $from -Filter $pattern -File | Copy-Item -Destination $to
    }
}

# Ровно то, что читает сверка: код, реестры, прайс Техносистемса, запрос к базе
# SplitHome, products.js репозитория (из него возвращаются THAICON и Mitsubishi Heavy).
Add-Files (Join-Path $siteRoot "tools") (Join-Path $app "tools") @("__init__.py")
Add-Files $syncRoot (Join-Path $app "tools\price_sync") @("*.py", "*.json", "*.csv", "*.sql")
Add-Files (Join-Path $syncRoot "server") (Join-Path $app "tools\price_sync\server") @("*.sh", "*.py")
Add-Files $siteRoot $app @("products.js")
if ($WithSecrets) {
    Add-Files (Join-Path $siteRoot "converter\config") (Join-Path $app "converter\config") @("deploy.json")
}

$bundle = Join-Path $env:TEMP "splithub-price-sync.tgz"
tar -czf $bundle -C $stage app
if ($LASTEXITCODE -ne 0) { throw "tar не собрал архив" }
Remove-Item -Recurse -Force $stage

# Имя без диска: «C:\...» scp принял бы за адрес хоста «C».
Push-Location $env:TEMP
try {
    scp -q "splithub-price-sync.tgz" "sprintbox-itp:/tmp/splithub-price-sync.tgz"
    if ($LASTEXITCODE -ne 0) { throw "не удалось отправить архив на сервер" }
} finally {
    Pop-Location
}
Remove-Item -Force $bundle

# Распаковать поверх (out/, logs/ и jac/ сервера архив не трогает), .sh — в LF и
# исполняемый, пароль хостинга — только root.
$unpack = "set -e; mkdir -p $remote; tar -xzf /tmp/splithub-price-sync.tgz -C $remote; " +
    "rm -f /tmp/splithub-price-sync.tgz; " +
    "sed -i 's/\r$//' $remote/app/tools/price_sync/server/run_sync.sh; " +
    "chmod 755 $remote/app/tools/price_sync/server/run_sync.sh; " +
    "chmod 600 $remote/app/converter/config/deploy.json 2>/dev/null || true; " +
    "echo ok"
$answer = ssh sprintbox-itp $unpack
if ($LASTEXITCODE -ne 0 -or "$answer" -notmatch "ok") { throw "распаковка на сервере не удалась: $answer" }
Write-Output "Выложено на сервер: $remote"

if ($WithSecrets) {
    # Сервер теперь сам заливает цены в 04:00 — компьютеру остаётся вечерний сбор JAC.
    & (Join-Path $syncRoot "schedule_task.ps1") -JacOnly
}
