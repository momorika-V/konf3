r"""Ассемблер и интерпретатор учебной виртуальной машины УВМ.

Вариант 22, этап 3: к ассемблеру (этапы 1--2) добавлен интерпретатор.
Память команд и данных объединена: программа загружается в память
с адреса 0, дальше в той же памяти живут данные. Цикл интерпретации:
чтение 10 байт из памяти, перевод в промежуточное представление,
выполнение. После работы память сохраняется в CSV-дамп.

Режим выбирается по расширению входного файла:
    python src/main.py <вход.yaml> <выход.bin> [--test]   ассемблер
    python src/main.py <вход.bin> <дамп.csv> [начало конец] [--test]

начало/конец -- диапазон адресов для дампа (по умолчанию 0 и 256).
--test : печатать трассировку выполняемых команд.
"""

import argparse
import csv
import os
import sys

import yaml

EXIT_OK = 0
EXIT_ERROR = 1

CMD_SIZE = 10      
OP_BITS = 6        
ADDR_BITS = 24     
CONST_BITS = 21    
OFFSET_BITS = 9    
DUMP_END_DEFAULT = 256   

OPS = {
    "load": {"code": 17,
             "fields": (("b", 6, ADDR_BITS, "addr"),
                        ("c", 30, CONST_BITS, "value"))},
    "read": {"code": 43,
             "fields": (("b", 6, ADDR_BITS, "dst"),
                        ("c", 30, ADDR_BITS, "src"))},
    "write": {"code": 21,
              "fields": (("b", 6, ADDR_BITS, "src"),
                         ("c", 30, OFFSET_BITS, "offset"),
                         ("d", 39, ADDR_BITS, "base"))},
    "rol": {"code": 57,
            "fields": (("b", 6, ADDR_BITS, "count"),
                       ("c", 30, ADDR_BITS, "dst"),
                       ("d", 54, ADDR_BITS, "value"))},
}


class ConfigError(Exception):
    """Понятная пользователю ошибка программы или входных данных."""


def fail(message):
    """Прерывает работу, выдавая понятное сообщение об ошибке."""
    raise ConfigError(message)


def read_text(path):
    """Читает текстовый файл, объясняя возможные проблемы."""
    if not os.path.isfile(path):
        fail("Входной файл не найден: " + path)
    try:
        with open(path, "r", encoding="utf-8") as source:
            return source.read()
    except (OSError, UnicodeDecodeError):
        fail("Не удалось прочитать файл как текст UTF-8: " + path)


def write_text(path, text):
    """Записывает текстовый файл, объясняя возможные проблемы."""
    try:
        with open(path, "w", encoding="utf-8") as target:
            target.write(text)
    except OSError:
        fail("Нельзя записать файл: " + path)


def parse_yaml(text):
    """Разбирает YAML-текст, добавляя к ошибке строку и столбец."""
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        if mark is None:
            fail("Ошибка синтаксиса YAML: " + str(exc).splitlines()[0])
        fail("Ошибка синтаксиса YAML: строка {}, столбец {}.".format(
            mark.line + 1, mark.column + 1))


def build_ir(doc):
    """Строит промежуточное представление из YAML-документа."""
    if not isinstance(doc, list):
        fail("Программа должна быть списком команд (YAML-список).")
    return [build_instruction(item, number)
            for number, item in enumerate(doc, start=1)]


def build_instruction(item, number):
    """Строит одну инструкцию промежуточного представления."""
    head = "Команда {}: ".format(number)
    if not isinstance(item, dict) or len(item) != 1:
        fail(head + "ожидается запись вида 'имя_команды: поля'.")
    op = next(iter(item))
    if op not in OPS:
        fail(head + "неизвестная команда '{}'. Доступны: {}.".format(
            op, ", ".join(sorted(OPS))))
    fields = item[op]
    if not isinstance(fields, dict):
        fail(head + "поля команды задаются словарем.")
    instruction = {"op": op}
    instruction.update(check_fields(head, op, fields))
    return instruction


def check_fields(head, op, fields):
    """Проверяет поля команды и собирает их значения по буквам."""
    values = {}
    names = []
    for letter, _bit, width, name in OPS[op]["fields"]:
        if name not in fields:
            fail(head + "нет поля '{}'.".format(name))
        names.append(name)
        values[letter] = check_number(head, name, fields[name], width)
    extra = set(fields) - set(names)
    if extra:
        fail(head + "лишние поля: {}.".format(", ".join(sorted(extra))))
    return values


def check_number(head, name, value, width):
    """Проверяет, что поле -- целое число в допустимом диапазоне."""
    if isinstance(value, bool) or not isinstance(value, int):
        value = try_convert(head, name, value)
    limit = (1 << width) - 1
    if value < 0 or value > limit:
        fail(head + "поле '{}' вне диапазона 0..{}.".format(name, limit))
    return value


def try_convert(head, name, value):
    """Пробует понять значение поля как целое число."""
    if isinstance(value, str):
        try:
            return int(value.strip(), 0)
        except ValueError:
            pass
    fail(head + "поле '{}' не целое число: {!r}.".format(name, value))


def ir_line(instruction):
    """Форматирует инструкцию как в тестах спецификации УВМ."""
    spec = OPS[instruction["op"]]
    parts = ["A={}".format(spec["code"])]
    for letter, _bit, _width, _name in sorted(spec["fields"]):
        parts.append("{}={}".format(letter.upper(), instruction[letter]))
    return instruction["op"] + ": " + " ".join(parts)


def ir_text(instructions):
    """Собирает текст промежуточного представления программы."""
    return "\n".join(ir_line(ins) for ins in instructions)


def encode_instruction(instruction):
    """Кодирует инструкцию в 80-битное слово (биты -- по спецификации)."""
    spec = OPS[instruction["op"]]
    word = spec["code"]
    for letter, bit, _width, _name in spec["fields"]:
        word |= instruction[letter] << bit
    return word


def instruction_bytes(instruction):
    """Возвращает 10 байт команды от младшего к старшему."""
    return encode_instruction(instruction).to_bytes(CMD_SIZE, "little")


def bytes_line(data):
    """Форматирует байты как в тестах спецификации: 0xD1, 0x10, ..."""
    return ", ".join("0x{:02X}".format(byte) for byte in data)


def machine_code(instructions):
    """Собирает машинный код всей программы."""
    return b"".join(instruction_bytes(ins) for ins in instructions)


def write_binary(path, data):
    """Записывает двоичный файл, объясняя возможные проблемы."""
    try:
        with open(path, "wb") as target:
            target.write(data)
    except OSError:
        fail("Нельзя записать файл: " + path)


def read_binary(path):
    """Читает двоичный файл программы."""
    if not os.path.isfile(path):
        fail("Файл программы не найден: " + path)
    try:
        with open(path, "rb") as source:
            return source.read()
    except OSError:
        fail("Не удалось прочитать файл: " + path)


ADDR_MASK = (1 << ADDR_BITS) - 1   # адреса складываются по модулю 2^24


def read_memory(memory, address):
    """Читает значение памяти: незаписанные адреса равны нулю."""
    return memory.get(address & ADDR_MASK, 0)


def decode_fields(op, spec, word):
    """Разбирает поля машинного слова по описанию команды."""
    instruction = {"op": op}
    for letter, bit, width, name in spec["fields"]:
        value = (word >> bit) & ((1 << width) - 1)
        instruction[letter] = value
        instruction[name] = value
    return instruction


def decode_word(word, address):
    """Переводит машинное слово в промежуточное представление."""
    code = word & (1 << OP_BITS) - 1
    for op, spec in OPS.items():
        if spec["code"] == code:
            return decode_fields(op, spec, word)
    fail("По адресу {}: неизвестный код команды A={}.".format(
        address, code))


def execute(instruction, memory):
    """Выполняет одну команду над объединенной памятью."""
    op = instruction["op"]
    if op == "load":
        memory[instruction["addr"]] = instruction["value"]
    elif op == "read":
        memory[instruction["dst"]] = read_memory(
            memory, instruction["src"])
    elif op == "write":
        base = read_memory(memory, instruction["base"])
        value = read_memory(memory, instruction["src"])
        memory[(base + instruction["offset"]) & ADDR_MASK] = value
    else:
        fail("Команда '{}' будет выполняться с этапа 4.".format(op))


def run_program(data, show_trace):
    """Выполняет программу из двоичных данных, возвращает память."""
    if len(data) % CMD_SIZE != 0:
        fail("Размер файла ({} байт) не кратен размеру команды {}."
             .format(len(data), CMD_SIZE))
    memory = {index: byte for index, byte in enumerate(data)}
    pc = 0
    while pc < len(data):
        word = int.from_bytes(data[pc:pc + CMD_SIZE], "little")
        instruction = decode_word(word, pc)
        execute(instruction, memory)
        if show_trace:
            print("{:>4}: {}".format(pc, ir_line(instruction)))
        pc += CMD_SIZE
    return memory


def check_range(start, end):
    """Проверяет диапазон адресов дампа."""
    if start < 0 or end < 0:
        fail("Адреса дампа не могут быть отрицательными.")
    if start > end:
        fail("Начало диапазона больше конца ({} > {}).".format(
            start, end))


def dump_csv(memory, path, start, end):
    """Сохраняет дамп памяти в CSV: адрес,значение."""
    try:
        with open(path, "w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(["address", "value"])
            for address in range(start, end):
                writer.writerow([address, memory.get(address, 0)])
    except OSError:
        fail("Нельзя записать файл: " + path)


def make_parser():
    """Описывает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Ассемблер и интерпретатор УВМ (этап 3). Режим"
                    " выбирается по расширению входного файла:",
        epilog=".yaml -- ассемблер, .bin -- интерпретатор")
    parser.add_argument("input", help="вход: программа .yaml или .bin")
    parser.add_argument("output", help="выход: .bin или дамп .csv")
    parser.add_argument("start", nargs="?", type=addr_number,
                        default=0, help="начало диапазона дампа")
    parser.add_argument("end", nargs="?", type=addr_number,
                        default=DUMP_END_DEFAULT,
                        help="конец диапазона дампа")
    parser.add_argument("--test", action="store_true",
                        help="печатать результат работы на экран")
    return parser


def addr_number(text):
    """Преобразует адрес дампа, объясняя ошибку по-русски."""
    try:
        return int(text, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "адрес должен быть целым числом, а не {!r}".format(text))


def assemble_file(source_path, target_path, show):
    """Транслирует программу и записывает двоичный файл."""
    text = read_text(source_path)
    instructions = build_ir(parse_yaml(text))
    code = machine_code(instructions)
    write_binary(target_path, code)
    print("Команд: {}. Размер файла: {} байт. Записан: {}".format(
        len(instructions), len(code), target_path))
    if show:
        for ins in instructions:
            print("{}: {}".format(
                ins["op"], bytes_line(instruction_bytes(ins))))


def interpret_file(args):
    """Выполняет программу и сохраняет дамп памяти."""
    check_range(args.start, args.end)
    data = read_binary(args.input)
    memory = run_program(data, args.test)
    dump_csv(memory, args.output, args.start, args.end)
    print("Выполнено. Дамп памяти (адреса {}..{}) записан: {}".format(
        args.start, args.end - 1, args.output))


def main(argv):
    """Точка входа: режим выбирается по расширению входного файла."""
    args = make_parser().parse_args(argv)
    try:
        if args.input.lower().endswith((".yaml", ".yml")):
            assemble_file(args.input, args.output, args.test)
        elif args.input.lower().endswith(".bin"):
            interpret_file(args)
        else:
            fail("Не удалось определить режим по файлу '{}':"
                 " ассемблер -- .yaml, интерпретатор -- .bin.".format(
                     args.input))
    except ConfigError as exc:
        print("Ошибка: " + str(exc))
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
