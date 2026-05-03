@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ========================================
echo  SplitHub — Откат к предыдущей версии
echo ========================================
echo.
echo Эта операция восстановит предыдущий каталог на сайте.
echo.
set /p confirm=Продолжить? (y/n):
if /i not "%confirm%"=="y" (
    echo Отмена.
    pause
    exit /b 0
)

python deploy.py --mode rollback

echo.
if errorlevel 1 (
    echo [!] Откат завершён с ошибкой. Проверьте logs/deploy_*.log
) else (
    echo [OK] Откат выполнен успешно!
)
echo.
pause
