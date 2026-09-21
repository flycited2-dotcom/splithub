# Регистрирует задачу Windows Task Scheduler: сверка цен и наличия СплитХаб раз в сутки
# в 20:00 — чтобы остатки поставщиков на сайте не устаревали.
# Запусти ОДИН раз от своего пользователя:
#     .\schedule_task.ps1
#     .\schedule_task.ps1 -Time 19:00 -EveryDays 3
# Удалить:  Unregister-ScheduledTask -TaskName "SplitHub_PriceSync" -Confirm:$false

param(
    [string]$Time = "20:00",
    [int]$EveryDays = 1,
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
# Терминал на весь экран поверх работы при каждом прогоне.
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\conhost.exe" `
    -Argument "--headless `"$pwsh`" -NoProfile -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -DaysInterval $EveryDays -At $Time
# Автоподъём: компьютер был выключен в 20:00 — прогон запустится, как только включат
# (StartWhenAvailable); прогон упал целиком — планировщик перезапустит его ещё до
# трёх раз с интервалом 30 минут. Внутри прогона шаги сами повторяются при сбое сети.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 30) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 60)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Сверка цен и наличия СплитХаб с поставщиками раз в сутки, заливка на сайт через предохранитель, итог в Telegram" -Force

Write-Output "Задача '$TaskName' зарегистрирована: каждые $EveryDays дня в $Time."
Write-Output "Проверить:        Get-ScheduledTask -TaskName $TaskName"
Write-Output "Запустить сейчас: Start-ScheduledTask -TaskName $TaskName"
