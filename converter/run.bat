@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ====================================================
echo   SplitHub Catalog Converter
echo ====================================================
echo.

:: Если файл перетащили на bat — скопировать его в input/
if not "%~1"=="" (
    echo Файл получен: %~nx1
    if exist "%~1" (
        copy /Y "%~1" "%~dp0input\%~nx1" > nul
        echo Скопирован в converter\input\
        echo.
    )
)

:: Проверить Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден.
    echo          Скачайте с https://python.org и установите.
    echo          При установке отметьте "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: Установить openpyxl если нет
python -c "import openpyxl" > nul 2>&1
if errorlevel 1 (
    echo Устанавливаю openpyxl...
    pip install openpyxl --quiet
)

:: Запустить конвертер
python convert.py %2 %3 %4

echo.
if errorlevel 1 (
    echo [!] Завершено с ошибками. Проверьте папку converter\logs\
) else (
    echo Файлы готовы в папке converter\out\
    echo.
    echo Для деплоя: загрузите deploy_*.zip на сервер (распаковать в public_html)
    echo Или только products.js если меняли только каталог.
)
echo.
pause
