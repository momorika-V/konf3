#!/bin/sh
# Команды: вход.yaml выход, test - тесты, demo - пример, exit - выход.
cd "$(dirname "$0")" || exit 1
PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python
"$PYTHON" -c "import yaml" >/dev/null 2>&1 || "$PYTHON" -m pip install PyYAML
echo "Команды: вход.yaml выход.bin / вход.bin дамп.csv [начало конец], test, demo, exit."
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
        "$PYTHON" src/main.py examples/copy.yaml temp/copy.bin
        "$PYTHON" src/main.py temp/copy.bin temp/dump.csv
        continue
    fi
    "$PYTHON" src/main.py $line
done
