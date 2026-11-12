@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Первый запуск: устанавливаю зависимости, это займёт пару минут...
    python -m venv .venv || goto :error
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :error
)

echo Запускаю приложение, страница откроется в браузере...
".venv\Scripts\python.exe" app.py
goto :eof

:error
echo.
echo Не получилось установить зависимости. Проверьте, что установлен Python 3.11+.
pause
