@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ========================================
echo  SplitHub — Полный цикл публикации
echo  (генерация + деплой)
echo ========================================
echo.

:: Step 1: Convert
echo [1/2] Конвертация Excel...
echo.
python convert.py
if errorlevel 1 (
    echo.
    echo [!] Конвертация завершилась с ошибкой.
    echo     Исправьте Excel и запустите снова.
    pause
    exit /b 1
)

echo.
echo [2/2] Публикация на сайт...
echo.

call :check_paramiko
call :check_config

python deploy.py
if errorlevel 1 (
    echo.
    echo [!] Деплой завершился с ошибкой. Проверьте logs/deploy_*.log
    pause
    exit /b 1
)

echo.
echo ========================================
echo  [OK] Готово! Каталог обновлён на сайте.
echo ========================================
echo.
pause
exit /b 0

:check_paramiko
python -c "import paramiko" > nul 2>&1
if errorlevel 1 (
    echo Устанавливаю paramiko...
    pip install paramiko --quiet
)
exit /b 0

:check_config
if not exist "config\deploy.json" (
    echo [ERROR] Файл config\deploy.json не найден.
    echo Скопируйте config\deploy.example.json в config\deploy.json и заполните.
    pause
    exit /b 1
)
exit /b 0
