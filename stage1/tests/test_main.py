"""Тесты этапа 1: разбор YAML и промежуточное представление."""

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
        """Лишний аргумент команды — ошибка."""
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
    """Проверки «глупых» ошибок пользователя во входных данных."""

    def test_empty_document(self):
        """Пустой YAML-файл (без команд) — ошибка, а не падение."""
        with self.assertRaises(main.ConfigError):
            build("")

    def test_comments_only_document(self):
        """Файл только из комментариев — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("# только комментарий\n")

    def test_bool_value(self):
        """Логическое значение вместо числа — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: 1\n    value: true\n")

    def test_null_value(self):
        """Пустое поле (null) вместо числа — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: 1\n    value:\n")

    def test_garbage_string_value(self):
        """Мусорная строка вместо числа — ошибка."""
        with self.assertRaises(main.ConfigError):
            build("- load:\n    addr: 1\n    value: abc\n")

    def test_string_with_spaces(self):
        """Число с лишними пробелами принимается."""
        ins = build("- load:\n    addr: ' 67 '\n    value: ' 619 '\n")[0]
        self.assertEqual((ins["b"], ins["c"]), (67, 619))

    def test_negative_offset(self):
        """Отрицательное смещение write — ошибка."""
        text = "- write:\n    src: 1\n    offset: -1\n    base: 3\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_too_big_addr(self):
        """Адрес больше 24 бит (16777216) — ошибка."""
        text = "- load:\n    addr: 16777216\n    value: 1\n"
        with self.assertRaises(main.ConfigError):
            build(text)

    def test_output_unwritable(self):
        """Запись в несуществующую папку — понятная ошибка."""
        bad = os.path.join("нет_такой_папки", "выход.txt")
        with self.assertRaises(main.ConfigError):
            main.write_text(bad, "текст")


if __name__ == "__main__":
    unittest.main()
