"""Тесты этапа 4: арифметико-логическая команда rol."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import main


def build(text):
    """Разбирает YAML-текст до промежуточного представления."""
    return main.build_ir(main.parse_yaml(text))


class ParseTest(unittest.TestCase):
    """Проверки разбора корректных программ."""

    def test_load_spec(self):
        """Команда load из спецификации даёт A=17, B=67, C=619."""
        ins = build("- load:\n    addr: 67\n    value: 619\n")[0]
        self.assertEqual(ins["op"], "load")
        self.assertEqual(ins["b"], 67)
        self.assertEqual(ins["c"], 619)

    def test_read_spec(self):
        """Команда read из спецификации даёт B=737, C=274."""
        ins = build("- read:\n    dst: 737\n    src: 274\n")[0]
        self.assertEqual((ins["b"], ins["c"]), (737, 274))

    def test_write_spec(self):
        """Команда write из спецификации даёт B=662, C=337, D=305."""
        text = ("- write:\n"
                "    src: 662\n"
                "    offset: 337\n"
                "    base: 305\n")
        ins = build(text)[0]
        self.assertEqual((ins["b"], ins["c"], ins["d"]), (662, 337, 305))

    def test_rol_spec(self):
        """Команда rol из спецификации даёт B=766, C=189, D=940."""
        text = ("- rol:\n"
                "    dst: 189\n"
                "    value: 940\n"
                "    count: 766\n")
        ins = build(text)[0]
        self.assertEqual((ins["b"], ins["c"], ins["d"]), (766, 189, 940))

    def test_full_program(self):
        """Программа из двух команд даёт два элемента IR."""
        text = ("- load:\n    addr: 67\n    value: 619\n"
                "- read:\n    dst: 737\n    src: 274\n")
        self.assertEqual(len(build(text)), 2)

    def test_number_as_string(self):
        """Числа в кавычках тоже принимаются."""
        ins = build("- load:\n    addr: '67'\n    value: '619'\n")[0]
        self.assertEqual((ins["b"], ins["c"]), (67, 619))

    def test_hex_number_as_string(self):
        """Шестнадцатеричные числа поддерживаются."""
        ins = build("- load:\n    addr: 0x43\n    value: 0x6b\n")[0]
        self.assertEqual((ins["b"], ins["c"]), (0x43, 0x6B))

    def test_empty_program(self):
        """Пустая программа даёт пустой IR."""
        self.assertEqual(build("[]"), [])

    def test_ir_line_format(self):
        """Строка IR содержит код операции и значения полей."""
        ins = build("- load:\n    addr: 67\n    value: 619\n")[0]
        self.assertEqual(main.ir_line(ins), "load: A=17 B=67 C=619")


class ParseErrorTest(unittest.TestCase):
    """Проверки сообщений об ошибках в программе."""

    def test_unknown_op(self):
        """Неизвестная команда — ошибка конфигурации."""
        with self.assertRaises(main.ConfigError):
            build("- jump:\n    addr: 1\n")

    def test_missing_field(self):
        """Пропущенный аргумент команды — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: 67\n")

    def test_extra_field(self):
        """Лишнее поле в команде — ошибка."""
        text = "- load:\n    addr: 1\n    value: 2\n    junk: 3\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_negative_number(self):
        """Отрицательные числа запрещены."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: -1\n    value: 2\n")

    def test_too_big_constant(self):
        """Константа не помещается в 21-битную ячейку — ошибка."""
        text = "- load:\n    addr: 1\n    value: 2097152\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_too_big_offset(self):
        """Смещение write не помещается в 9 бит — ошибка."""
        text = "- write:\n    src: 1\n    offset: 1000\n    base: 3\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_not_a_number(self):
        """Список вместо числа — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: [1]\n    value: 2\n")

    def test_float_number(self):
        """Дробное число — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: 1.5\n    value: 2\n")

    def test_not_a_list(self):
        """Корень YAML не список — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("load:\n  addr: 1\n")

    def test_item_not_dict(self):
        """Элемент программы не словарь — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- just_a_string\n")

    def test_two_keys_in_item(self):
        """Две команды в одном элементе — ошибка."""
        text = "- load:\n    addr: 1\n    value: 2\n  read:\n    dst: 3\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_yaml_syntax_error(self):
        """Битый YAML — ошибка конфигурации."""
        with self.assertRaises(main.ConfigError):
            main.parse_yaml("- load:\n  addr: [1\n")


class EncodeTest(unittest.TestCase):
    """Проверки машинного кода по тестам спецификации УВМ."""

    def spec_program(self):
        """Возвращает IR программы из тестов спецификации."""
        return build("- load:\n    addr: 67\n    value: 619\n"
                     "- read:\n    dst: 737\n    src: 274\n"
                     "- write:\n    src: 662\n    offset: 337\n"
                     "    base: 305\n"
                     "- rol:\n    dst: 189\n    value: 940\n"
                     "    count: 766\n")

    def test_load_bytes(self):
        """Кодировка load совпадает с тестами спецификации."""
        code = main.instruction_bytes(build(
            "- load:\n    addr: 67\n    value: 619\n")[0])
        expected = bytes([0xD1, 0x10, 0x00, 0xC0, 0x9A, 0x00,
                          0x00, 0x00, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_read_bytes(self):
        """Кодировка read совпадает с тестами спецификации."""
        code = main.instruction_bytes(build(
            "- read:\n    dst: 737\n    src: 274\n")[0])
        expected = bytes([0x6B, 0xB8, 0x00, 0x80, 0x44, 0x00,
                          0x00, 0x00, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_write_bytes(self):
        """Кодировка write совпадает с тестами спецификации."""
        text = ("- write:\n    src: 662\n    offset: 337\n"
                "    base: 305\n")
        code = main.instruction_bytes(build(text)[0])
        expected = bytes([0x95, 0xA5, 0x00, 0x40, 0xD4, 0x98,
                          0x00, 0x00, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_rol_bytes(self):
        """Кодировка rol совпадает с тестами спецификации."""
        text = "- rol:\n    dst: 189\n    value: 940\n    count: 766\n"
        code = main.instruction_bytes(build(text)[0])
        expected = bytes([0xB9, 0xBF, 0x00, 0x40, 0x2F, 0x00,
                          0x00, 0xEB, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_full_program_bytes(self):
        """Программа из спецификации кодируется в 4 слова."""
        code = main.machine_code(self.spec_program())
        self.assertEqual(len(code), 4 * main.CMD_SIZE)
        expected = bytes([
            0xD1, 0x10, 0x00, 0xC0, 0x9A, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x6B, 0xB8, 0x00, 0x80, 0x44, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x95, 0xA5, 0x00, 0x40, 0xD4, 0x98, 0x00, 0x00, 0x00, 0x00,
            0xB9, 0xBF, 0x00, 0x40, 0x2F, 0x00, 0x00, 0xEB, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_bytes_line_format(self):
        """Строка байтов выводится через запятую с префиксом 0x."""
        line = main.bytes_line(bytes([0xD1, 0x10, 0x00]))
        self.assertEqual(line, "0xD1, 0x10, 0x00")

    def test_empty_program_code(self):
        """Пустая программа даёт пустой машинный код."""
        self.assertEqual(main.machine_code(build("[]")), b"")


class InterpreterTest(unittest.TestCase):
    """Проверки интерпретатора: память, команды, дамп."""

    def test_decode_spec_words(self):
        """Слово из спецификации декодируется обратно в команду."""
        word = main.encode_instruction(build(
            "- load:\n    addr: 67\n    value: 619\n")[0])
        ins = main.decode_word(word, 0)
        self.assertEqual((ins["op"], ins["b"], ins["c"]),
                         ("load", 67, 619))

    def test_decode_unknown_code(self):
        """Нераспознанный код операции — ошибка."""
        with self.assertRaises(main.ConfigError):
            main.decode_word(0x3F, 0)

    def test_read_memory_default_zero(self):
        """Чтение по незаписанному адресу даёт 0."""
        self.assertEqual(main.read_memory({}, 5), 0)

    def test_load_command(self):
        """load записывает значение по адресу."""
        memory = {}
        main.execute({"op": "load", "addr": 7, "value": 123}, memory)
        self.assertEqual(memory[7], 123)

    def test_read_command(self):
        """read копирует слово из одной ячейки в другую."""
        memory = {5: 77}
        main.execute({"op": "read", "dst": 9, "src": 5}, memory)
        self.assertEqual(memory[9], 77)

    def test_write_command_with_pointer(self):
        """write пишет через базовый регистр со смещением."""
        memory = {305: 300}
        main.execute({"op": "write", "src": 662, "offset": 7,
                      "base": 305}, memory)
        self.assertEqual(memory[307], main.read_memory(memory, 662))

    def test_copy_program(self):
        """Программа copy копирует пять слов памяти."""
        text = open(os.path.join(
            os.path.dirname(__file__), "..", "examples",
            "copy.yaml"), encoding="utf-8").read()
        code = main.machine_code(build(text))
        memory = main.run_program(code, False)
        expected = [11, 22, 33, 44, 55]
        copied = [memory[110 + i] for i in range(5)]
        self.assertEqual(copied, expected)

    def test_program_size_not_multiple(self):
        """Код не кратен размеру команды — ошибка."""
        with self.assertRaises(main.ConfigError):
            main.run_program(b"\x00", False)

    def test_check_range_errors(self):
        """Адрес вне диапазона ячеек и отрицательный — ошибки."""
        with self.assertRaises(main.ConfigError):
            main.check_range(5, 4)
        with self.assertRaises(main.ConfigError):
            main.check_range(-1, 4)

    def test_dump_csv_written(self):
        """Дамп CSV содержит заголовок и диапазон адресов."""
        path = os.path.join(os.path.dirname(__file__), "dump_check.csv")
        try:
            main.dump_csv({3: 9}, path, 2, 5)
            with open(path, encoding="utf-8") as source:
                lines = source.read().splitlines()
        finally:
            os.remove(path)
        self.assertEqual(lines, ["address,value", "2,0", "3,9", "4,0"])


class RotateTest(unittest.TestCase):
    """Проверки побитового циклического сдвига влево."""

    def test_rotate_small(self):
        """Циклический сдвиг rol(1, 1) даёт 2."""
        self.assertEqual(main.rotate_left(1, 1), 2)

    def test_rotate_zero_count(self):
        """Сдвиг на 0 оставляет значение без изменений."""
        self.assertEqual(main.rotate_left(123, 0), 123)

    def test_rotate_full_circle(self):
        """Сдвиг на ширину ячейки даёт исходное значение."""
        self.assertEqual(
            main.rotate_left(12345, main.CELL_BITS), 12345)

    def test_rotate_wraps_high_bit(self):
        """Старший бит ячейки при сдвиге уходит в младший."""
        # старший бит ячейки при сдвиге уходит в младший
        self.assertEqual(main.rotate_left(1 << 20, 1), 1)

    def test_rotate_count_more_than_width(self):
        """Счётчик больше ширины ячейки берётся по модулю."""
        self.assertEqual(
            main.rotate_left(1, main.CELL_BITS + 1), 2)

    def test_rol_command(self):
        """Команда rol(3, 2) записывает в память 12."""
        memory = {5: 3, 6: 2}
        main.execute({"op": "rol", "dst": 7, "value": 5,
                      "count": 6}, memory)
        self.assertEqual(memory[7], 12)  # rol(3, 2): 11 -> 1100

    def test_rol_demo_program(self):
        """Демо-программа rol записывает ожидаемые слова."""
        text = open(os.path.join(
            os.path.dirname(__file__), "..", "examples",
            "rol_demo.yaml"), encoding="utf-8").read()
        code = main.machine_code(build(text))
        memory = main.run_program(code, False)
        self.assertEqual(memory[210], 2)
        self.assertEqual(memory[211], 262140)
        self.assertEqual(memory[212], 1)


class UserInputErrorTest(unittest.TestCase):
    """Проверки реакции на ошибки пользователя."""

    def test_empty_document(self):
        """Пустой документ — ошибка конфигурации."""
        with self.assertRaises(main.ConfigError):
            build("")

    def test_comments_only_document(self):
        """Документ из одних комментариев — ошибка конфигурации."""
        with self.assertRaises(main.ConfigError):
            build("# только комментарий\n")

    def test_bool_value(self):
        """Логическое значение вместо числа — ошибка."""
        text = "- load:\n    addr: 1\n    value: true\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_null_value(self):
        """Пустое (null) значение поля — ошибка."""
        text = "- load:\n    addr: 1\n    value:\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_garbage_string_value(self):
        """Строка 'abc' вместо числа — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("value: abc")

    def test_string_with_spaces(self):
        """Числа в строках с пробелами по краям принимаются."""
        text = "- load:\n    addr: ' 67 '\n    value: ' 619 '\n"
        ins = build(text)[0]
        self.assertEqual((ins["b"], ins["c"]), (67, 619))

    def test_negative_offset(self):
        """Отрицательное смещение write — ошибка."""
        text = "- write:\n    src: 1\n    offset: -1\n    base: 3\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_too_big_addr(self):
        """Адрес больше 24 бит — ошибка."""
        text = "- load:\n    addr: 16777216\n    value: 1\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_output_unwritable(self):
        """Запись в несуществующую папку — ошибка конфигурации."""
        path = os.path.join("нет_такой_папки", "выход.bin")
        with self.assertRaises(main.ConfigError):
            main.write_binary(path, b"")

    def test_run_unknown_opcode(self):
        """Неизвестный код операции при выполнении — ошибка."""
        with self.assertRaises(main.ConfigError):
            main.run_program(bytes([0x3F] + [0] * 9), False)

    def test_run_empty_bin(self):
        """Пустой двоичный файл даёт пустую память."""
        self.assertEqual(main.run_program(b"", False), {})

    def test_main_error_return(self):
        """Несуществующий входной файл даёт код выхода EXIT_ERROR."""
        result = main.main(["нет_такого_файла.yaml", "выход.bin"])
        self.assertEqual(result, main.EXIT_ERROR)

    def test_main_unknown_extension(self):
        """Неизвестное расширение входа даёт код выхода EXIT_ERROR."""
        result = main.main(["файл.txt", "выход.bin"])
        self.assertEqual(result, main.EXIT_ERROR)

    def test_rol_empty_memory(self):
        """rol над пустой памятью пишет в ячейку ноль."""
        memory = {}
        main.execute({"op": "rol", "dst": 7, "value": 5,
                      "count": 6}, memory)
        self.assertEqual(memory[7], 0)


class FileErrorTest(unittest.TestCase):
    """Проверки ошибок работы с файлами."""

    def test_input_not_found(self):
        """Несуществующий входной файл — понятная ошибка."""
        with self.assertRaises(main.ConfigError):
            main.read_text("нет_такого_файла.yaml")

    def test_input_is_directory(self):
        """Каталог вместо файла — понятная ошибка."""
        with self.assertRaises(main.ConfigError):
            main.read_text(".")

    def test_input_not_utf8(self):
        """Файл не в UTF-8 — понятная ошибка."""
        path = os.path.join(os.path.dirname(__file__), "bad_utf8.bin")
        with open(path, "wb") as target:
            target.write(b"\xff\xfe\x00")
        try:
            with self.assertRaises(main.ConfigError):
                main.read_text(path)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
