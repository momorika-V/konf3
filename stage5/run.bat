@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
python -c "import yaml" >nul 2>&1 || python -m pip install PyYAML
echo Команды: вход.yaml выход.bin / вход.bin дамп.csv [начало конец], test, demo, ex1..ex3, exit.
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
    python src\main.py examples\task_vectors.yaml temp\task.bin
    python src\main.py temp\task.bin temp\task.csv 155 180
    goto loop
)
if /i "%ARGS%"=="ex1" (
    if not exist temp mkdir temp
    python src\main.py examples\copy.yaml temp\ex1.bin
    python src\main.py temp\ex1.bin temp\ex1.csv 95 120
    goto loop
)
if /i "%ARGS%"=="ex2" (
    if not exist temp mkdir temp
    python src\main.py examples\write_demo.yaml temp\ex2.bin
    python src\main.py temp\ex2.bin temp\ex2.csv 0 90
    goto loop
)
if /i "%ARGS%"=="ex3" (
    if not exist temp mkdir temp
    python src\main.py examples\rol_demo.yaml temp\ex3.bin
    python src\main.py temp\ex3.bin temp\ex3.csv 195 215
    goto loop
)
python src\main.py %ARGS%
goto loop
