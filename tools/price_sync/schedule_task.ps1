# Регистрирует задачу Windows Task Scheduler: сверка цен СплитХаб раз в 3 дня в 20:00.
# Три дня — чтобы остатки Бриза, Daichi, Русклимата и MDV не устаревали.
# Запусти ОДИН раз от своего пользователя:
#     .\schedule_task.ps1
#     .\schedule_task.ps1 -Time 19:00 -EveryDays 1
# Удалить:  Unregister-ScheduledTask -TaskName "SplitHub_PriceSync" -Confirm:$false

param(
    [string]$Time = "20:00",
    [int]$EveryDays = 3,
    [string]$TaskName = "SplitHub_PriceSync"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root "run_sync.ps1"

# PowerShell 7 через стабильный алиас из WindowsApps: путь внутри пакета Store
# меняется с каждой версией, а алиас — нет. Windows PowerShell 5.1 не годится:
# он теряет кавычки в аргументах ssh и ломает выгрузку SplitHome.
$pwsh = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\pwsh.exe"

# conhost --headless запускает консоль без окна. Без него Windows 11 открывает
# Терминал на весь экран поверх работы каждые три дня.
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\conhost.exe" `
    -Argument "--headless `"$pwsh`" -NoProfile -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -DaysInterval $EveryDays -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 45)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Сверка цен каталога СплитХаб с прайсами поставщиков раз в 3 дня (без деплоя)" -Force

Write-Output "Задача '$TaskName' зарегистрирована: каждые $EveryDays дня в $Time."
Write-Output "Проверить:        Get-ScheduledTask -TaskName $TaskName"
Write-Output "Запустить сейчас: Start-ScheduledTask -TaskName $TaskName"
