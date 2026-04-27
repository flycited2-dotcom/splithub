@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ========================================
echo  SplitHub — Предпросмотр изменений
echo ========================================
echo.

python deploy.py --mode preview

echo.
pause
