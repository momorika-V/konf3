@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
python -c "import yaml" >nul 2>&1 || python -m pip install PyYAML
echo Команды: вход.yaml выход.bin / вход.bin дамп.csv [начало конец], test, demo, exit.
:loop
set "ARGS="
set /p "ARGS=> "
if not defined ARGS goto loop
if /i "%ARGS%"=="exit" exit /b
if /i "%ARGS%"=="test" (
    python -m unittest discover -s tests -v
    goto loop
)
if /i "%ARGS%"=="demo" (
    if not exist temp mkdir temp
    python src\main.py examples\copy.yaml temp\copy.bin
    python src\main.py temp\copy.bin temp\dump.csv
    goto loop
)
python src\main.py %ARGS%
goto loop
