import errno
import logging
from pathlib import Path
from unittest.mock import patch
from typing import Optional

import pytest

# Предполагаем, что pytest запускается из корня проекта,
# и src/ добавлен в PYTHONPATH или проект установлен как editable.
# Если будут проблемы с импортами, возможно, понадобится настроить PYTHONPATH
# или использовать относительные импорты, если структура тестов это позволяет.
from src import config
from src.app_state import AppState

# Отключаем логирование в тестах, чтобы не засорять вывод,
# если только не отлаживаем сами тесты.
logging.disable(logging.CRITICAL)


# Простая заглушка для tk.StringVar
class MockStringVar:
    def __init__(self, value=""):
        self._value = str(value)  # StringVar всегда хранит строку

    def get(self):
        return self._value

    def set(self, value):
        self._value = str(value)  # Убедимся, что храним строку


# Фикстура для автоматической подмены tk.StringVar во всех тестах этого модуля
@pytest.fixture(autouse=True)
def mock_tkinter(monkeypatch):
    # Используем monkeypatch для подмены StringVar во всем модуле app_state
    monkeypatch.setattr("src.app_state.tk.StringVar", MockStringVar)
    # Если бы AppState импортировал tk напрямую (import tkinter as tk),
    # патч выглядел бы так:
    # monkeypatch.setattr("src.app_state.tk.StringVar", MockStringVar)
    # Если импорт был 'from tkinter import StringVar', патч был бы:
    # monkeypatch.setattr("src.app_state.StringVar", MockStringVar)
    # Важно патчить там, где объект *используется* (в данном случае в app_state.py)


@pytest.fixture
def app_state() -> AppState:
    """Фикстура для создания экземпляра AppState."""
    # Tkinter уже замокан благодаря mock_tkinter
    return AppState()


# --- Тесты ---


def test_initialization(app_state: AppState):
    """Тест инициализации AppState значениями по умолчанию."""
    assert app_state.url_base.get() == config.DEFAULT_URL_BASE
    assert app_state.url_ids.get() == config.DEFAULT_URL_IDS
    assert app_state.pdf_filename.get() == config.DEFAULT_PDF_FILENAME
    assert app_state.total_pages.get() == config.DEFAULT_TOTAL_PAGES
    assert app_state.pages_dir.get() == config.DEFAULT_PAGES_DIR
    assert app_state.spreads_dir.get() == config.DEFAULT_SPREADS_DIR


def test_get_settings_dict(app_state: AppState):
    """Тест получения словаря настроек."""
    # Можно изменить одно значение для проверки
    test_url = "http://new.example.com/"
    app_state.url_base.set(test_url)

    expected_dict = {
        "url_base": test_url,
        "url_ids": config.DEFAULT_URL_IDS,
        "pdf_filename": config.DEFAULT_PDF_FILENAME,
        "total_pages": config.DEFAULT_TOTAL_PAGES,
        "pages_dir": config.DEFAULT_PAGES_DIR,
        "spreads_dir": config.DEFAULT_SPREADS_DIR,
    }
    assert app_state.get_settings_dict() == expected_dict


def test_set_from_dict(app_state: AppState):
    """Тест установки значений из словаря."""
    settings_to_set = {
        "url_base": "http://test.com",
        "url_ids": "test_ids",
        "pdf_filename": "test.pdf",
        "total_pages": "99",
        # 'pages_dir' пропущен
        "spreads_dir": "test_spreads",
    }
    app_state.set_from_dict(settings_to_set)

    assert app_state.url_base.get() == "http://test.com"
    assert app_state.url_ids.get() == "test_ids"
    assert app_state.pdf_filename.get() == "test.pdf"
    assert app_state.total_pages.get() == "99"
    assert (
        app_state.pages_dir.get() == config.DEFAULT_PAGES_DIR
    )  # Должно остаться значение по умолчанию
    assert app_state.spreads_dir.get() == "test_spreads"


def test_set_from_dict_empty(app_state: AppState):
    """Тест установки значений из пустого словаря (все должно стать по умолчанию)."""
    # Сначала установим не-умолчательные значения
    app_state.url_base.set("some_value")
    app_state.total_pages.set("123")

    # Теперь установим из пустого словаря
    app_state.set_from_dict({})

    # Проверяем, что все вернулось к значениям по умолчанию
    assert app_state.url_base.get() == config.DEFAULT_URL_BASE
    assert app_state.url_ids.get() == config.DEFAULT_URL_IDS
    assert app_state.pdf_filename.get() == config.DEFAULT_PDF_FILENAME
    assert app_state.total_pages.get() == config.DEFAULT_TOTAL_PAGES
    assert app_state.pages_dir.get() == config.DEFAULT_PAGES_DIR
    assert app_state.spreads_dir.get() == config.DEFAULT_SPREADS_DIR


@pytest.mark.parametrize(
    "pages_input, expected_output",
    [
        ("10", 10),
        (" 5 ", 5),  # Пробелы должны обрезаться
        ("1", 1),
        ("0", None),  # 0 невалидно
        ("-5", None),  # Отрицательное невалидно
        ("abc", None),  # Не число
        ("", None),  # Пустая строка
        (" ", None),  # Строка с пробелами
        ("10.5", None),  # Дробное число
    ],
)
def test_get_total_pages_int(
    app_state: AppState, pages_input: str, expected_output: Optional[int]
):
    """Тест получения количества страниц как int."""
    app_state.total_pages.set(pages_input)
    assert app_state.get_total_pages_int() == expected_output


# --- Тесты валидации ---


def test_validate_for_download_valid(app_state: AppState):
    """Тест валидации для скачивания с корректными данными."""
    # Установим валидные (непустые) значения, включая > 0 страниц
    app_state.url_base.set("http://example.com")
    app_state.url_ids.set("12345")
    app_state.pdf_filename.set("document.pdf")
    app_state.total_pages.set("25")
    app_state.pages_dir.set("./download_pages")
    # spreads_dir не проверяется здесь

    assert app_state.validate_for_download() == []


@pytest.mark.parametrize(
    "field_to_invalidate, value, expected_error_part",
    [
        ("url_base", "", "Базовый URL"),
        ("url_ids", " ", "ID файла"),  # Пробелы тоже считаются невалидными
        ("pdf_filename", "", "Имя файла на сайте"),
        ("pages_dir", "", "Папка для страниц"),
        ("total_pages", "", "Кол-во страниц"),
        ("total_pages", "0", "Кол-во страниц (должно быть > 0)"),
        ("total_pages", "-10", "Кол-во страниц (должно быть > 0)"),
        ("total_pages", "abc", "Кол-во страниц (должно быть числом)"),
    ],
)
def test_validate_for_download_invalid(
    app_state: AppState, field_to_invalidate: str, value: str, expected_error_part: str
):
    """Тест валидации для скачивания с одним невалидным полем."""
    # Сначала установим все валидные значения
    app_state.url_base.set("http://example.com")
    app_state.url_ids.set("12345")
    app_state.pdf_filename.set("document.pdf")
    app_state.total_pages.set("25")
    app_state.pages_dir.set("./download_pages")

    # Теперь сделаем одно поле невалидным
    getattr(app_state, field_to_invalidate).set(value)

    errors = app_state.validate_for_download()
    assert len(errors) == 1
    assert expected_error_part in errors[0]  # Проверяем наличие части ошибки


def test_validate_for_download_multiple_invalid(app_state: AppState):
    """Тест валидации для скачивания с несколькими невалидными полями."""
    # Явно устанавливаем невалидные значения для полей, которые должны вызвать ошибку
    app_state.url_base.set("")  # Невалидно
    app_state.url_ids.set("  ")  # Невалидно (пробелы)
    app_state.pdf_filename.set("")  # Невалидно
    app_state.pages_dir.set("")  # Невалидно
    app_state.total_pages.set("abc")  # Невалидно (не число)
    # spreads_dir не проверяется в этой валидации

    errors = app_state.validate_for_download()
    expected_error_count = 5
    assert len(errors) == expected_error_count, (
        f"Ожидалось {expected_error_count} ошибок, получено {len(errors)}: {errors}"
    )

    error_messages = set(
        errors
    )  # Используем set для проверки наличия без учета порядка
    expected_errors = {
        "Базовый URL",
        "ID файла",
        "Имя файла на сайте",
        "Папка для страниц",
        "Кол-во страниц (должно быть числом)",
    }
    assert error_messages == expected_errors


# --- Тесты validate_for_processing ---


def test_validate_for_processing_valid(app_state: AppState, tmp_path: Path):
    """Тест валидации для обработки с корректными, существующими папками."""
    pages_dir = tmp_path / "pages"
    spreads_dir = tmp_path / "spreads"
    pages_dir.mkdir()
    # spreads_dir не обязательно должна существовать для этой валидации,
    # но pages_dir должна, если check_dir_exists=True (по умолчанию)

    app_state.pages_dir.set(str(pages_dir))
    app_state.spreads_dir.set(str(spreads_dir))

    assert app_state.validate_for_processing() == []  # check_dir_exists=True


def test_validate_for_processing_pages_dir_not_exists(
    app_state: AppState, tmp_path: Path
):
    """Тест валидации для обработки, когда папка страниц не существует."""
    pages_dir = tmp_path / "non_existent_pages"
    spreads_dir = tmp_path / "spreads"
    # Не создаем pages_dir

    app_state.pages_dir.set(str(pages_dir))
    app_state.spreads_dir.set(str(spreads_dir))

    errors = app_state.validate_for_processing()
    assert len(errors) == 1
    assert f"Папка для страниц ('{pages_dir!s}' не найдена)" in errors[0]


def test_validate_for_processing_pages_dir_is_file(app_state: AppState, tmp_path: Path):
    """Тест валидации для обработки, когда путь к папке страниц указывает на файл."""
    pages_file = tmp_path / "pages_file.txt"
    pages_file.touch()  # Создаем файл
    spreads_dir = tmp_path / "spreads"

    app_state.pages_dir.set(str(pages_file))
    app_state.spreads_dir.set(str(spreads_dir))

    errors = app_state.validate_for_processing()
    assert len(errors) == 1
    # Path.is_dir() вернет False для файла, ошибка будет та же, что и для несуществующей папки
    assert f"Папка для страниц ('{pages_file!s}' не найдена)" in errors[0]


def test_validate_for_processing_empty_paths(app_state: AppState):
    """Тест валидации для обработки с пустыми путями."""
    app_state.pages_dir.set("")
    app_state.spreads_dir.set(" ")  # Путь с пробелами

    errors = app_state.validate_for_processing()
    assert len(errors) == 2
    error_messages = set(errors)
    assert "Папка для страниц" in error_messages
    assert "Папка для разворотов" in error_messages


def test_validate_for_processing_no_dir_check(app_state: AppState, tmp_path: Path):
    """Тест валидации для обработки с check_dir_exists=False."""
    pages_dir = tmp_path / "non_existent_pages"
    spreads_dir = tmp_path / "non_existent_spreads"
    # Папки не создаем

    app_state.pages_dir.set(str(pages_dir))
    app_state.spreads_dir.set(str(spreads_dir))

    # Проверка существования папки отключена
    errors = app_state.validate_for_processing(check_dir_exists=False)
    assert errors == []  # Ошибок быть не должно, т.к. пути не пустые


def test_validate_for_processing_empty_paths_no_dir_check(app_state: AppState):
    """Тест валидации пустых путей с check_dir_exists=False."""
    app_state.pages_dir.set("")
    app_state.spreads_dir.set("")

    # Проверка на пустые строки выполняется до проверки существования папки
    errors = app_state.validate_for_processing(check_dir_exists=False)
    assert len(errors) == 2
    error_messages = set(errors)
    assert "Папка для страниц" in error_messages
    assert "Папка для разворотов" in error_messages


def test_validate_for_processing_permission_error(app_state: AppState, tmp_path: Path):
    """Тест ошибки доступа (PermissionError) при валидации папки страниц."""
    pages_dir = tmp_path / "restricted_pages"
    pages_dir.mkdir()  # Папка должна существовать и быть директорией

    app_state.pages_dir.set(str(pages_dir))
    app_state.spreads_dir.set(str(tmp_path / "spreads"))  # Должно быть не пустым

    error_message = "Permission denied simulation"
    # Мокаем os.listdir в модуле app_state, чтобы он вызвал ошибку
    # Создаем экземпляр OSError с кодом EACCES (Permission denied)
    permission_error = OSError(errno.EACCES, error_message)
    permission_error.filename = str(pages_dir)  # OSError часто содержит имя файла/пути

    with patch(
        "src.app_state.os.listdir", side_effect=permission_error
    ) as mock_listdir:
        # Мы также должны убедиться, что Path(pages_dir).is_dir() вернет True
        # Это можно сделать, мокнув Path, но проще убедиться, что папка реально создана (что мы и сделали)
        # и мокать только os.listdir
        errors = app_state.validate_for_processing()

        # Проверяем результат
        assert len(errors) == 1, f"Ожидалась 1 ошибка, получено: {errors}"
        assert "Папка для страниц (ошибка доступа/чтения:" in errors[0]
        # Проверим, что текст нашей ошибки попал в сообщение
        # Формат вывода OSError может немного отличаться, поэтому ищем подстроку
        assert error_message in errors[0]

        # Убедимся, что наш мок был вызван с правильным путем
        mock_listdir.assert_called_once_with(Path(pages_dir))
