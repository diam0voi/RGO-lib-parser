# tests/test_utils.py
import pytest
from unittest.mock import patch, MagicMock, call, ANY
from pathlib import Path
import logging
import logging.handlers
import sys
# importlib больше не нужен
# import importlib
import stat
import os
import re

# Импортируем тестируемый модуль и зависимости
from src import utils
from src import config as src_config

try:
    from PIL import Image
except ImportError:
    Image = MagicMock()

# --- Обновленные фикстуры ---

@pytest.fixture
def mock_pil_image_open():
    with patch('src.utils.Image.open') as mock_open:
        mock_img = MagicMock(spec=Image.Image if 'Image' in globals() and hasattr(Image, 'Image') else object)
        mock_img.size = (100, 100)
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_img
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_open.return_value = mock_context
        yield mock_open, mock_img

@pytest.fixture
def mock_utils_config():
    with patch.multiple(src_config,
                        DEFAULT_ASPECT_RATIO_THRESHOLD=1.1,
                        LOG_FILE="test_app.log",
                        LOG_MAX_BYTES=1024 * 5,
                        LOG_BACKUP_COUNT=3,
                        LOG_LEVEL=logging.DEBUG,
                        APP_NAME="TestAppUtils",
                        create=True):
        yield src_config

@pytest.fixture
def mock_utils_logger():
    # Снова патчим getLogger, но правильно
    original_getLogger = logging.getLogger # Сохраняем оригинал
    mock_logger_instance = MagicMock(spec=logging.Logger)
    # Патчим getLogger глобально
    with patch('logging.getLogger') as mock_getLogger:
        def getLogger_side_effect(name=None):
            logger_name = name if name is not None else logging.root.name
            if logger_name == utils.__name__: # Имя логгера модуля utils
                return mock_logger_instance # Возвращаем наш мок
            else:
                # Для всех остальных вызываем ОРИГИНАЛЬНЫЙ getLogger
                return original_getLogger(name)
        mock_getLogger.side_effect = getLogger_side_effect
        yield mock_logger_instance # Возвращаем мок логгера 'src.utils'

@pytest.fixture
def mock_path_in_utils():
    path_mocks = {}
    real_Path = Path
    def get_mock_path(path_arg):
        path_str = os.path.normpath(str(path_arg))
        if path_str not in path_mocks:
            mock = MagicMock(spec=real_Path)
            mock.name = real_Path(path_str).name
            mock.suffix = real_Path(path_str).suffix
            mock.__str__ = MagicMock(return_value=path_str)
            mock.__fspath__ = MagicMock(return_value=path_str)
            mock.is_dir = MagicMock(return_value=False, name=f"is_dir_{path_str}")
            mock.mkdir = MagicMock(name=f"mkdir_{path_str}")
            mock.resolve = MagicMock(return_value=mock, name=f"resolve_{path_str}")
            real_parent = real_Path(path_str).parent
            if str(real_parent) != path_str:
                mock.parent = get_mock_path(str(real_parent))
            else:
                mock.parent = mock
            def truediv_side_effect(self, other):
                return get_mock_path(os.path.join(str(self), str(other)))
            mock.__truediv__ = truediv_side_effect
            path_mocks[path_str] = mock
        return path_mocks[path_str]
    with patch('src.utils.Path', side_effect=get_mock_path) as MockPathClass:
         MockPathClass.path_mocks = path_mocks
         yield MockPathClass, get_mock_path, path_mocks

@pytest.fixture
def mock_logging_handlers():
     # УБРАЛИ autospec=True
    with patch('logging.handlers.RotatingFileHandler') as MockRotatingFileHandlerClass:
        # Создаем мок экземпляра с нужными методами
        mock_handler_instance = MagicMock(spec=logging.handlers.RotatingFileHandler)
        mock_handler_instance.setFormatter = MagicMock(name="setFormatterMock")
        mock_handler_instance.setLevel = MagicMock(name="setLevelMock")
        MockRotatingFileHandlerClass.return_value = mock_handler_instance
        yield MockRotatingFileHandlerClass

@pytest.fixture
def mock_logging_basic(mock_utils_config):
    config_obj = mock_utils_config
    original_getLogger = logging.getLogger # Сохраняем оригинал
    mock_root_logger = MagicMock(spec=logging.Logger, name="RootLoggerMock")
    mock_root_logger.setLevel = MagicMock()
    mock_root_logger.addHandler = MagicMock()
    mock_root_logger.info = MagicMock()
    mock_root_logger.handlers = []
    getLogger_calls = {}
    def getLogger_side_effect(name=None):
        logger_name = name if name is not None else logging.root.name
        getLogger_calls[logger_name] = getLogger_calls.get(logger_name, 0) + 1
        if logger_name == logging.root.name:
            return mock_root_logger # Наш мок для root
        else:
            # Для всех остальных - оригинал
            return original_getLogger(name)
    # Патчим getLogger глобально
    with patch('logging.getLogger', side_effect=getLogger_side_effect) as mock_getLogger, \
         patch('logging.Formatter', spec=logging.Formatter) as mock_Formatter, \
         patch('builtins.print') as mock_print:
        mock_root_logger.reset_mock()
        mock_root_logger.handlers = []
        mock_Formatter.reset_mock()
        mock_getLogger.reset_mock()
        mock_print.reset_mock()
        getLogger_calls.clear()
        yield {
            "getLogger": mock_getLogger,
            "Formatter": mock_Formatter,
            "print": mock_print,
            "root_logger": mock_root_logger,
            "getLogger_calls": getLogger_calls,
        }


# --- Тесты для get_page_number (без изменений) ---
@pytest.mark.parametrize("filename, expected", [
    ("page_001.jpg", 1),
    ("spread_123-456.png", 123),
    ("005_image.jpeg", 5),
    ("img_99.gif", 99),
    ("123.tiff", 123),
    ("cover.jpg", -1),
    ("image.png", -1),
    ("", -1),
    (None, -1),
    ("no_number_here", -1),
])
def test_get_page_number(filename, expected):
    assert utils.get_page_number(filename) == expected

# --- Тесты для is_likely_spread (УБРАН reload, используется mock_utils_logger с патчем getLogger) ---

def test_is_likely_spread_true_with_threshold(mock_pil_image_open, mock_utils_config, mock_utils_logger):
    mock_open, mock_img = mock_pil_image_open
    mock_img.size = (1200, 1000)
    custom_threshold = 1.15
    # Вызываем функцию ПОСЛЕ того, как фикстуры применили патчи
    assert utils.is_likely_spread("dummy_path.jpg", threshold=custom_threshold) is True
    mock_open.assert_called_once_with("dummy_path.jpg")
    # mock_utils_logger теперь должен ловить вызовы
    mock_utils_logger.debug.assert_called_once()
    call_args, _ = mock_utils_logger.debug.call_args
    log_message = call_args[0]
    match = re.search(r"Threshold: ([\d.]+)", log_message)
    assert match is not None
    assert float(match.group(1)) == pytest.approx(custom_threshold)

def test_is_likely_spread_uses_default_threshold(mock_pil_image_open, mock_utils_config, mock_utils_logger):
    mock_open, mock_img = mock_pil_image_open
    mock_img.size = (1200, 1000)
    default_threshold = mock_utils_config.DEFAULT_ASPECT_RATIO_THRESHOLD
    assert utils.is_likely_spread("dummy_path_default.jpg") is True
    mock_open.assert_called_once_with("dummy_path_default.jpg")
    mock_utils_logger.debug.assert_called_once()
    call_args, _ = mock_utils_logger.debug.call_args
    log_message = call_args[0]
    assert log_message.startswith("Image: dummy_path_default.jpg, Size: 1200x1000")
    assert "Ratio: 1.20" in log_message
    match = re.search(r"Threshold: ([\d.]+)", log_message)
    assert match is not None
    assert float(match.group(1)) == pytest.approx(default_threshold)

def test_is_likely_spread_false_ratio(mock_pil_image_open, mock_utils_config, mock_utils_logger):
    mock_open, mock_img = mock_pil_image_open
    mock_img.size = (1000, 1000)
    assert utils.is_likely_spread("dummy_path.jpg") is False
    mock_utils_logger.debug.assert_called_once()
    call_args, _ = mock_utils_logger.debug.call_args
    log_message = call_args[0]
    assert "Ratio: 1.00" in log_message
    match = re.search(r"Threshold: ([\d.]+)", log_message)
    assert match is not None
    assert float(match.group(1)) == pytest.approx(mock_utils_config.DEFAULT_ASPECT_RATIO_THRESHOLD)

def test_is_likely_spread_false_zero_height(mock_pil_image_open, mock_utils_config, mock_utils_logger):
    mock_open, mock_img = mock_pil_image_open
    mock_img.size = (1000, 0)
    assert utils.is_likely_spread("dummy_zero_h.jpg") is False
    mock_utils_logger.warning.assert_called_once_with("Image has zero height: dummy_zero_h.jpg")
    mock_utils_logger.debug.assert_not_called()

def test_is_likely_spread_exception_pil(mock_pil_image_open, mock_utils_logger, mock_utils_config):
    mock_open, _ = mock_pil_image_open
    error_message = "PIL Error"
    mock_open.side_effect = Exception(error_message)
    assert utils.is_likely_spread("dummy_pil_error.jpg") is False
    mock_utils_logger.warning.assert_called_once_with(
        f"Could not check aspect ratio for dummy_pil_error.jpg: {error_message}",
        exc_info=True
    )
    mock_utils_logger.debug.assert_not_called()
    mock_utils_logger.error.assert_not_called()

def test_is_likely_spread_file_not_found(mock_pil_image_open, mock_utils_logger, mock_utils_config):
    mock_open, _ = mock_pil_image_open
    error_message = "File not found"
    mock_open.side_effect = FileNotFoundError(error_message)
    assert utils.is_likely_spread("non_existent.jpg") is False
    mock_utils_logger.error.assert_called_once_with(
        "Image file not found for aspect ratio check: non_existent.jpg"
    )
    mock_utils_logger.debug.assert_not_called()
    mock_utils_logger.warning.assert_not_called()


# --- Тесты для resource_path (УБРАН reload) ---

# Патчи применяются декораторами ДО входа в тест и ДО вызова функции
@patch('sys.frozen', True, create=True)
@patch('sys._MEIPASS', '/path/to/_MEIPASS', create=True)
# mock_utils_logger теперь тоже работает через getLogger
def test_resource_path_pyinstaller(mock_path_in_utils, mock_utils_logger):
    MockPathClass, get_mock_path, path_mocks = mock_path_in_utils
    relative = os.path.join("assets", "icon.png")
    expected_meipass_path_str = os.path.normpath('/path/to/_MEIPASS')
    expected_final_path_str = os.path.normpath(os.path.join(expected_meipass_path_str, relative))

    # УБРАЛИ reload
    result = utils.resource_path(relative) # Вызываем функцию

    assert os.path.normpath(result) == expected_final_path_str
    MockPathClass.assert_any_call(expected_meipass_path_str)
    mock_meipass_path = get_mock_path(expected_meipass_path_str)
    mock_meipass_path.__truediv__.assert_called_once_with(relative)
    # Проверяем логи через mock_utils_logger
    mock_utils_logger.debug.assert_any_call(f"Running in PyInstaller bundle, MEIPASS: {mock_meipass_path}")
    mock_final_path = get_mock_path(expected_final_path_str)
    mock_utils_logger.debug.assert_any_call(f"Resolved resource path for '{relative}': '{mock_final_path}'")


@patch('sys.frozen', False, create=True)
@patch('src.utils.__file__', os.path.normpath('/fake/project/src/utils.py'))
def test_resource_path_script(mock_path_in_utils, mock_utils_logger):
    MockPathClass, get_mock_path, path_mocks = mock_path_in_utils
    relative = os.path.join("assets", "icon.png")
    fake_utils_file = os.path.normpath('/fake/project/src/utils.py')
    expected_project_root = os.path.normpath('/fake/project')
    expected_final_path_str = os.path.normpath(os.path.join(expected_project_root, relative))

    if hasattr(sys, '_MEIPASS'):
        del sys._MEIPASS # Убеждаемся, что атрибута нет

    # УБРАЛИ reload
    result = utils.resource_path(relative) # Вызываем функцию

    assert os.path.normpath(result) == expected_final_path_str
    MockPathClass.assert_any_call(fake_utils_file)
    mock_file_path = get_mock_path(fake_utils_file)
    mock_file_path.resolve.assert_called_once()
    assert mock_file_path.parent is not None
    assert mock_file_path.parent.parent is not None
    mock_base_path = get_mock_path(expected_project_root)
    mock_base_path.__truediv__.assert_called_once_with(relative)
    # Проверяем логи через mock_utils_logger
    mock_utils_logger.debug.assert_any_call(f"Running as script, calculated project root: {mock_base_path}")
    mock_final_path = get_mock_path(expected_final_path_str)
    mock_utils_logger.debug.assert_any_call(f"Resolved resource path for '{relative}': '{mock_final_path}'")


# --- Тесты для setup_logging (УБРАН reload) ---

# Фикстуры mock_logging_basic и mock_logging_handlers применяют патчи ДО вызова функции
def test_setup_logging_success(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    MockPath, get_mock_path, path_mocks = mock_path_in_utils
    MockRotatingFileHandlerClass = mock_logging_handlers
    mock_log_basics = mock_logging_basic
    config_obj = mock_utils_config

    log_file_path_str = config_obj.LOG_FILE
    mock_log_file = get_mock_path(log_file_path_str)
    mock_log_dir = mock_log_file.parent
    mock_log_dir.is_dir.return_value = True

    root_logger_instance = mock_log_basics["root_logger"]
    mock_print = mock_log_basics["print"]
    mock_formatter = mock_log_basics["Formatter"]

    # УБРАЛИ reload
    utils.setup_logging() # Вызываем функцию

    # Проверки остаются такими же
    mock_log_dir.is_dir.assert_called_once()
    mock_log_dir.mkdir.assert_not_called()
    mock_formatter.assert_called_once_with('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter_instance = mock_formatter.return_value
    MockRotatingFileHandlerClass.assert_called_once_with(
        log_file_path_str,
        maxBytes=config_obj.LOG_MAX_BYTES,
        backupCount=config_obj.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    mock_handler_instance = MockRotatingFileHandlerClass.return_value
    mock_handler_instance.setFormatter.assert_called_once_with(formatter_instance)
    mock_handler_instance.setLevel.assert_called_once_with(config_obj.LOG_LEVEL)
    assert logging.root.name in mock_log_basics["getLogger_calls"]
    root_logger_instance.setLevel.assert_called_once_with(config_obj.LOG_LEVEL)
    root_logger_instance.addHandler.assert_called_once_with(mock_handler_instance)
    root_logger_instance.info.assert_called_once_with(
        "="*20 + f" Logging started for {config_obj.APP_NAME} " + "="*20
    )
    mock_print.assert_not_called()


def test_setup_logging_creates_dir(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    MockPath, get_mock_path, path_mocks = mock_path_in_utils
    MockRotatingFileHandlerClass = mock_logging_handlers
    mock_log_basics = mock_logging_basic
    config_obj = mock_utils_config

    log_file_path_str = config_obj.LOG_FILE
    mock_log_file = get_mock_path(log_file_path_str)
    mock_log_dir = mock_log_file.parent
    mock_log_dir.is_dir.return_value = False

    root_logger_instance = mock_log_basics["root_logger"]
    mock_print = mock_log_basics["print"]
    mock_formatter = mock_log_basics["Formatter"]

    # УБРАЛИ reload
    utils.setup_logging() # Вызываем функцию

    # Проверки остаются такими же
    mock_log_dir.is_dir.assert_called_once()
    mock_log_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_formatter.assert_called_once_with('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter_instance = mock_formatter.return_value
    MockRotatingFileHandlerClass.assert_called_once_with(
        log_file_path_str,
        maxBytes=config_obj.LOG_MAX_BYTES,
        backupCount=config_obj.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    mock_handler_instance = MockRotatingFileHandlerClass.return_value
    mock_handler_instance.setFormatter.assert_called_once_with(formatter_instance)
    mock_handler_instance.setLevel.assert_called_once_with(config_obj.LOG_LEVEL)
    assert logging.root.name in mock_log_basics["getLogger_calls"]
    root_logger_instance.setLevel.assert_called_once_with(config_obj.LOG_LEVEL)
    root_logger_instance.addHandler.assert_called_once_with(mock_handler_instance)
    root_logger_instance.info.assert_called_once_with(
        "="*20 + f" Logging started for {config_obj.APP_NAME} " + "="*20
    )
    mock_print.assert_not_called()


def test_setup_logging_dir_creation_error(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    MockPath, get_mock_path, path_mocks = mock_path_in_utils
    MockRotatingFileHandlerClass = mock_logging_handlers
    mock_log_basics = mock_logging_basic
    config_obj = mock_utils_config

    log_file_path_str = config_obj.LOG_FILE
    mock_log_file = get_mock_path(log_file_path_str)
    mock_log_dir = mock_log_file.parent
    mock_log_dir.is_dir.return_value = False
    error_message = "Permission denied"
    mock_log_dir.mkdir.side_effect = OSError(error_message)

    root_logger_instance = mock_log_basics["root_logger"]
    mock_print = mock_log_basics["print"]
    mock_formatter = mock_log_basics["Formatter"]

    mock_log_dir.mkdir.reset_mock()
    mock_log_dir.mkdir.side_effect = OSError(error_message)

    # УБРАЛИ reload
    utils.setup_logging() # Вызываем функцию

    # Проверки остаются такими же
    mock_log_dir.is_dir.assert_called_once()
    mock_log_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_formatter.assert_not_called()
    mock_print.assert_called_once_with(
        f"FATAL: Could not create log directory {mock_log_dir}: {error_message}"
    )
    MockRotatingFileHandlerClass.assert_not_called()
    # Проверяем, что getLogger не вызывался для root, так как вышли раньше
    assert logging.root.name not in mock_log_basics["getLogger_calls"]
    root_logger_instance.setLevel.assert_not_called()
    root_logger_instance.addHandler.assert_not_called()
    root_logger_instance.info.assert_not_called()


def test_setup_logging_handler_error(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    MockPath, get_mock_path, path_mocks = mock_path_in_utils
    MockRotatingFileHandlerClass = mock_logging_handlers
    mock_log_basics = mock_logging_basic
    config_obj = mock_utils_config

    log_file_path_str = config_obj.LOG_FILE
    mock_log_file = get_mock_path(log_file_path_str)
    mock_log_dir = mock_log_file.parent
    mock_log_dir.is_dir.return_value = True

    error_message = "Cannot open log file for writing"
    MockRotatingFileHandlerClass.side_effect = Exception(error_message)

    root_logger_instance = mock_log_basics["root_logger"]
    mock_print = mock_log_basics["print"]
    mock_formatter = mock_log_basics["Formatter"]

    MockRotatingFileHandlerClass.reset_mock()
    MockRotatingFileHandlerClass.side_effect = Exception(error_message)

    # УБРАЛИ reload
    utils.setup_logging() # Вызываем функцию

    # Проверки остаются такими же
    mock_log_dir.is_dir.assert_called_once()
    mock_log_dir.mkdir.assert_not_called()
    mock_formatter.assert_called_once_with('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    MockRotatingFileHandlerClass.assert_called_once_with(
        log_file_path_str,
        maxBytes=config_obj.LOG_MAX_BYTES,
        backupCount=config_obj.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    mock_print.assert_called_once_with(
        f"FATAL: Could not configure file logging to {log_file_path_str}: {error_message}",
        file=sys.stderr
    )
    # Проверяем, что getLogger не вызывался для root, так как вышли раньше
    assert logging.root.name not in mock_log_basics["getLogger_calls"]
    root_logger_instance.setLevel.assert_not_called()
    root_logger_instance.addHandler.assert_not_called()
    root_logger_instance.info.assert_not_called()
