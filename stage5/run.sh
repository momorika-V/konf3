#!/bin/sh
# Команды: вход.yaml выход, test - тесты, demo - пример, exit - выход.
cd "$(dirname "$0")" || exit 1
PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python
"$PYTHON" -c "import yaml" >/dev/null 2>&1 || "$PYTHON" -m pip install PyYAML
echo "Команды: вход.yaml выход.bin / вход.bin дамп.csv [начало конец], test, demo, ex1..ex3, exit."
while true; do
    printf "> "
    read -r line || break
    [ "$line" = "exit" ] && break
    if [ "$line" = "test" ]; then
        "$PYTHON" -m unittest discover -s tests -v
        continue
    fi
    if [ "$line" = "demo" ]; then
        mkdir -p temp
        "$PYTHON" src/main.py examples/task_vectors.yaml temp/task.bin
        "$PYTHON" src/main.py temp/task.bin temp/task.csv 155 180
        continue
    fi
    if [ "$line" = "ex1" ]; then
        mkdir -p temp
        "$PYTHON" src/main.py examples/copy.yaml temp/ex1.bin
        "$PYTHON" src/main.py temp/ex1.bin temp/ex1.csv 95 120
        continue
    fi
    if [ "$line" = "ex2" ]; then
        mkdir -p temp
        "$PYTHON" src/main.py examples/write_demo.yaml temp/ex2.bin
        "$PYTHON" src/main.py temp/ex2.bin temp/ex2.csv 0 90
        continue
    fi
    if [ "$line" = "ex3" ]; then
        mkdir -p temp
        "$PYTHON" src/main.py examples/rol_demo.yaml temp/ex3.bin
        "$PYTHON" src/main.py temp/ex3.bin temp/ex3.csv 195 215
        continue
    fi
    "$PYTHON" src/main.py $line
done
