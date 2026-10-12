# Регистрирует задачу Windows Task Scheduler: сверка цен и наличия СплитХаб каждую ночь
# в 04:00 — к утру на сайте цены и остатки поставщиков — и, как раньше, в 20:00.
# Вечерний прогон — страховка: компьютер на ночь уходит в сон и таймером не
# просыпается (25.09.2026 по журналу: часовая задача с пробуждением ночью не шла ни
# разу), тогда ночной прогон выполнится утром, при включении.
# Запусти ОДИН раз от своего пользователя:
#     .\schedule_task.ps1
#     .\schedule_task.ps1 -Time 03:00,19:00 -EveryDays 1
#     .\schedule_task.ps1 -JacOnly   # сверку ведёт сервер: здесь только остатки JAC в 20:00
# Удалить:  Unregister-ScheduledTask -TaskName "SplitHub_PriceSync" -Confirm:$false

param(
    [string[]]$Time = @("04:00", "20:00"),
    [int]$EveryDays = 1,
    [string]$TaskName = "SplitHub_PriceSync",
    [switch]$JacOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root "run_sync.ps1"
$extra = ""
$description = "Ночная сверка цен и наличия СплитХаб с поставщиками, заливка на сайт через предохранитель, итог в Telegram"
if ($JacOnly) {
    # Сервер считает и заливает цены в 04:00 сам; компьютеру остаётся вечерний сбор
    # остатков JAC — к ночи он уже лежит на сервере.
    if (-not $PSBoundParameters.ContainsKey("Time")) { $Time = @("20:00") }
    $extra = " -JacOnly"
    $description = "Сбор остатков JAC для ночной сверки цен СплитХаб на сервере"
}

# PowerShell 7 через стабильный алиас из WindowsApps: путь внутри пакета Store
# меняется с каждой версией, а алиас — нет. Windows PowerShell 5.1 не годится:
# он теряет кавычки в аргументах ssh и ломает выгрузку SplitHome.
$pwsh = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\pwsh.exe"

# conhost --headless запускает консоль без окна. Без него Windows 11 открывает
# Терминал на весь экран поверх работы при каждом прогоне.
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\conhost.exe" `
    -Argument "--headless `"$pwsh`" -NoProfile -ExecutionPolicy Bypass -File `"$runner`"$extra" `
    -WorkingDirectory $root

$triggers = @($Time | ForEach-Object { New-ScheduledTaskTrigger -Daily -DaysInterval $EveryDays -At $_ })
# WakeToRun просит разбудить спящий компьютер к ночному прогону (заработает, если
# разрешить пробуждение в настройках питания/BIOS); бодрым на время сверки его держит
# сам run_sync.ps1. Не проснулся или был выключен — прогон запустится, как только
# включат (StartWhenAvailable); прогон упал
# целиком — планировщик перезапустит его ещё до трёх раз с интервалом 30 минут.
# Внутри прогона шаги сами повторяются при сбое сети, а скрапер JAC — при неполном
# сборе (до трёх попыток через 15 минут), поэтому лимит — два часа, а не один.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -DontStopOnIdleEnd `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 30) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
    -Settings $settings -Description $description -Force

Write-Output ("Задача '$TaskName' зарегистрирована: каждые $EveryDays дня в " + ($Time -join " и ") + ".")
Write-Output "Проверить:        Get-ScheduledTask -TaskName $TaskName"
Write-Output "Запустить сейчас: Start-ScheduledTask -TaskName $TaskName"
