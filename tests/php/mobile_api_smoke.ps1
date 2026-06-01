$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$php = if ($env:SPLITHUB_TEST_PHP) {
    $env:SPLITHUB_TEST_PHP
} else {
    Join-Path $env:TEMP 'codex-php-8.5.6\php.exe'
}
if (-not (Test-Path $php)) {
    throw "PHP CLI is missing: $php"
}

$port = Get-Random -Minimum 18000 -Maximum 22000
$tmpDb = Join-Path $env:TEMP "splithub_mobile_api_$PID.sqlite"
$requestFile = Join-Path $env:TEMP "splithub_mobile_api_request_$PID.json"
$responseFile = Join-Path $env:TEMP "splithub_mobile_api_response_$PID.json"
$env:SPLITHUB_DB_PATH = $tmpDb
$env:SPLITHUB_PRODUCTS_PATH = Join-Path $root 'products.json'
$env:SPLITHUB_CONFIG_PATH = Join-Path $root 'config.example.php'

function Assert-True([bool]$value, [string]$message) {
    if (-not $value) {
        throw "FAIL: $message"
    }
    Write-Host "PASS: $message"
}

function Invoke-Mobile(
    [string]$action,
    [string]$method = 'GET',
    [hashtable]$body = @{},
    [string]$token = '',
    [string]$query = ''
) {
    $url = "http://127.0.0.1:$port/api/mobile.php?action=$action$query"
    $args = @('-sS', '-o', $responseFile, '-w', '%{http_code}', '-H', 'Content-Type: application/json')
    if ($token) {
        $args += @('-H', "Authorization: Bearer $token")
    }
    if ($method -eq 'POST') {
        [System.IO.File]::WriteAllText(
            $requestFile,
            ($body | ConvertTo-Json -Compress -Depth 8),
            [System.Text.UTF8Encoding]::new($false)
        )
        $args += @('--data-binary', "@$requestFile")
    }
    $status = & curl.exe @args $url
    $content = Get-Content -LiteralPath $responseFile -Raw
    $data = try { $content | ConvertFrom-Json } catch { $null }
    return @{
        Status = [int]$status
        Data = $data
        Raw = $content
    }
}

foreach ($path in @($tmpDb, "$tmpDb-wal", "$tmpDb-shm", $requestFile, $responseFile)) {
    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
}

$server = Start-Process -FilePath $php -ArgumentList '-S', "127.0.0.1:$port", '-t', $root -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 1

    $catalog = Invoke-Mobile 'catalog'
    Assert-True ($catalog.Status -eq 200 -and $catalog.Data.ok) 'catalog endpoint works'

    $register = Invoke-Mobile 'register' 'POST' @{
        name = 'Mobile Smoke'
        phone = '79780000003'
        password = 'pass123'
        telegram = '@mobile'
    }
    Assert-True ($register.Status -eq 200 -and $register.Data.token) 'registration returns bearer token'
    $token = $register.Data.token

    $profile = Invoke-Mobile 'profile' 'GET' @{} $token
    Assert-True ($profile.Status -eq 200 -and $profile.Data.user.phone -eq '79780000003') 'profile uses bearer token'

    $changed = Invoke-Mobile 'create_order' 'POST' @{
        items = @(@{ id = '1001'; price = 1; qty = 2 })
    } $token
    Assert-True ($changed.Status -eq 409 -and $changed.Data.code -eq 'CATALOG_CHANGED') 'changed catalog price rejected'

    $created = Invoke-Mobile 'create_order' 'POST' @{
        items = @(@{ id = '1001'; price = 24900; qty = 2 })
        comment = 'mobile smoke'
    } $token
    Assert-True ($created.Status -eq 200 -and $created.Data.total -eq 49800) 'validated order created'
    $orderId = [int]$created.Data.order_id

    $orders = Invoke-Mobile 'orders' 'GET' @{} $token
    Assert-True ($orders.Status -eq 200 -and $orders.Data.orders.Count -eq 1) 'order history returned'

    $order = Invoke-Mobile 'order' 'GET' @{} $token "&id=$orderId"
    Assert-True ($order.Status -eq 200 -and $order.Data.order.items.Count -eq 1) 'order details returned'

    $repeat = Invoke-Mobile 'repeat_order' 'POST' @{ order_id = $orderId } $token
    Assert-True ($repeat.Status -eq 200 -and $repeat.Data.items[0].id -eq '1001') 'repeat order returns catalog ids'

    $cancel = Invoke-Mobile 'cancel_order' 'POST' @{ order_id = $orderId; reason = 'smoke' } $token
    Assert-True ($cancel.Status -eq 200 -and $cancel.Data.ok) 'new order can be cancelled'
} finally {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    foreach ($path in @($tmpDb, "$tmpDb-wal", "$tmpDb-shm", $requestFile, $responseFile)) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
}
