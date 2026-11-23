"""Тесты этапа 3: машинный код и интерпретатор с памятью."""

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
        """Код команды load совпадает с тестом спецификации."""
        code = main.instruction_bytes(build(
            "- load:\n    addr: 67\n    value: 619\n")[0])
        expected = bytes([0xD1, 0x10, 0x00, 0xC0, 0x9A, 0x00,
                          0x00, 0x00, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_read_bytes(self):
        """Код команды read совпадает с тестом спецификации."""
        code = main.instruction_bytes(build(
            "- read:\n    dst: 737\n    src: 274\n")[0])
        expected = bytes([0x6B, 0xB8, 0x00, 0x80, 0x44, 0x00,
                          0x00, 0x00, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_write_bytes(self):
        """Код команды write совпадает с тестом спецификации."""
        text = ("- write:\n    src: 662\n    offset: 337\n"
                "    base: 305\n")
        code = main.instruction_bytes(build(text)[0])
        expected = bytes([0x95, 0xA5, 0x00, 0x40, 0xD4, 0x98,
                          0x00, 0x00, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_rol_bytes(self):
        """Код команды rol совпадает с тестом спецификации."""
        text = "- rol:\n    dst: 189\n    value: 940\n    count: 766\n"
        code = main.instruction_bytes(build(text)[0])
        expected = bytes([0xB9, 0xBF, 0x00, 0x40, 0x2F, 0x00,
                          0x00, 0xEB, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_full_program_bytes(self):
        """Программа из спецификации кодируется побайтово верно."""
        code = main.machine_code(self.spec_program())
        self.assertEqual(len(code), 4 * main.CMD_SIZE)
        expected = bytes([
            0xD1, 0x10, 0x00, 0xC0, 0x9A, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x6B, 0xB8, 0x00, 0x80, 0x44, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x95, 0xA5, 0x00, 0x40, 0xD4, 0x98, 0x00, 0x00, 0x00, 0x00,
            0xB9, 0xBF, 0x00, 0x40, 0x2F, 0x00, 0x00, 0xEB, 0x00, 0x00])
        self.assertEqual(code, expected)

    def test_bytes_line_format(self):
        """Строка байтов форматируется как 0xNN через запятую."""
        line = main.bytes_line(bytes([0xD1, 0x10, 0x00]))
        self.assertEqual(line, "0xD1, 0x10, 0x00")

    def test_empty_program_code(self):
        """Пустая программа даёт пустой машинный код."""
        self.assertEqual(main.machine_code(build("[]")), b"")


class InterpreterTest(unittest.TestCase):
    """Проверки интерпретатора: память, команды, дамп."""

    def test_decode_spec_words(self):
        """Декодирование машинного слова возвращает команду load."""
        word = main.encode_instruction(build(
            "- load:\n    addr: 67\n    value: 619\n")[0])
        ins = main.decode_word(word, 0)
        self.assertEqual((ins["op"], ins["b"], ins["c"]),
                         ("load", 67, 619))

    def test_decode_unknown_code(self):
        """Неизвестный код операции при декодировании — ошибка."""
        with self.assertRaises(main.ConfigError):
            main.decode_word(0x3F, 0)

    def test_read_memory_default_zero(self):
        """Чтение по незанятому адресу даёт ноль."""
        self.assertEqual(main.read_memory({}, 5), 0)

    def test_load_command(self):
        """load записывает значение по указанному адресу."""
        memory = {}
        main.execute({"op": "load", "addr": 7, "value": 123}, memory)
        self.assertEqual(memory[7], 123)

    def test_read_command(self):
        """read копирует слово из src в dst."""
        memory = {5: 77}
        main.execute({"op": "read", "dst": 9, "src": 5}, memory)
        self.assertEqual(memory[9], 77)

    def test_write_command_with_pointer(self):
        """write сохраняет слово по адресу base + offset."""
        memory = {305: 300}
        main.execute({"op": "write", "src": 662, "offset": 7,
                      "base": 305}, memory)
        self.assertEqual(memory[307], main.read_memory(memory, 662))

    def test_rol_not_supported_yet(self):
        """Команда rol в интерпретаторе пока не поддерживается."""
        memory = {1: 2}
        with self.assertRaises(main.ConfigError):
            main.execute({"op": "rol", "dst": 3, "value": 1,
                          "count": 1}, memory)

    def test_copy_program(self):
        """Программа copy.yaml копирует пять слов в новые адреса."""
        text = open(os.path.join(
            os.path.dirname(__file__), "..", "examples",
            "copy.yaml"), encoding="utf-8").read()
        code = main.machine_code(build(text))
        memory = main.run_program(code, False)
        expected = [11, 22, 33, 44, 55]
        copied = [memory[110 + i] for i in range(5)]
        self.assertEqual(copied, expected)

    def test_program_size_not_multiple(self):
        """Код не кратен длине команды — ошибка запуска."""
        with self.assertRaises(main.ConfigError):
            main.run_program(b"\x00", False)

    def test_check_range_errors(self):
        """check_range ловит отрицательные и завышенные значения."""
        with self.assertRaises(main.ConfigError):
            main.check_range(5, 4)
        with self.assertRaises(main.ConfigError):
            main.check_range(-1, 4)

    def test_dump_csv_written(self):
        """Дамп CSV содержит шапку и диапазон адресов с нулями."""
        path = os.path.join(os.path.dirname(__file__), "dump_check.csv")
        try:
            main.dump_csv({3: 9}, path, 2, 5)
            with open(path, encoding="utf-8") as source:
                lines = source.read().splitlines()
        finally:
            os.remove(path)
        self.assertEqual(lines, ["address,value", "2,0", "3,9", "4,0"])


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


class UserInputErrorTest(unittest.TestCase):
    """Проверки реакций на «глупые» ошибки пользователя."""

    def test_empty_document(self):
        """Пустой YAML-документ — ошибка конфигурации."""
        with self.assertRaises(main.ConfigError):
            build("")

    def test_comments_only_document(self):
        """Документ только из комментария — ошибка конфигурации."""
        with self.assertRaises(main.ConfigError):
            build("# только комментарий\n")

    def test_bool_value(self):
        """Логическое значение вместо числа — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: 1\n    value: true\n")

    def test_null_value(self):
        """Пустое (null) значение поля — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: 1\n    value:\n")

    def test_garbage_string_value(self):
        """Слово вместо числа в корне программы — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("value: abc")

    def test_string_with_spaces(self):
        """Числа-строки с пробелами по краям принимаются."""
        ins = build("- load:\n    addr: ' 67 '\n    value: ' 619 '\n")[0]
        self.assertEqual((ins["b"], ins["c"]), (67, 619))

    def test_negative_offset(self):
        """Отрицательное смещение write — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- write:\n    src: 1\n    offset: -1\n    base: 3\n")

    def test_too_big_addr(self):
        """Адрес за границей 24 бит — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: 16777216\n    value: 1\n")

    def test_output_unwritable(self):
        """Запись в несуществующую папку — понятная ошибка."""
        path = os.path.join("нет_такой_папки", "выход.bin")
        with self.assertRaises(main.ConfigError):
            main.write_binary(path, b"")

    def test_run_unknown_opcode(self):
        """Неизвестный код команды 63 при выполнении — ошибка."""
        with self.assertRaises(main.ConfigError):
            main.run_program(bytes([0x3F] + [0] * 9), False)

    def test_run_empty_bin(self):
        """Пустая программа ничего не делает: память пуста."""
        self.assertEqual(main.run_program(b"", False), {})

    def test_main_error_return(self):
        """Несуществующий входной файл даёт код EXIT_ERROR."""
        argv = ["нет_такого_файла.yaml", "не_будет_создан.bin"]
        self.assertEqual(main.main(argv), main.EXIT_ERROR)

    def test_main_unknown_extension(self):
        """Расширение .txt не определяет режим: код EXIT_ERROR."""
        argv = ["файл.txt", "не_будет_создан.csv"]
        self.assertEqual(main.main(argv), main.EXIT_ERROR)


if __name__ == "__main__":
    unittest.main()
