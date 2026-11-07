@echo off
chcp 65001 > nul
rem Деплой SEO-правок splithub.ru: двойной клик. Сначала забирает ветку с правками,
rem потом tools\price_sync\deploy_seo.py (сверка, бэкапы, заливка, проверка, откат).
cd /d "%~dp0\..\.."

echo.
echo ========================================
echo  SplitHub — деплой SEO-правок
echo ========================================
echo.

if not exist "converter\config\deploy.json" (
    echo [ERROR] Нет converter\config\deploy.json ^(доступ к хостингу^).
    pause
    exit /b 1
)
python -c "import paramiko, requests" > nul 2>&1
if errorlevel 1 pip install paramiko requests --quiet

python -m tools.price_sync.deploy_seo %*
if errorlevel 1 (
    echo.
    echo [!] Деплой не завершён — смотрите сообщения выше.
    pause
    exit /b 1
)

echo.
echo Выкладываю seo_pages.py на сервер ночной сверки...
powershell -ExecutionPolicy Bypass -File tools\price_sync\push_to_server.ps1
echo.
echo [OK] Готово.
pause
