import logging
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from PIL import Image, UnidentifiedImageError


from src import utils
from src import config


# --- Тесты для get_page_number ---
@pytest.mark.parametrize(
    "filename, expected",
    [
        ("page_001.jpg", 1),
        ("cover02.png", 2),
        ("img_12345_extra.tif", 12345),
        ("no_number_here.gif", -1),
        ("prefix_1_suffix_2.bmp", 1),
        ("", -1),
        (None, -1),
        ("image_with_zero_0.jpg", 0),
        ("123.jpg", 123),
        ("00045.png", 45),
    ],
    ids=[
        "standard", "leading_text", "long_number", "no_number", "multiple_numbers",
        "empty_string", "none_input", "zero_value", "number_at_start", "leading_zeros",
    ]
)
def test_get_page_number(filename, expected):
    assert utils.get_page_number(filename) == expected


# --- Тесты для is_likely_spread ---
@pytest.fixture
def mock_config_threshold(mocker):
    return mocker.patch('src.utils.config.DEFAULT_ASPECT_RATIO_THRESHOLD', 1.5)


@pytest.fixture
def mock_image_open(mocker):
    mock_img = MagicMock(spec=Image.Image)
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_img
    mock_context_manager.__exit__.return_value = None
    return mocker.patch('PIL.Image.open', return_value=mock_context_manager), mock_img


def test_is_likely_spread_true_default_threshold(mock_image_open, mock_config_threshold, caplog):
    mock_open, mock_img = mock_image_open
    mock_img.size = (2000, 1000)
    image_path = "dummy/path/wide_image.jpg"
    caplog.set_level(logging.DEBUG, logger='src.utils')
    assert utils.is_likely_spread(image_path) is True
    mock_open.assert_called_once_with(image_path)
    assert f"Image: wide_image.jpg, Size: 2000x1000, Ratio: 2.00, Threshold: 1.5" in caplog.text


def test_is_likely_spread_false_default_threshold(mock_image_open, mock_config_threshold, caplog):
    mock_open, mock_img = mock_image_open
    mock_img.size = (1500, 1000)
    image_path = Path("dummy/path/normal_image.png")
    caplog.set_level(logging.DEBUG, logger='src.utils')
    assert utils.is_likely_spread(image_path) is False
    mock_open.assert_called_once_with(image_path)
    assert f"Image: normal_image.png, Size: 1500x1000, Ratio: 1.50, Threshold: 1.5" in caplog.text


def test_is_likely_spread_true_custom_threshold(mock_image_open, caplog):
    mock_open, mock_img = mock_image_open
    mock_img.size = (1200, 1000)
    custom_threshold = 1.1
    image_path = "dummy/path/custom_wide.tif"
    caplog.set_level(logging.DEBUG, logger='src.utils')
    assert utils.is_likely_spread(image_path, threshold=custom_threshold) is True
    mock_open.assert_called_once_with(image_path)
    assert f"Image: custom_wide.tif, Size: 1200x1000, Ratio: 1.20, Threshold: {custom_threshold:.1f}" in caplog.text


def test_is_likely_spread_false_custom_threshold(mock_image_open, caplog):
    mock_open, mock_img = mock_image_open
    mock_img.size = (1000, 1000)
    custom_threshold = 1.1
    image_path = "dummy/path/custom_narrow.gif"
    caplog.set_level(logging.DEBUG, logger='src.utils')
    assert utils.is_likely_spread(image_path, threshold=custom_threshold) is False
    mock_open.assert_called_once_with(image_path)
    assert f"Image: custom_narrow.gif, Size: 1000x1000, Ratio: 1.00, Threshold: {custom_threshold:.1f}" in caplog.text


def test_is_likely_spread_file_not_found(mock_image_open, caplog):
    mock_open, _ = mock_image_open
    image_path = "non_existent_file.jpg"
    mock_open.side_effect = FileNotFoundError(f"File not found: {image_path}")
    caplog.set_level(logging.ERROR, logger='src.utils')
    assert utils.is_likely_spread(image_path) is False
    mock_open.assert_called_once_with(image_path)
    assert f"Image file not found for aspect ratio check: {image_path}" in caplog.text


def test_is_likely_spread_image_open_error(mock_image_open, caplog):
    mock_open, _ = mock_image_open
    image_path = "corrupted_file.jpg"
    mock_open.side_effect = UnidentifiedImageError("Cannot identify image file")
    caplog.set_level(logging.WARNING, logger='src.utils')
    assert utils.is_likely_spread(image_path) is False
    mock_open.assert_called_once_with(image_path)
    assert f"Could not check aspect ratio for {image_path}: Cannot identify image file" in caplog.text


def test_is_likely_spread_zero_height(mock_image_open, caplog):
    mock_open, mock_img = mock_image_open
    mock_img.size = (1000, 0)
    image_path = "zero_height.jpg"
    caplog.set_level(logging.WARNING, logger='src.utils')
    assert utils.is_likely_spread(image_path) is False
    mock_open.assert_called_once_with(image_path)
    assert f"Image has zero height: {image_path}" in caplog.text


# --- Тесты для resource_path ---
@pytest.fixture
def mock_sys_meipass(mocker, tmp_path):
    dummy_meipass_path = tmp_path / "_MEIPASS_BUNDLE"
    dummy_meipass_path.mkdir()
    dummy_meipass_str = str(dummy_meipass_path.resolve())
    mocker.patch.object(sys, '_MEIPASS', dummy_meipass_str, create=True)
    return dummy_meipass_str

@pytest.fixture
def mock_sys_no_meipass(mocker):
    if hasattr(sys, '_MEIPASS'):
        mocker.patch.object(sys, '_MEIPASS', 'dummy', create=True)
        delattr(sys, '_MEIPASS')
    yield


def test_resource_path_normal_mode(mock_sys_no_meipass, caplog):
    caplog.set_level(logging.DEBUG, logger='src.utils')
    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent
    expected_base_path = project_root
    relative = "data/some_resource.txt"
    expected_path = (expected_base_path / relative).resolve()

    actual_path_str = utils.resource_path(relative)
    actual_path = Path(actual_path_str).resolve()

    assert actual_path == expected_path
    assert f"Running as script, calculated project root: {expected_base_path.resolve()}" in caplog.text
    assert f"Resolved resource path for '{relative}': '{expected_path}'" in caplog.text

def test_resource_path_pyinstaller_mode(mock_sys_meipass, caplog):
    caplog.set_level(logging.DEBUG, logger='src.utils')
    meipass_path_str = mock_sys_meipass
    relative = "assets/icon.ico"
    expected_path = (Path(meipass_path_str) / relative).resolve()

    actual_path_str = utils.resource_path(relative)
    actual_path = Path(actual_path_str).resolve()

    assert actual_path == expected_path
    assert f"Running in PyInstaller bundle, MEIPASS: {meipass_path_str}" in caplog.text
    assert f"Resolved resource path for '{relative}': '{expected_path}'" in caplog.text


# --- Тесты для setup_logging ---

# Патчи для Formatter, Handler, getLogger, info остаются декораторами
@patch('src.utils.logging.Formatter', autospec=True)
@patch('src.utils.logging.handlers.RotatingFileHandler', autospec=True)
@patch('src.utils.logging.getLogger')
@patch('src.utils.logging.info')
def test_setup_logging_success(
    mock_logging_info,
    mock_get_logger,
    mock_handler_cls,
    mock_formatter_cls,
    mocker,
    capsys
):
    """Тест: Успешная настройка логирования."""
    # Значения для теста
    log_file_path = "/fake/path/app.log"
    dir_path_str = "/fake/path"
    log_max_bytes = 1024 * 1024
    log_backup_count = 5
    log_level = logging.DEBUG
    app_name = "TestApp"

    # Моки для логгера и хендлера
    mock_root_logger = MagicMock(spec=logging.RootLogger)
    mock_get_logger.return_value = mock_root_logger
    mock_handler_instance = mock_handler_cls.return_value
    mock_formatter_instance = mock_formatter_cls.return_value

    # --- Настройка мока Path внутри теста ---
    mock_path_cls = mocker.patch.object(utils, 'Path', autospec=True)
    mock_log_path_instance = MagicMock(spec=Path)
    mock_log_dir_instance = MagicMock(spec=Path)
    mock_path_cls.return_value = mock_log_path_instance
    mock_log_path_instance.__fspath__.return_value = log_file_path
    mock_log_path_instance.__str__.return_value = log_file_path
    parent_mock = PropertyMock(return_value=mock_log_dir_instance)
    type(mock_log_path_instance).parent = parent_mock
    mock_log_dir_instance.is_dir.return_value = True
    mock_log_dir_instance.__str__.return_value = dir_path_str
    # --- Конец настройки мока Path ---

    # --- Патчим атрибуты config напрямую ---
    mocker.patch.object(config, 'LOG_FILE', log_file_path)
    mocker.patch.object(config, 'LOG_MAX_BYTES', log_max_bytes)
    mocker.patch.object(config, 'LOG_BACKUP_COUNT', log_backup_count)
    mocker.patch.object(config, 'LOG_LEVEL', log_level)
    mocker.patch.object(config, 'APP_NAME', app_name)
    # --- Конец патчинга config ---

    utils.setup_logging()

    # Проверки
    mock_path_cls.assert_called_once_with(log_file_path)
    parent_mock.assert_called_once()
    mock_log_dir_instance.is_dir.assert_called_once()
    mock_log_dir_instance.mkdir.assert_not_called()
    mock_formatter_cls.assert_called_once_with('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    mock_handler_cls.assert_called_once_with(
        log_file_path,
        maxBytes=log_max_bytes, # Используем переменную
        backupCount=log_backup_count, # Используем переменную
        encoding='utf-8'
    )
    mock_handler_instance.setFormatter.assert_called_once_with(mock_formatter_instance)
    mock_handler_instance.setLevel.assert_called_once_with(log_level) # Используем переменную
    mock_get_logger.assert_called_once_with()
    mock_root_logger.setLevel.assert_called_once_with(log_level) # Используем переменную
    mock_root_logger.addHandler.assert_called_once_with(mock_handler_instance)
    mock_logging_info.assert_called_once_with("="*20 + f" Logging started for {app_name} " + "="*20) # Используем переменную

    captured = capsys.readouterr()
    assert "FATAL:" not in captured.out
    assert "FATAL:" not in captured.err


@patch('src.utils.logging.Formatter', autospec=True)
@patch('src.utils.logging.handlers.RotatingFileHandler', autospec=True)
@patch('src.utils.logging.getLogger')
@patch('src.utils.logging.info')
def test_setup_logging_creates_dir(
    mock_logging_info,
    mock_get_logger,
    mock_handler_cls,
    mock_formatter_cls,
    mocker,
    capsys
):
    """Тест: Настройка логирования, когда директория лога не существует."""
    # Значения для теста
    log_file_path = "/another/fake/path/app.log"
    dir_path_str = "/another/fake/path"
    log_max_bytes = 5000
    log_backup_count = 2
    log_level = logging.INFO
    app_name = "AnotherApp"

    # Моки для логгера и хендлера
    mock_root_logger = MagicMock(spec=logging.RootLogger)
    mock_get_logger.return_value = mock_root_logger
    mock_handler_instance = mock_handler_cls.return_value
    mock_formatter_instance = mock_formatter_cls.return_value

    # --- Настройка мока Path внутри теста ---
    mock_path_cls = mocker.patch.object(utils, 'Path', autospec=True)
    mock_log_path_instance = MagicMock(spec=Path)
    mock_log_dir_instance = MagicMock(spec=Path)
    mock_path_cls.return_value = mock_log_path_instance
    mock_log_path_instance.__fspath__.return_value = log_file_path
    mock_log_path_instance.__str__.return_value = log_file_path
    parent_mock = PropertyMock(return_value=mock_log_dir_instance)
    type(mock_log_path_instance).parent = parent_mock
    mock_log_dir_instance.is_dir.return_value = False # Директории нет
    mock_log_dir_instance.__str__.return_value = dir_path_str
    # --- Конец настройки мока Path ---

    # --- Патчим атрибуты config напрямую ---
    mocker.patch.object(config, 'LOG_FILE', log_file_path)
    mocker.patch.object(config, 'LOG_MAX_BYTES', log_max_bytes)
    mocker.patch.object(config, 'LOG_BACKUP_COUNT', log_backup_count)
    mocker.patch.object(config, 'LOG_LEVEL', log_level)
    mocker.patch.object(config, 'APP_NAME', app_name)
    # --- Конец патчинга config ---

    utils.setup_logging()

    # Проверки
    mock_path_cls.assert_called_once_with(log_file_path)
    parent_mock.assert_called_once()
    mock_log_dir_instance.is_dir.assert_called_once()
    mock_log_dir_instance.mkdir.assert_called_once_with(parents=True, exist_ok=True) # Директория создавалась

    mock_formatter_cls.assert_called_once_with('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    mock_handler_cls.assert_called_once_with(
        log_file_path,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
        encoding='utf-8'
    )
    mock_handler_instance.setFormatter.assert_called_once_with(mock_formatter_instance)
    mock_handler_instance.setLevel.assert_called_once_with(log_level)
    mock_get_logger.assert_called_once_with()
    mock_root_logger.setLevel.assert_called_once_with(log_level)
    mock_root_logger.addHandler.assert_called_once_with(mock_handler_instance)
    mock_logging_info.assert_called_once_with("="*20 + f" Logging started for {app_name} " + "="*20)

    captured = capsys.readouterr()
    assert "FATAL:" not in captured.out
    assert "FATAL:" not in captured.err


@patch('src.utils.logging.Formatter', autospec=True)
@patch('src.utils.logging.handlers.RotatingFileHandler', autospec=True)
@patch('src.utils.logging.getLogger')
@patch('src.utils.logging.info')
def test_setup_logging_dir_creation_error(
    mock_logging_info,
    mock_get_logger,
    mock_handler_cls,
    mock_formatter_cls,
    mocker,
    capsys
):
    """Тест: Ошибка при создании директории лога."""
    # Значения для теста
    log_file_path = "/restricted/path/app.log"
    dir_path_str = "/mocked/dir/path"
    error_message = "Permission denied"
    log_max_bytes = 1024
    log_backup_count = 1
    log_level = logging.INFO
    app_name = "ErrorApp"

    # Моки для логгера и хендлера
    mock_root_logger = MagicMock(spec=logging.RootLogger)
    mock_get_logger.return_value = mock_root_logger
    mock_handler_instance = mock_handler_cls.return_value
    mock_formatter_instance = mock_formatter_cls.return_value

    # --- Настройка мока Path внутри теста ---
    mock_path_cls = mocker.patch.object(utils, 'Path', autospec=True)
    mock_log_path_instance = MagicMock(spec=Path)
    mock_log_dir_instance = MagicMock(spec=Path)
    mock_path_cls.return_value = mock_log_path_instance
    mock_log_path_instance.__fspath__.return_value = log_file_path
    mock_log_path_instance.__str__.return_value = log_file_path
    parent_mock = PropertyMock(return_value=mock_log_dir_instance)
    type(mock_log_path_instance).parent = parent_mock
    mock_log_dir_instance.is_dir.return_value = False
    mock_log_dir_instance.mkdir.side_effect = OSError(error_message) # Ошибка при создании
    mock_log_dir_instance.__str__.return_value = dir_path_str
    # --- Конец настройки мока Path ---

    # --- Патчим атрибуты config напрямую ---
    mocker.patch.object(config, 'LOG_FILE', log_file_path)
    mocker.patch.object(config, 'LOG_MAX_BYTES', log_max_bytes)
    mocker.patch.object(config, 'LOG_BACKUP_COUNT', log_backup_count)
    mocker.patch.object(config, 'LOG_LEVEL', log_level)
    mocker.patch.object(config, 'APP_NAME', app_name)
    # --- Конец патчинга config ---

    utils.setup_logging()

    # Проверки
    mock_path_cls.assert_called_once_with(log_file_path)
    parent_mock.assert_called_once()
    mock_log_dir_instance.is_dir.assert_called_once()
    mock_log_dir_instance.mkdir.assert_called_once_with(parents=True, exist_ok=True) # Была попытка создать

    # Проверки, что все остальное было вызвано, т.к. код продолжается после OSError
    mock_formatter_cls.assert_called_once_with('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    mock_handler_cls.assert_called_once_with(
        log_file_path,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
        encoding='utf-8'
    )
    mock_handler_instance.setFormatter.assert_called_once_with(mock_formatter_instance)
    mock_handler_instance.setLevel.assert_called_once_with(log_level)
    mock_get_logger.assert_called_once_with()
    mock_root_logger.setLevel.assert_called_once_with(log_level)
    mock_root_logger.addHandler.assert_called_once_with(mock_handler_instance)
    mock_logging_info.assert_called_once_with("="*20 + f" Logging started for {app_name} " + "="*20)

    # Проверка вывода ошибки в stdout
    captured = capsys.readouterr()
    assert "FATAL: Could not create log directory" in captured.out
    assert dir_path_str in captured.out
    assert error_message in captured.out
    assert "FATAL:" not in captured.err


@patch('src.utils.logging.Formatter', autospec=True)
@patch('src.utils.logging.handlers.RotatingFileHandler', autospec=True)
@patch('src.utils.logging.getLogger')
@patch('src.utils.logging.info')
def test_setup_logging_handler_error(
    mock_logging_info,
    mock_get_logger,
    mock_handler_cls,
    mock_formatter_cls,
    mocker,
    capsys
):
    """Тест: Ошибка при создании RotatingFileHandler."""
    # Значения для теста
    log_file_path = "/write_protected/app.log"
    dir_path_str = "/write_protected"
    error_message = "Cannot open log file"
    log_max_bytes = 1024
    log_backup_count = 3
    log_level = logging.WARNING
    app_name = "HandlerErrorApp" # Не используется в проверках, но патчим для полноты

    # Моки
    mock_formatter_instance = mock_formatter_cls.return_value

    # --- Настройка мока Path внутри теста ---
    mock_path_cls = mocker.patch.object(utils, 'Path', autospec=True)
    mock_log_path_instance = MagicMock(spec=Path)
    mock_log_dir_instance = MagicMock(spec=Path)
    mock_path_cls.return_value = mock_log_path_instance
    mock_log_path_instance.__fspath__.return_value = log_file_path
    mock_log_path_instance.__str__.return_value = log_file_path
    parent_mock = PropertyMock(return_value=mock_log_dir_instance)
    type(mock_log_path_instance).parent = parent_mock
    mock_log_dir_instance.is_dir.return_value = True
    mock_log_dir_instance.__str__.return_value = dir_path_str
    # --- Конец настройки мока Path ---

    # --- Патчим атрибуты config напрямую ---
    mocker.patch.object(config, 'LOG_FILE', log_file_path)
    mocker.patch.object(config, 'LOG_MAX_BYTES', log_max_bytes)
    mocker.patch.object(config, 'LOG_BACKUP_COUNT', log_backup_count)
    mocker.patch.object(config, 'LOG_LEVEL', log_level)
    mocker.patch.object(config, 'APP_NAME', app_name)
    # --- Конец патчинга config ---

    # Получаем инстанс хендлера *до* установки side_effect
    mock_handler_instance = mock_handler_cls.return_value
    mock_handler_cls.side_effect = Exception(error_message) # Ошибка при создании хендлера

    utils.setup_logging()

    # Проверки
    mock_path_cls.assert_called_once_with(log_file_path)
    parent_mock.assert_called_once()
    mock_log_dir_instance.is_dir.assert_called_once()
    mock_log_dir_instance.mkdir.assert_not_called()

    mock_formatter_cls.assert_called_once_with('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Проверяем, что была попытка создать хендлер
    mock_handler_cls.assert_called_once_with(
        log_file_path,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
        encoding='utf-8'
    )

    # Проверяем, что эти вызовы НЕ произошли из-за ошибки выше
    mock_handler_instance.setFormatter.assert_not_called()
    mock_handler_instance.setLevel.assert_not_called()
    mock_get_logger.assert_not_called()
    mock_logging_info.assert_not_called()

    # Проверка вывода ошибки в stderr
    captured = capsys.readouterr()
    assert "FATAL: Could not configure file logging" in captured.err
    assert log_file_path in captured.err
    assert error_message in captured.err
    assert "FATAL:" not in captured.out