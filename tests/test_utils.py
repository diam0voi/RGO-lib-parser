# tests/test_utils.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import logging
import sys
import importlib
import stat # <-- Импорт был здесь, все ок
import os # <-- Добавлен импорт os для os.PathLike

# Импортируем тестируемый модуль и зависимости
from src import utils
try:
    from PIL import Image
except ImportError:
    Image = MagicMock()

# --- Фикстуры для test_utils ---

@pytest.fixture(autouse=True)
def disable_logging():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)

@pytest.fixture
def mock_pil_image_open():
    with patch('src.utils.Image.open') as mock_open:
        mock_img = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_img
        mock_open.return_value = mock_context
        yield mock_open, mock_img

@pytest.fixture
def mock_utils_config():
    # ДОБАВЛЕНО: Мокаем атрибуты, используемые в setup_logging
    with patch('src.utils.config') as mock_config:
        mock_config.DEFAULT_ASPECT_RATIO_THRESHOLD = 1.1
        mock_config.LOG_FILE = "test_app.log"
        mock_config.LOG_MAX_BYTES = 1024
        mock_config.LOG_BACKUP_COUNT = 1
        mock_config.LOG_LEVEL = logging.DEBUG
        mock_config.APP_NAME = "TestApp"
        yield mock_config

@pytest.fixture
def mock_utils_logger():
    with patch('src.utils.logger') as mock_logger:
        yield mock_logger

# ДОБАВЛЕНО: Фикстура для мока Path в setup_logging
@pytest.fixture
def mock_path_in_utils():
    with patch('src.utils.Path') as MockPath:
        # Мок для Path(log_file).parent
        mock_log_dir = MagicMock(spec=Path)
        mock_log_dir.is_dir.return_value = True # По умолчанию директория существует

        # Мок для Path(log_file)
        mock_log_file_path = MagicMock(spec=Path)
        mock_log_file_path.parent = mock_log_dir

        # Мок для Path(__file__)
        mock_file_path = MagicMock(spec=Path)
        mock_file_path.resolve.return_value = mock_file_path
        mock_file_path.parent = MagicMock(spec=Path) # src_dir
        mock_file_path.parent.parent = MagicMock(spec=Path) # base_path

        def path_side_effect(arg):
            if arg == mock_utils_config.LOG_FILE:
                return mock_log_file_path
            elif arg == utils.__file__: # Сравниваем с реальным путем или моком __file__
                 return mock_file_path
            else:
                # Возвращаем стандартный Path для других случаев (например, в resource_path)
                # или специфичный мок, если нужно
                return Path(arg) # Используем настоящий Path для остальных

        MockPath.side_effect = path_side_effect
        # Также мокаем статические методы, если они используются напрямую
        MockPath.is_dir = Path.is_dir
        MockPath.mkdir = MagicMock()

        # Возвращаем основной мок класса Path и специфичные моки для директорий/файлов
        yield MockPath, mock_log_dir, mock_log_file_path


# ДОБАВЛЕНО: Фикстура для мока logging.handlers
@pytest.fixture
def mock_logging_handlers():
    with patch('src.utils.logging.handlers') as mock_handlers:
        mock_handlers.RotatingFileHandler = MagicMock()
        yield mock_handlers

# ДОБАВЛЕНО: Фикстура для мока logging базовых функций
@pytest.fixture
def mock_logging_basic():
     # Используем MagicMock для getLogger, чтобы он возвращал мок-логгер
    mock_logger_instance = MagicMock(spec=logging.Logger)
    # Настраиваем setLevel и addHandler, так как они вызываются
    mock_logger_instance.setLevel = MagicMock()
    mock_logger_instance.addHandler = MagicMock()

    with patch('src.utils.logging.getLogger', return_value=mock_logger_instance) as mock_getLogger, \
         patch('src.utils.logging.Formatter') as mock_Formatter, \
         patch('src.utils.logging.info') as mock_info, \
         patch('src.utils.logging.basicConfig') as mock_basicConfig, \
         patch('src.utils.print') as mock_print: # Мокаем print для отлова фатальных ошибок
        # Возвращаем словарь моков для удобства доступа в тестах
        yield {
            "getLogger": mock_getLogger,
            "Formatter": mock_Formatter,
            "info": mock_info,
            "basicConfig": mock_basicConfig,
            "print": mock_print,
            "logger_instance": mock_logger_instance # Возвращаем инстанс логгера
        }


# --- Тесты для get_page_number ---

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

def test_is_likely_spread_true(mock_pil_image_open, mock_utils_config):
    mock_open, mock_img = mock_pil_image_open
    mock_utils_config.DEFAULT_ASPECT_RATIO_THRESHOLD = 1.1
    mock_img.size = (1200, 1000) # Ratio 1.2 > 1.1
    assert utils.is_likely_spread("dummy_path.jpg") is True
    mock_open.assert_called_once_with("dummy_path.jpg")

def test_is_likely_spread_false_ratio(mock_pil_image_open, mock_utils_config):
    mock_open, mock_img = mock_pil_image_open
    mock_utils_config.DEFAULT_ASPECT_RATIO_THRESHOLD = 1.1
    mock_img.size = (1000, 1000) # Ratio 1.0 < 1.1
    assert utils.is_likely_spread("dummy_path.jpg") is False

def test_is_likely_spread_false_zero_height(mock_pil_image_open, mock_utils_config, mock_utils_logger):
    # ДОБАВЛЕНО: mock_utils_logger для проверки warning
    mock_open, mock_img = mock_pil_image_open
    mock_utils_config.DEFAULT_ASPECT_RATIO_THRESHOLD = 1.1
    mock_img.size = (1000, 0)
    assert utils.is_likely_spread("dummy_path.jpg") is False
    # ДОБАВЛЕНО: Проверка вызова warning
    mock_utils_logger.warning.assert_called_with("Image has zero height: dummy_path.jpg")

def test_is_likely_spread_exception(mock_pil_image_open, mock_utils_logger, mock_utils_config):
    mock_open, _ = mock_pil_image_open
    mock_open.side_effect = Exception("PIL Error")
    assert utils.is_likely_spread("dummy_path.jpg") is False
    mock_utils_logger.warning.assert_called_once_with(
        "Could not check aspect ratio for dummy_path.jpg: PIL Error", exc_info=True
    )

def test_is_likely_spread_file_not_found(mock_pil_image_open, mock_utils_logger, mock_utils_config):
    mock_open, _ = mock_pil_image_open
    mock_open.side_effect = FileNotFoundError("File not found")
    assert utils.is_likely_spread("non_existent.jpg") is False
    mock_utils_logger.error.assert_called_once_with("Image file not found for aspect ratio check: non_existent.jpg")

# --- Тесты для resource_path ---

# ИСПРАВЛЕНО: Убираем create=True, т.к. _MEIPASS может не существовать
@patch('sys.frozen', True, create=True) # Имитируем запуск из PyInstaller
@patch('sys._MEIPASS', new_callable=MagicMock)
def test_resource_path_pyinstaller(mock_meipass):
    meipass_path_str = '/path/to/_MEIPASS'
    # ИСПРАВЛЕНО: Настраиваем мок как Path-совместимый объект
    mock_meipass.__str__.return_value = meipass_path_str
    mock_meipass.__fspath__.return_value = meipass_path_str # Для Path()

    # Перезагрузка utils не нужна, т.к. sys._MEIPASS проверяется внутри функции

    expected = str(Path(meipass_path_str) / "assets" / "icon.png")
    # ИСПРАВЛЕНО: Используем os.path.join для большей надежности с путями
    assert utils.resource_path("assets/icon.png") == os.path.join(meipass_path_str, "assets", "icon.png")

# ИСПРАВЛЕНО: Патчим sys.frozen=False и удаляем патч sys._MEIPASS
@patch('sys.frozen', False, create=True)
@patch('src.utils.__file__') # Патчим __file__ модуля utils
def test_resource_path_script(mock_file_attr):
    """Тест resource_path при запуске как обычный скрипт."""
    # ИСПРАВЛЕНО: Определяем пути более надежно
    # Имитируем, что utils.py находится в /project/src/utils.py
    utils_file_abs_path = Path('/fake/project/src/utils.py').resolve()
    project_root = utils_file_abs_path.parent.parent # /fake/project

    # Настраиваем мок __file__ так, чтобы он вел себя как строка или Path-like
    mock_file_attr.__str__.return_value = str(utils_file_abs_path)
    mock_file_attr.__fspath__.return_value = str(utils_file_abs_path) # Для Path()

    # --- ИСПРАВЛЕНО: Мокаем Path(__file__).resolve().parent.parent ---
    # Вместо моканья cwd, мокаем результат цепочки вызовов в самой функции
    with patch('src.utils.Path') as MockPath:
        mock_resolved_path = MagicMock(spec=Path)
        mock_src_dir = MagicMock(spec=Path)
        mock_base_path = MagicMock(spec=Path) # Это будет наш project_root

        mock_resolved_path.parent = mock_src_dir
        mock_src_dir.parent = mock_base_path

        # Когда Path() вызывается с моком __file__, возвращаем настроенный mock_resolved_path
        MockPath.return_value.resolve.return_value = mock_resolved_path

        # Когда Path() вызывается с base_path для финального пути,
        # он должен вернуть объект, который может быть объединен с relative_path
        # Мокаем `base_path / relative_path`
        mock_base_path.__truediv__ = lambda self, rel_path: project_root / rel_path # Используем реальный Path для конкатенации

        expected = str(project_root / "assets" / "icon.png")
        result = utils.resource_path("assets/icon.png")
        assert result == expected
        # Проверяем, что Path(__file__).resolve() было вызвано
        MockPath.assert_any_call(mock_file_attr)
        MockPath.return_value.resolve.assert_called_once()


# --- ДОБАВЛЕНЫ тесты для setup_logging ---

def test_setup_logging_success(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    """Тест успешной настройки логирования."""
    MockPath, mock_log_dir, _ = mock_path_in_utils
    mock_log_dir.is_dir.return_value = True # Директория существует

    utils.setup_logging()

    # Проверяем создание директории (не должно быть вызвано)
    mock_log_dir.mkdir.assert_not_called()

    # Проверяем создание форматера
    mock_logging_basic["Formatter"].assert_called_once_with('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Проверяем создание хендлера
    mock_logging_handlers.RotatingFileHandler.assert_called_once_with(
        mock_utils_config.LOG_FILE,
        maxBytes=mock_utils_config.LOG_MAX_BYTES,
        backupCount=mock_utils_config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    mock_handler_instance = mock_logging_handlers.RotatingFileHandler.return_value
    mock_handler_instance.setFormatter.assert_called_once()
    mock_handler_instance.setLevel.assert_called_once_with(mock_utils_config.LOG_LEVEL)

    # Проверяем настройку корневого логгера
    mock_logging_basic["getLogger"].assert_called_with() # Без аргумента - корневой
    root_logger_instance = mock_logging_basic["logger_instance"]
    root_logger_instance.setLevel.assert_called_once_with(mock_utils_config.LOG_LEVEL)
    root_logger_instance.addHandler.assert_called_once_with(mock_handler_instance)

    # Проверяем информационное сообщение о старте
    mock_logging_basic["info"].assert_called_once_with("="*20 + f" Logging started for {mock_utils_config.APP_NAME} " + "="*20)

    # Проверяем, что print не вызывался (не было фатальных ошибок)
    mock_logging_basic["print"].assert_not_called()


def test_setup_logging_creates_dir(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    """Тест создания директории логов, если она не существует."""
    MockPath, mock_log_dir, _ = mock_path_in_utils
    mock_log_dir.is_dir.return_value = False # Директория НЕ существует

    utils.setup_logging()

    # Проверяем создание директории
    mock_log_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    # Остальные проверки как в test_setup_logging_success
    mock_logging_handlers.RotatingFileHandler.assert_called_once()
    mock_logging_basic["getLogger"].assert_called()
    mock_logging_basic["info"].assert_called_once()
    mock_logging_basic["print"].assert_not_called()


def test_setup_logging_dir_creation_error(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    """Тест ошибки при создании директории логов."""
    MockPath, mock_log_dir, _ = mock_path_in_utils
    mock_log_dir.is_dir.return_value = False # Директория НЕ существует
    error_message = "Permission denied"
    mock_log_dir.mkdir.side_effect = OSError(error_message)

    utils.setup_logging()

    # Проверяем попытку создания директории
    mock_log_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    # Проверяем вывод фатальной ошибки в print
    mock_logging_basic["print"].assert_any_call(
        f"FATAL: Could not create log directory {mock_log_dir}: {error_message}"
    )

    # Хендлер и логгер не должны были настраиваться
    mock_logging_handlers.RotatingFileHandler.assert_not_called()
    mock_logging_basic["getLogger"].assert_not_called() # getLogger не вызывается до добавления хендлера
    mock_logging_basic["info"].assert_not_called()


def test_setup_logging_handler_error(mock_utils_config, mock_path_in_utils, mock_logging_handlers, mock_logging_basic):
    """Тест ошибки при создании файлового хендлера."""
    MockPath, mock_log_dir, _ = mock_path_in_utils
    mock_log_dir.is_dir.return_value = True # Директория существует
    error_message = "Cannot open file"
    mock_logging_handlers.RotatingFileHandler.side_effect = Exception(error_message)

    utils.setup_logging()

    # Проверяем попытку создания хендлера
    mock_logging_handlers.RotatingFileHandler.assert_called_once()

    # Проверяем вывод фатальной ошибки в print (stderr)
    mock_logging_basic["print"].assert_called_once_with(
        f"FATAL: Could not configure file logging to {mock_utils_config.LOG_FILE}: {error_message}",
        file=sys.stderr
    )

    # Логгер не должен был получить этот хендлер, info не вызывается
    mock_logging_basic["getLogger"].assert_not_called()
    mock_logging_basic["info"].assert_not_called()