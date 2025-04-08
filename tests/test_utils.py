# tests/test_utils.py
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import logging
import logging.handlers # Импортируем handlers для доступа к классу
import sys
import importlib
import stat
import os

# Импортируем тестируемый модуль и зависимости
from src import utils
from src import config as src_config # Импортируем config

try:
    from PIL import Image
except ImportError:
    Image = MagicMock()

# --- Фикстуры для test_utils ---

@pytest.fixture(autouse=True)
def disable_logging():
    logging.disable(logging.CRITICAL + 10)
    yield
    logging.disable(logging.NOTSET)

@pytest.fixture
def mock_pil_image_open():
    with patch('src.utils.Image.open') as mock_open:
        mock_img = MagicMock(spec=Image.Image if Image is not MagicMock else None)
        mock_img.size = (100, 100)
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_img
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_open.return_value = mock_context
        yield mock_open, mock_img

@pytest.fixture
def mock_utils_config():
    with patch('src.utils.config') as mock_config:
        mock_config.DEFAULT_ASPECT_RATIO_THRESHOLD = 1.1
        mock_config.LOG_FILE = "test_app.log"
        mock_config.LOG_MAX_BYTES = 1024 * 5
        mock_config.LOG_BACKUP_COUNT = 3
        mock_config.LOG_LEVEL = logging.DEBUG
        mock_config.APP_NAME = "TestAppUtils"
        yield mock_config

@pytest.fixture
def mock_utils_logger():
    with patch('src.utils.logger') as mock_logger:
        yield mock_logger

@pytest.fixture
def mock_path_in_utils():
    # Упрощенный мок Path, фокусируемся на том, что нужно тестам
    path_mocks = {}

    def get_mock_path(path_arg):
        path_str = str(path_arg)
        # Нормализуем путь для ключа словаря (важно для Windows)
        norm_path_str = os.path.normpath(path_str)
        if norm_path_str not in path_mocks:
            mock = MagicMock(spec=Path)
            mock.name = Path(path_str).name
            mock.suffix = Path(path_str).suffix
            mock.__str__ = MagicMock(return_value=path_str)
            mock.__fspath__ = MagicMock(return_value=path_str)
            mock.is_dir = MagicMock(return_value=False, name=f"is_dir_{norm_path_str}")
            mock.mkdir = MagicMock(name=f"mkdir_{norm_path_str}")
            mock.resolve = MagicMock(return_value=mock, name=f"resolve_{norm_path_str}")

            # Настройка parent
            real_parent = Path(path_str).parent
            if real_parent != Path(path_str):
                mock.parent = get_mock_path(str(real_parent))
            else:
                mock.parent = mock # Корень

            # Настройка truediv (/)
            mock.__truediv__ = lambda self, other: get_mock_path(os.path.join(str(self), str(other)))

            path_mocks[norm_path_str] = mock
        return path_mocks[norm_path_str]

    # Патчим Path в модуле utils
    with patch('src.utils.Path', side_effect=get_mock_path) as MockPathClass:
        yield MockPathClass, get_mock_path, path_mocks

@pytest.fixture
def mock_logging_handlers():
    # ИСПРАВЛЕНО: Патчим конкретный класс RotatingFileHandler, а не весь модуль
    # Указываем полный путь к классу
    with patch('logging.handlers.RotatingFileHandler', spec=logging.handlers.RotatingFileHandler) as MockRotatingFileHandlerClass:
        mock_handler_instance = MagicMock(spec=logging.handlers.RotatingFileHandler)
        mock_handler_instance.setFormatter = MagicMock(name="setFormatterMock")
        mock_handler_instance.setLevel = MagicMock(name="setLevelMock")
        MockRotatingFileHandlerClass.return_value = mock_handler_instance
        yield MockRotatingFileHandlerClass # Возвращаем мок класса

@pytest.fixture
def mock_logging_basic(mock_utils_config):
    mock_root_logger = MagicMock(spec=logging.Logger, name="RootLoggerMock")
    mock_root_logger.setLevel = MagicMock()
    mock_root_logger.addHandler = MagicMock()
    mock_root_logger.info = MagicMock()
    # ИСПРАВЛЕНО: Имитируем handlers как список, чтобы избежать ошибок при добавлении
    mock_root_logger.handlers = []

    mock_utils_logger_instance = MagicMock(spec=logging.Logger, name="UtilsLoggerMock")

    getLogger_calls = [] # Сохраняем вызовы для проверки
    def getLogger_side_effect(name=None):
        getLogger_calls.append(name) # Логируем вызов
        if name == utils.__name__:
            return mock_utils_logger_instance
        elif name is None or name == logging.root.name:
            return mock_root_logger
        else:
            return MagicMock(spec=logging.Logger, name=f"OtherLogger_{name}")

    # Патчим getLogger, Formatter и print
    with patch('logging.getLogger', side_effect=getLogger_side_effect) as mock_getLogger, \
         patch('logging.Formatter', spec=logging.Formatter) as mock_Formatter, \
         patch('builtins.print') as mock_print:

        # Сбрасываем моки перед тестом
        mock_root_logger.reset_mock()
        mock_root_logger.handlers = [] # Сбрасываем handlers
        mock_Formatter.reset_mock()
        mock_getLogger.reset_mock()
        mock_print.reset_mock()
        getLogger_calls.clear() # Очищаем лог вызовов

        yield {
            "getLogger": mock_getLogger,
            "Formatter": mock_Formatter,
            "print": mock_print,
            "root_logger": mock_root_logger,
            "utils_logger": mock_utils_logger_instance,
            "getLogger_calls": getLogger_calls # Возвращаем лог вызовов
        }

# --- Тесты для get_page_number ---
# ... (без изменений) ...
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

# --- Тесты для is_likely_spread ---
# ... (без изменений) ...
def test_is_likely_spread_true(mock_pil_image_open, mock_utils_config):
    mock_open, mock_img = mock_pil_image_open
    mock_utils_config.DEFAULT_ASPECT_RATIO_THRESHOLD = 1.1
    mock_img.size = (1200, 1000) # Ratio 1.2 > 1.1
    assert utils.is_likely_spread("dummy_path.jpg") is True
    mock_open.assert_called_once_with("dummy_path.jpg")

def test_is_likely_spread_false_ratio(mock_pil_image_open, mock_utils_config):
    mock_open, mock_img = mock_pil_image_open
    mock_utils_config.DEFAULT_ASPECT_RATIO_THRESHOLD = 1.1
    mock_img.size = (1000, 1000) # Ratio 1.0 <= 1.1
    assert utils.is_likely_spread("dummy_path.jpg") is False

def test_is_likely_spread_false_zero_height(mock_pil_image_open, mock_utils_config, mock_utils_logger):
    mock_open, mock_img = mock_pil_image_open
    mock_utils_config.DEFAULT_ASPECT_RATIO_THRESHOLD = 1.1
    mock_img.size = (1000, 0)
    assert utils.is_likely_spread("dummy_path.jpg") is False
    mock_utils_logger.warning.assert_called_with("Image has zero height: dummy_path.jpg")

def test_is_likely_spread_exception_pil(mock_pil_image_open, mock_utils_logger, mock_utils_config):
    mock_open, _ = mock_pil_image_open
    error_message = "PIL Error"
    mock_open.side_effect = Exception(error_message)
    assert utils.is_likely_spread("dummy_path.jpg") is False
    mock_utils_logger.warning.assert_called_once_with(
        f"Could not check aspect ratio for dummy_path.jpg: {error_message}",
        exc_info=True
    )

def test_is_likely_spread_file_not_found(mock_pil_image_open, mock_utils_logger, mock_utils_config):
    mock_open, _ = mock_pil_image_open
    error_message = "File not found"
    mock_open.side_effect = FileNotFoundError(error_message)
    assert utils.is_likely_spread("non_existent.jpg") is False
    mock_utils_logger.error.assert_called_once_with("Image file not found for aspect ratio check: non_existent.jpg")


# --- Тесты для resource_path ---
@patch('sys.frozen', True, create=True)
@patch('sys._MEIPASS', '/path/to/_MEIPASS', create=True)
def test_resource_path_pyinstaller(mock_path_in_utils):
    MockPathClass, get_mock_path, path_mocks = mock_path_in_utils
    relative = os.path.join("assets", "icon.png")
    expected_path_str = os.path.join(sys._MEIPASS, relative)

    result = utils.resource_path(relative)

    assert os.path.normpath(result) == os.path.normpath(expected_path_str)
    # ИСПРАВЛЕНО: Проверяем вызов Path с _MEIPASS
    MockPathClass.assert_any_call(sys._MEIPASS)
    # ИСПРАВЛЕНО: Проверяем вызов __truediv__ на моке пути _MEIPASS
    mock_meipass_path = get_mock_path(sys._MEIPASS)
    mock_meipass_path.__truediv__.assert_called_with(relative)


@patch('sys.frozen', False, create=True)
@patch('sys._MEIPASS', None, create=True)
# ИСПРАВЛЕНО: Патчим __file__ более надежно
@patch('src.utils.__file__', os.path.normpath('/fake/project/src/utils.py'))
def test_resource_path_script(mock_path_in_utils):
    MockPathClass, get_mock_path, path_mocks = mock_path_in_utils
    relative = os.path.join("assets", "icon.png")
    # Ожидаемый путь: корень проекта + relative
    # Корень проекта вычисляется как Path(__file__).parent.parent
    expected_project_root = os.path.normpath('/fake/project')
    expected_path_str = os.path.join(expected_project_root, relative)

    # ИСПРАВЛЕНО: Настраиваем мок Path, чтобы он правильно вычислял parent.parent
    # Фикстура mock_path_in_utils уже должна это делать через рекурсивный вызов get_mock_path
    # Убедимся, что мок __file__ правильно обрабатывается
    mock_file_path = get_mock_path(utils.__file__)
    mock_src_dir = get_mock_path(os.path.dirname(utils.__file__))
    mock_base_path = get_mock_path(os.path.dirname(os.path.dirname(utils.__file__)))

    # Явно связываем моки родителей (на всякий случай)
    mock_file_path.parent = mock_src_dir
    mock_src_dir.parent = mock_base_path

    result = utils.resource_path(relative)

    assert os.path.normpath(result) == os.path.normpath(expected_path_str)
    # Проверяем вызовы Path
    MockPathClass.assert_any_call(utils.__file__)
    # Проверяем вызов resolve на моке __file__
    mock_file_path.resolve.assert_called_once()
    # Проверяем вызов __truediv__ на моке базового пути
    mock_base_path.__truediv__.assert_called_with(relative)


# --- Тесты для setup_logging ---

def test_setup_logging_success(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    MockPath, get_mock_path, path_mocks = mock_path_in_utils
    # ИСПРАВЛЕНО: Получаем мок класса из фикстуры
    MockRotatingFileHandlerClass = mock_logging_handlers
    mock_log_basics = mock_logging_basic

    mock_log_dir = get_mock_path(Path(mock_utils_config.LOG_FILE).parent)
    mock_log_dir.is_dir.return_value = True

    # Сброс перед вызовом
    mock_log_basics["root_logger"].reset_mock()
    mock_log_basics["root_logger"].handlers = [] # Важно сбросить список
    MockRotatingFileHandlerClass.reset_mock()
    mock_log_basics["Formatter"].reset_mock()
    mock_log_basics["getLogger"].reset_mock()
    mock_log_basics["getLogger_calls"].clear()

    utils.setup_logging()

    mock_log_dir.mkdir.assert_not_called()
    mock_log_basics["Formatter"].assert_called_once_with('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter_instance = mock_log_basics["Formatter"].return_value
    MockRotatingFileHandlerClass.assert_called_once_with(
        mock_utils_config.LOG_FILE,
        maxBytes=mock_utils_config.LOG_MAX_BYTES,
        backupCount=mock_utils_config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    mock_handler_instance = MockRotatingFileHandlerClass.return_value
    mock_handler_instance.setFormatter.assert_called_once_with(formatter_instance)
    mock_handler_instance.setLevel.assert_called_once_with(mock_utils_config.LOG_LEVEL)

    # ИСПРАВЛЕНО: Проверяем, что getLogger вызывался для root
    assert None in mock_log_basics["getLogger_calls"] or logging.root.name in mock_log_basics["getLogger_calls"]
    root_logger_instance = mock_log_basics["root_logger"]
    root_logger_instance.setLevel.assert_called_once_with(mock_utils_config.LOG_LEVEL)
    # ИСПРАВЛЕНО: Проверяем addHandler
    root_logger_instance.addHandler.assert_called_once_with(mock_handler_instance)

    root_logger_instance.info.assert_called_once_with(
        "="*20 + f" Logging started for {mock_utils_config.APP_NAME} " + "="*20
    )
    mock_log_basics["print"].assert_not_called()


def test_setup_logging_creates_dir(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    MockPath, get_mock_path, path_mocks = mock_path_in_utils
    MockRotatingFileHandlerClass = mock_logging_handlers
    mock_log_basics = mock_logging_basic

    mock_log_dir = get_mock_path(Path(mock_utils_config.LOG_FILE).parent)
    mock_log_dir.is_dir.return_value = False # Директория НЕ существует

    # Сброс
    mock_log_dir.mkdir.reset_mock()
    mock_log_basics["root_logger"].reset_mock()
    mock_log_basics["root_logger"].handlers = []

    utils.setup_logging()

    mock_log_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    MockRotatingFileHandlerClass.assert_called_once()
    mock_log_basics["root_logger"].addHandler.assert_called_once()
    mock_log_basics["root_logger"].info.assert_called_once()
    mock_log_basics["print"].assert_not_called()


def test_setup_logging_dir_creation_error(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    MockPath, get_mock_path, path_mocks = mock_path_in_utils
    MockRotatingFileHandlerClass = mock_logging_handlers
    mock_log_basics = mock_logging_basic

    mock_log_dir = get_mock_path(Path(mock_utils_config.LOG_FILE).parent)
    mock_log_dir.is_dir.return_value = False
    error_message = "Permission denied"
    mock_log_dir.mkdir.side_effect = OSError(error_message)

    # Сброс
    mock_log_dir.mkdir.reset_mock()
    MockRotatingFileHandlerClass.reset_mock()
    mock_log_basics["print"].reset_mock()
    mock_log_basics["root_logger"].reset_mock()
    mock_log_basics["root_logger"].handlers = []

    utils.setup_logging()

    mock_log_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_log_basics["print"].assert_called_once_with(
        f"FATAL: Could not create log directory {mock_log_dir}: {error_message}"
    )
    MockRotatingFileHandlerClass.assert_not_called()
    mock_log_basics["root_logger"].addHandler.assert_not_called()
    mock_log_basics["root_logger"].info.assert_not_called()


def test_setup_logging_handler_error(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    MockPath, get_mock_path, path_mocks = mock_path_in_utils
    MockRotatingFileHandlerClass = mock_logging_handlers
    mock_log_basics = mock_logging_basic

    mock_log_dir = get_mock_path(Path(mock_utils_config.LOG_FILE).parent)
    mock_log_dir.is_dir.return_value = True
    error_message = "Cannot open file"
    MockRotatingFileHandlerClass.side_effect = Exception(error_message)

    # Сброс
    MockRotatingFileHandlerClass.reset_mock()
    MockRotatingFileHandlerClass.side_effect = Exception(error_message) # Восстанавливаем side_effect
    mock_log_basics["print"].reset_mock()
    mock_log_basics["root_logger"].reset_mock()
    mock_log_basics["root_logger"].handlers = []
    mock_log_basics["getLogger"].reset_mock()
    mock_log_basics["getLogger_calls"].clear()

    utils.setup_logging()

    MockRotatingFileHandlerClass.assert_called_once() # Попытка создания была
    mock_log_basics["print"].assert_called_once_with(
        f"FATAL: Could not configure file logging to {mock_utils_config.LOG_FILE}: {error_message}",
        file=sys.stderr
    )
    # getLogger для root вызывается до ошибки
    assert None in mock_log_basics["getLogger_calls"] or logging.root.name in mock_log_basics["getLogger_calls"]
    mock_log_basics["root_logger"].addHandler.assert_not_called()
    mock_log_basics["root_logger"].info.assert_not_called()