@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ========================================
echo  SplitHub Converter — ПРОВЕРКА (dry-run)
echo  Файлы НЕ будут записаны
echo ========================================
echo.

python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден.
    pause
    exit /b 1
)

python -c "import openpyxl" > nul 2>&1
if errorlevel 1 (
    pip install openpyxl --quiet
)

python convert.py --dry-run

echo.
pause
