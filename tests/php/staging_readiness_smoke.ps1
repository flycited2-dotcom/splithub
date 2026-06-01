param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,
    [switch]$AllowHttp
)

$ErrorActionPreference = 'Stop'

$base = $BaseUrl.TrimEnd('/')
$uri = [System.Uri]$base
if (-not $AllowHttp -and $uri.Scheme -ne 'https') {
    throw 'BaseUrl must use HTTPS. Pass -AllowHttp only for a local test server.'
}

$responseFile = Join-Path $env:TEMP "splithub_staging_readiness_$PID.json"

function Assert-True([bool]$value, [string]$message) {
    if (-not $value) {
        throw "FAIL: $message"
    }
    Write-Host "PASS: $message"
}

function Invoke-Public([string]$path) {
    $status = & curl.exe '-sS' '-o' $responseFile '-w' '%{http_code}' "$base/$path"
    $content = Get-Content -LiteralPath $responseFile -Raw
    return @{
        Status = [int]$status
        Data = try { $content | ConvertFrom-Json } catch { $null }
    }
}

try {
    $catalog = Invoke-Public 'api/mobile.php?action=catalog'
    Assert-True ($catalog.Status -eq 200 -and $catalog.Data.ok -and $catalog.Data.products.Count -gt 0) 'mobile catalog endpoint is public'

    $snapshot = Invoke-Public 'products.json'
    Assert-True ($snapshot.Status -eq 200 -and $snapshot.Data.Count -gt 0) 'structured catalog snapshot is public'

    $profile = Invoke-Public 'api/mobile.php?action=profile'
    Assert-True ($profile.Status -eq 401 -and $profile.Data.code -eq 'AUTH_REQUIRED') 'profile requires bearer authentication'

    $receipts = Invoke-Public 'api/push_receipts.php'
    Assert-True ($receipts.Status -eq 403 -and $receipts.Data.error -eq 'forbidden') 'push receipts endpoint requires cron secret'
} finally {
    Remove-Item -LiteralPath $responseFile -Force -ErrorAction SilentlyContinue
}

exit 0
