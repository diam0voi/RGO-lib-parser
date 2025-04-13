# tests/test_settings_manager.py
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, call # Используем MagicMock для мока AppState

import pytest

# Импортируем тестируемый класс и зависимости, которые будем мокать/использовать
from src.settings_manager import SettingsManager
# Предполагаем, что AppState находится здесь. Если нет, поправь импорт.
# Нам не нужен сам класс AppState для теста, но нужен для type hinting, если строго
# from src.app_state import AppState # Можно раскомментировать для type hinting

# --- Фикстуры ---

@pytest.fixture
def mock_app_state(mocker) -> MagicMock:
    """Фикстура для создания мока AppState с имитацией состояния."""
    mock = mocker.MagicMock(name="AppStateMock") # Дадим имя для ясности в логах/ошибках
    # Имитируем внутреннее состояние
    mock._current_state = {}

    def _get_settings_dict():
        # Возвращаем копию текущего имитируемого состояния
        # print(f"DEBUG MOCK: get_settings_dict returning {mock._current_state}") # Для отладки
        return mock._current_state.copy()

    def _set_from_dict(data: dict):
        # Обновляем имитируемое состояние (полностью заменяем, как часто бывает)
        # print(f"DEBUG MOCK: set_from_dict called with {data}") # Для отладки
        mock._current_state = data.copy()
        # print(f"DEBUG MOCK: _current_state is now {mock._current_state}") # Для отладки

    # Используем side_effect для имитации поведения
    mock.get_settings_dict.side_effect = _get_settings_dict
    mock.set_from_dict.side_effect = _set_from_dict

    return mock

@pytest.fixture
def temp_settings_file(tmp_path: Path) -> Path:
    """Фикстура для создания пути к временному файлу настроек."""
    return tmp_path / "test_settings.json"

@pytest.fixture
def settings_manager(mock_app_state: MagicMock, temp_settings_file: Path, mocker) -> SettingsManager:
    """Фикстура для создания экземпляра SettingsManager с моками."""
    # Мокаем путь к файлу настроек в КОНФИГЕ, который используется в SettingsManager
    mocker.patch('src.settings_manager.config.SETTINGS_FILE', str(temp_settings_file))

    # Создаем экземпляр SettingsManager
    manager = SettingsManager(app_state=mock_app_state)
    # Убедимся, что он использует наш временный путь
    assert manager.settings_file_path == temp_settings_file
    return manager

# --- Тесты ---

def test_init(settings_manager: SettingsManager, mock_app_state: MagicMock, temp_settings_file: Path):
    """Тестирует инициализацию SettingsManager."""
    assert settings_manager.app_state is mock_app_state
    assert settings_manager.settings_file_path == temp_settings_file
    assert settings_manager.initial_settings_dict == {} # Изначально пустой

def test_load_settings_file_not_found(settings_manager: SettingsManager, mock_app_state: MagicMock, caplog):
    """Тестирует загрузку настроек, когда файл не существует."""
    caplog.set_level(logging.INFO) # Устанавливаем уровень логирования для захвата

    # Убедимся, что файла нет
    assert not settings_manager.settings_file_path.is_file()
    # mock_app_state._current_state изначально {}

    settings_manager.load_settings()

    # Проверяем, что set_from_dict вызван с пустым словарем (т.к. файл не найден)
    mock_app_state.set_from_dict.assert_called_once_with({})
    # Проверяем, что get_settings_dict был вызван для сохранения initial_settings
    mock_app_state.get_settings_dict.assert_called_once()
    # Проверяем, что initial_settings_dict теперь содержит состояние ПОСЛЕ set_from_dict({})
    assert settings_manager.initial_settings_dict == {}

    # Проверяем логи
    assert f"Settings file {settings_manager.settings_file_path} not found, using defaults." in caplog.text

def test_load_settings_file_exists_valid_json(settings_manager: SettingsManager, mock_app_state: MagicMock, temp_settings_file: Path, caplog):
    """Тестирует загрузку настроек из существующего валидного JSON файла."""
    caplog.set_level(logging.INFO)

    settings_data = {"key1": "value1", "nested": {"key2": 123}}

    # Создаем файл с валидным JSON
    temp_settings_file.parent.mkdir(parents=True, exist_ok=True) # Убедимся, что папка есть
    with open(temp_settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings_data, f)

    # Фикстура mock_app_state уже настроена с side_effect,
    # который будет возвращать состояние после set_from_dict

    settings_manager.load_settings()

    # Проверяем, что set_from_dict вызван с данными из файла
    mock_app_state.set_from_dict.assert_called_once_with(settings_data)
    # Проверяем, что get_settings_dict был вызван для сохранения initial_settings
    mock_app_state.get_settings_dict.assert_called_once()
    # Проверяем, что initial_settings_dict содержит загруженные данные (которые вернул get_settings_dict после set_from_dict)
    assert settings_manager.initial_settings_dict == settings_data

    # Проверяем логи
    assert f"Settings loaded successfully from {temp_settings_file}" in caplog.text

def test_load_settings_file_exists_invalid_json(settings_manager: SettingsManager, mock_app_state: MagicMock, temp_settings_file: Path, caplog):
    """Тестирует загрузку настроек из файла с невалидным JSON."""
    caplog.set_level(logging.WARNING)

    # Создаем файл с невалидным JSON
    temp_settings_file.parent.mkdir(parents=True, exist_ok=True) # Убедимся, что папка есть
    with open(temp_settings_file, 'w', encoding='utf-8') as f:
        f.write("this is not json {")

    # mock_app_state._current_state изначально {}

    settings_manager.load_settings()

    # Проверяем, что set_from_dict вызван с пустым словарем (т.к. произошла ошибка)
    mock_app_state.set_from_dict.assert_called_once_with({})
    # Проверяем, что get_settings_dict был вызван для сохранения initial_settings
    mock_app_state.get_settings_dict.assert_called_once()
     # Проверяем, что initial_settings_dict содержит состояние ПОСЛЕ set_from_dict({})
    assert settings_manager.initial_settings_dict == {}

    # Проверяем логи
    assert f"Could not load or parse settings from {temp_settings_file}" in caplog.text
    # Проверяем часть реального сообщения об ошибке JSON
    assert "Expecting value" in caplog.text # Заменили "JSONDecodeError"

def test_save_settings_success(settings_manager: SettingsManager, mock_app_state: MagicMock, temp_settings_file: Path, caplog):
    """Тестирует успешное сохранение настроек."""
    caplog.set_level(logging.INFO)

    settings_to_save = {"user": "tester", "theme": "dark"}
    # Устанавливаем состояние мока, которое должен вернуть get_settings_dict
    mock_app_state._current_state = settings_to_save.copy() # Устанавливаем через имитируемое состояние

    # Выполняем сохранение
    result = settings_manager.save_settings()

    # Проверяем результат
    assert result is True
    # Проверяем, что get_settings_dict был вызван для получения данных
    mock_app_state.get_settings_dict.assert_called_once()
    # Проверяем, что файл был создан и содержит правильные данные
    assert temp_settings_file.is_file()
    with open(temp_settings_file, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    assert saved_data == settings_to_save
    # Проверяем, что initial_settings_dict обновлен после сохранения
    assert settings_manager.initial_settings_dict == settings_to_save

    # Проверяем логи
    assert f"Settings successfully saved to {temp_settings_file}" in caplog.text

def test_save_settings_io_error(settings_manager: SettingsManager, mock_app_state: MagicMock, temp_settings_file: Path, mocker, caplog):
    """Тестирует обработку IOError (OSError) при сохранении настроек."""
    caplog.set_level(logging.ERROR)

    settings_to_save = {"data": "some data"}
    # Устанавливаем состояние мока
    mock_app_state._current_state = settings_to_save.copy()

    # Сохраняем начальное состояние initial_settings_dict перед попыткой сохранения
    initial_state_before_save = settings_manager.initial_settings_dict.copy()

    # Мокаем open, чтобы он вызывал ошибку IOError/OSError при записи
    # Важно: мокаем open в контексте модуля settings_manager, если он импортирован там напрямую,
    # или builtins.open, если используется глобальный open. Судя по коду, используется глобальный.
    mocker.patch('builtins.open', mocker.mock_open()).side_effect = OSError("Disk full")

    # Выполняем сохранение
    result = settings_manager.save_settings()

    # Проверяем результат
    assert result is False
    # Проверяем, что get_settings_dict был вызван
    mock_app_state.get_settings_dict.assert_called_once()
    # Проверяем, что initial_settings_dict НЕ был обновлен
    assert settings_manager.initial_settings_dict == initial_state_before_save

    # Проверяем логи
    assert f"Could not save settings to {temp_settings_file}" in caplog.text
    # Проверяем текст ошибки в логе
    assert "OSError: Disk full" in caplog.text # Используем OSError

def test_save_settings_unexpected_error(settings_manager: SettingsManager, mock_app_state: MagicMock, temp_settings_file: Path, mocker, caplog):
    """Тестирует обработку неожиданной ошибки при сохранении настроек."""
    caplog.set_level(logging.ERROR)

    settings_to_save = {"config": "test"}
    # Устанавливаем состояние мока
    mock_app_state._current_state = settings_to_save.copy()

    initial_state_before_save = settings_manager.initial_settings_dict.copy()

    # Мокаем json.dump, чтобы он вызывал неожиданную ошибку
    # Путь к json.dump как он используется в settings_manager.py
    mocker.patch('src.settings_manager.json.dump', side_effect=TypeError("Unexpected type"))

    # Выполняем сохранение
    result = settings_manager.save_settings()

    # Проверяем результат
    assert result is False
     # Проверяем, что get_settings_dict был вызван
    mock_app_state.get_settings_dict.assert_called_once()
    # Проверяем, что initial_settings_dict НЕ был обновлен
    assert settings_manager.initial_settings_dict == initial_state_before_save

    # Проверяем логи
    assert "Unexpected error saving settings" in caplog.text
    assert "TypeError: Unexpected type" in caplog.text


def test_save_settings_if_changed_when_changed(settings_manager: SettingsManager, mock_app_state: MagicMock, mocker, caplog):
    """Тестирует вызов сохранения, если настройки изменились."""
    caplog.set_level(logging.INFO)

    # Устанавливаем начальное состояние в менеджере
    settings_manager.initial_settings_dict = {"key": "initial_value"}

    # Устанавливаем ИЗМЕНЕННОЕ состояние в моке AppState
    current_settings = {"key": "new_value"}
    mock_app_state._current_state = current_settings.copy()

    # Мокаем сам метод save_settings, чтобы проверить его вызов
    mock_save = mocker.patch.object(settings_manager, 'save_settings', return_value=True)

    settings_manager.save_settings_if_changed()

    # Проверяем, что get_settings_dict был вызван для сравнения
    mock_app_state.get_settings_dict.assert_called_once()
    # Проверяем, что save_settings был вызван
    mock_save.assert_called_once()
    # Проверяем логи
    assert "Settings have changed since last load/save. Saving..." in caplog.text

def test_save_settings_if_changed_when_unchanged(settings_manager: SettingsManager, mock_app_state: MagicMock, mocker, caplog):
    """Тестирует пропуск сохранения, если настройки не изменились."""
    caplog.set_level(logging.INFO)

    # Устанавливаем начальное состояние в менеджере
    initial_settings = {"key": "value"}
    settings_manager.initial_settings_dict = initial_settings.copy() # Используем копию

    # Устанавливаем ТАКОЕ ЖЕ состояние в моке AppState
    mock_app_state._current_state = initial_settings.copy() # Устанавливаем через имитируемое состояние

    # Мокаем save_settings
    mock_save = mocker.patch.object(settings_manager, 'save_settings')

    settings_manager.save_settings_if_changed()

     # Проверяем, что get_settings_dict был вызван для сравнения
    mock_app_state.get_settings_dict.assert_called_once()
    # Проверяем, что save_settings НЕ был вызван
    mock_save.assert_not_called()
    # Проверяем логи
    assert "Settings are unchanged. Skipping save on exit." in caplog.text
    # Убедимся, что лога об изменениях НЕТ
    assert "Settings have changed" not in caplog.text

def test_save_settings_if_changed_when_changed_but_save_fails(settings_manager: SettingsManager, mock_app_state: MagicMock, mocker, caplog):
    """Тестирует случай, когда настройки изменились, но сохранение не удалось."""
    caplog.set_level(logging.ERROR) # Ловим ошибку

    # Устанавливаем начальное состояние
    settings_manager.initial_settings_dict = {"a": 1}
    # Устанавливаем измененное состояние в моке
    mock_app_state._current_state = {"a": 2}.copy() # Изменились

    # Мокаем save_settings, чтобы он вернул False (ошибка сохранения)
    mock_save = mocker.patch.object(settings_manager, 'save_settings', return_value=False)

    settings_manager.save_settings_if_changed()

    # Проверяем, что get_settings_dict был вызван для сравнения
    mock_app_state.get_settings_dict.assert_called_once()
    # Проверяем, что save_settings был вызван
    mock_save.assert_called_once()
    # Проверяем лог ошибки
    assert "Failed to save settings on exit." in caplog.text
