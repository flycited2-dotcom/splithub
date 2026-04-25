@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ========================================
echo  SplitHub — Публикация каталога на сайт
echo ========================================
echo.

call :check_python
call :check_paramiko
call :check_config

python deploy.py %*

echo.
if errorlevel 1 (
    echo [!] Деплой завершён с ошибкой. Проверьте logs/deploy_*.log
) else (
    echo [OK] Каталог опубликован успешно!
)
echo.
pause
exit /b

:check_python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден.
    echo         Скачайте с python.org. При установке отметьте "Add Python to PATH"
    pause
    exit /b 1
)
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
    echo.
    echo Скопируйте config\deploy.example.json в config\deploy.json
    echo и заполните хост, логин и пароль SFTP.
    echo.
    pause
    exit /b 1
)
exit /b 0
