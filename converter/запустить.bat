@echo off
chcp 65001 > /dev/null
cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════╗
echo ║     SplitHub — Обновление каталога   ║
echo ╚══════════════════════════════════════╝
echo.
echo  Папка с мастер-файлом:  converter\input\
echo  Готовый файл для сайта: converter\out\products.js
echo.
echo ──────────────────────────────────────
echo  Запускаю конвертер...
echo ──────────────────────────────────────

python -c "import openpyxl" > /dev/null 2>&1
if errorlevel 1 ( pip install openpyxl -q )

python convert.py
if errorlevel 1 (
    echo.
    echo [!] Конвертер завершился с ошибками.
    echo     Исправьте Excel и запустите снова.
    echo.
    pause
    exit /b 1
)

echo.
echo ──────────────────────────────────────
set /p ANSWER= Залить на сервер? (да/нет): 
echo ──────────────────────────────────────

if /i "%ANSWER%"=="да" goto DEPLOY
if /i "%ANSWER%"=="Да" goto DEPLOY
if /i "%ANSWER%"=="ДА" goto DEPLOY
if /i "%ANSWER%"=="д" goto DEPLOY
if /i "%ANSWER%"=="y" goto DEPLOY
if /i "%ANSWER%"=="yes" goto DEPLOY
goto SKIP

:DEPLOY
echo.
echo  Загружаю на сервер...
python deploy.py
if errorlevel 1 (
    echo [!] Ошибка деплоя. Проверьте интернет и попробуйте снова.
) else (
    echo.
    echo  Готово! Каталог обновлён на splithub.ru
)
goto END

:SKIP
echo.
echo  Деплой пропущен. Файл готов в converter\out\products.js
echo  Запустите запустить.bat снова когда будете готовы.

:END
echo.
pause
