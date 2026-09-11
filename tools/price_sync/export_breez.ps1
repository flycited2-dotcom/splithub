# Забирает оптовые цены Бриза (`base`) из его API в out\breez_base.json.
#
# В базе SplitHome у Бриза лежит РОЗНИЦА — накручивать наценку на неё нельзя.
# Настоящий опт Бриз отдаёт только в своём /leftoversnew/. Запрос уходит С СЕРВЕРА,
# где лежит ключ: BREEZ_AUTH_HEADER никуда не копируется.
#
#     .\export_breez.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $root "out"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$target = Join-Path $outDir "breez_base.json"

# .env не «сорсим»: в значении ключа есть пробел («Basic xxx»), и shell пытается
# выполнить вторую половину как команду — заодно печатая её в лог. Читаем sed-ом.
$remote = 'H=$(sed -n "s/^BREEZ_AUTH_HEADER=//p" /opt/oasis/.env); U=$(sed -n "s/^BREEZ_BASE_URL=//p" /opt/oasis/.env); curl -sS --max-time 120 -H "Authorization: $H" -H "Accept: application/json" "${U%/}/leftoversnew/"'

Write-Output "Запрашиваю опт-цены Бриза через sprintbox-itp..."
ssh sprintbox-itp $remote 2>$null | Set-Content -Path $target -Encoding UTF8

if (-not (Test-Path $target) -or (Get-Item $target).Length -lt 100) {
    throw "Ответ Бриза пустой. Проверь BREEZ_AUTH_HEADER в /opt/oasis/.env на сервере."
}

Write-Output ("Готово: " + [math]::Round((Get-Item $target).Length / 1KB) + " КБ -> $target")
