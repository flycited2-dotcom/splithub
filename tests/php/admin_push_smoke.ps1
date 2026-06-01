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

$port = Get-Random -Minimum 25001 -Maximum 28000
$tmpDb = Join-Path $env:TEMP "splithub_admin_push_$PID.sqlite"
$configFile = Join-Path $env:TEMP "splithub_admin_push_config_$PID.php"
$requestFile = Join-Path $env:TEMP "splithub_admin_push_request_$PID.json"
$responseFile = Join-Path $env:TEMP "splithub_admin_push_response_$PID.json"
$cookieFile = Join-Path $env:TEMP "splithub_admin_push_cookie_$PID.txt"
$env:SPLITHUB_DB_PATH = $tmpDb
$env:SPLITHUB_PRODUCTS_PATH = Join-Path $root 'products.json'
$env:SPLITHUB_CONFIG_PATH = $configFile
[System.IO.File]::WriteAllText(
    $configFile,
    "<?php`ndefine('BOT_TOKEN', '');`ndefine('CHAT_ID', '');`ndefine('CRON_SECRET', 'smoke');`n",
    [System.Text.UTF8Encoding]::new($false)
)

function Assert-True([bool]$value, [string]$message) {
    if (-not $value) {
        throw "FAIL: $message"
    }
    Write-Host "PASS: $message"
}

function Invoke-Api([string]$path, [string]$method = 'GET', [hashtable]$body = @{}) {
    $url = "http://127.0.0.1:$port/api/$path"
    $args = @('-sS', '-o', $responseFile, '-w', '%{http_code}', '-b', $cookieFile, '-c', $cookieFile, '-H', 'Content-Type: application/json')
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
    return @{ Status = [int]$status; Data = $content | ConvertFrom-Json }
}

foreach ($path in @($tmpDb, "$tmpDb-wal", "$tmpDb-shm", $requestFile, $responseFile, $cookieFile)) {
    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
}

$customerId = & $php tests\php\seed_admin_push_smoke.php
$server = Start-Process -FilePath $php -ArgumentList '-S', "127.0.0.1:$port", '-t', $root -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 1
    $login = Invoke-Api 'auth.php?action=login' 'POST' @{ phone = 'admin'; password = 'pass123' }
    Assert-True ($login.Status -eq 200 -and $login.Data.user.role -eq 'admin') 'admin signed in'

    $promotion = Invoke-Api 'admin.php?action=push_promotion' 'POST' @{ title = 'Promo'; body = 'Text'; category = 'inv' }
    Assert-True ($promotion.Status -eq 200 -and $promotion.Data.users -eq 0) 'promotion action accepts empty audience'

    $manager = Invoke-Api 'admin.php?action=push_manager_message' 'POST' @{ user_id = [int]$customerId; body = 'Call us' }
    Assert-True ($manager.Status -eq 200 -and $manager.Data.ok) 'manager message campaign created'

    $log = Invoke-Api 'admin.php?action=push_log'
    Assert-True ($log.Status -eq 200 -and $log.Data.campaigns[0].type -eq 'manager_message') 'push campaign log returned'
} finally {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    foreach ($path in @($tmpDb, "$tmpDb-wal", "$tmpDb-shm", $configFile, $requestFile, $responseFile, $cookieFile)) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
}
