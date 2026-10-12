# Выгружает каталог SplitHome (Русклимат / Daichi / Бриз) с VPS в out\oasis_stock.csv.
#
# Запрос read-only и выполняется НА СЕРВЕРЕ, внутри контейнера с базой: пароли
# никуда не уезжают, порт Postgres наружу не открыт и открывать не нужно.
#
#     .\export_oasis.ps1
#
# Требуется рабочий ssh-алиас sprintbox-itp (уже настроен в ~\.ssh\config).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sql = Join-Path $root "oasis_export.sql"
$outDir = Join-Path $root "out"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$target = Join-Path $outDir "oasis_stock.csv"

$remote = 'docker exec -i oasis-db-1 sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -At -F''|'' -f -"'

Write-Output "Выгружаю каталог SplitHome с sprintbox-itp..."
Get-Content -Path $sql -Raw -Encoding UTF8 | ssh sprintbox-itp $remote | Set-Content -Path $target -Encoding UTF8

if (-not (Test-Path $target) -or (Get-Item $target).Length -eq 0) {
    throw "Выгрузка пустая. Проверь: ssh sprintbox-itp 'docker ps --filter name=oasis-db-1'"
}

$lines = (Get-Content $target | Measure-Object -Line).Lines
Write-Output "Готово: $lines строк -> $target"
