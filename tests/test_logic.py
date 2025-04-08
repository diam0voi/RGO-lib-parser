# tests/test_logic.py
import pytest
from unittest.mock import patch, MagicMock, mock_open, call, ANY
import os
import base64
import logging
import threading
import stat
from io import BytesIO
from pathlib import Path
import time # <-- ДОБАВЛЕН импорт time для проверки sleep
import sys # <-- ДОБАВЛЕН для sys.stderr

# Импортируем тестируемый класс и зависимости
from src.logic import LibraryHandler
import src.logic # Импортируем сам модуль для доступа к config и utils
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ИСПРАВЛЕНО: Импортируем utils напрямую для передачи в хелпер
from src import utils as src_utils

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    Image = MagicMock()
    Image.Resampling = MagicMock()
    Image.Resampling.LANCZOS = "LANCZOS_MOCK"
    # Определяем UnidentifiedImageError, если PIL не установлен
    class UnidentifiedImageError(Exception): pass
    Image.UnidentifiedImageError = UnidentifiedImageError


# --- Константы и фейковый конфиг ---
FAKE_CONFIG_DATA = {
    "DEFAULT_USER_AGENT": "Test Agent/1.0",
    "INITIAL_COOKIE_URL": "https://fake.rgo.ru/cookie",
    "MAX_RETRIES": 2,
    "RETRY_ON_HTTP_CODES": [500, 502],
    "DEFAULT_DELAY_SECONDS": 0.01,
    # "RETRY_DELAY": 0.02, # Не используется напрямую в тестах
    "REQUEST_TIMEOUT": (10, 30),
    "IMAGE_EXTENSIONS": ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'),
    "DEFAULT_ASPECT_RATIO_THRESHOLD": 1.1,
    "JPEG_QUALITY": 90,
    # Добавляем недостающие для тестов main
    "APP_NAME": "RGO Lib Parser Test",
    "LOG_FILE": "test_app.log",
}

# --- Вспомогательная функция ---
# ИСПРАВЛЕНО: Вынесена из класса и принимает mock_utils
def setup_mock_files(mock_path_methods, mock_utils_dict, file_list):
    """Вспомогательная функция для настройки моков файлов."""
    MockPathClass, get_mock_path, path_mocks = mock_path_methods
    input_dir_path = "/fake/input" # Базовая директория для iterdir

    mock_files_in_dir = []
    page_num_map = {}
    # Используем полный путь как ключ для is_spread_map
    full_path_spread_map = {}

    for name, page_num, is_spread, is_file in file_list:
        full_path_str = os.path.join(input_dir_path, name)
        mock_file = get_mock_path(full_path_str) # Получаем/создаем мок
        mock_file.is_file.return_value = is_file
        mock_file.suffix = Path(name).suffix # Устанавливаем суффикс явно
        mock_file.name = name # Устанавливаем имя явно
        mock_files_in_dir.append(mock_file)
        if page_num != -1:
            page_num_map[name] = page_num
        full_path_spread_map[full_path_str] = is_spread

    # Настраиваем iterdir для входной директории
    get_mock_path(input_dir_path).iterdir.return_value = mock_files_in_dir

    # ИСПРАВЛЕНО: Используем переданный словарь mock_utils_dict
    mock_utils_dict["get_page_number"].side_effect = lambda fname: page_num_map.get(Path(fname).name, -1)
    # Используем полный путь файла для is_likely_spread
    mock_utils_dict["is_likely_spread"].side_effect = lambda fpath, threshold: full_path_spread_map.get(str(fpath), False)

    return mock_files_in_dir # Возвращаем список моков файлов


# --- Фикстуры для test_logic ---

@pytest.fixture(autouse=True)
def disable_logging():
    logging.disable(logging.CRITICAL + 10)
    yield
    logging.disable(logging.NOTSET)

@pytest.fixture(autouse=True)
def mock_logic_config():
    # ИСПРАВЛЕНО: Используем MagicMock для имитации объекта config
    mock_config = MagicMock()
    for key, value in FAKE_CONFIG_DATA.items():
        setattr(mock_config, key, value)

    # Патчим config в модуле logic
    with patch('src.logic.config', mock_config) as patched_config:
        yield patched_config # Возвращаем сам мок для возможных проверок


@pytest.fixture
def mock_requests_session():
    with patch('src.logic.requests.Session') as MockSession:
        mock_instance = MockSession.return_value
        # Настраиваем мок ответа по умолчанию
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.content = b'fakedata'
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.raise_for_status.return_value = None
        mock_instance.get.return_value = mock_response
        # Используем реальный объект CookieJar для большей совместимости
        mock_instance.cookies = requests.cookies.RequestsCookieJar()
        mock_instance.mount = MagicMock()
        mock_instance.headers = {} # Инициализируем заголовки
        yield MockSession

@pytest.fixture
def mock_shutil_copy2():
     with patch('src.logic.shutil.copy2') as mock_copy:
        yield mock_copy

@pytest.fixture
def mock_path_methods():
    # ИСПРАВЛЕНО: Улучшаем мок Path и возвращаем path_mocks
    path_mocks = {} # Словарь для хранения моков путей

    def get_mock_path(path_arg):
        # Преобразуем аргумент в строку для ключа словаря
        path_str = str(path_arg)
        if path_str not in path_mocks:
            mock = MagicMock(spec=Path)
            # Устанавливаем основные атрибуты
            mock.name = Path(path_str).name
            mock.suffix = Path(path_str).suffix
            mock.__str__ = MagicMock(return_value=path_str)
            mock.__fspath__ = MagicMock(return_value=path_str) # Для совместимости с os.path

            # Настраиваем stat по умолчанию
            stat_result = MagicMock(spec=os.stat_result) # Используем spec
            stat_result.st_mode = stat.S_IFREG | 0o666
            stat_result.st_size = 1024 # Не пустой по умолчанию
            # Добавляем остальные атрибуты, чтобы избежать AttributeError
            stat_result.st_ino = 1
            stat_result.st_dev = 1
            stat_result.st_nlink = 1
            stat_result.st_uid = 0
            stat_result.st_gid = 0
            stat_result.st_atime = 0
            stat_result.st_mtime = 0
            stat_result.st_ctime = 0
            mock.stat = MagicMock(return_value=stat_result, name=f"stat_for_{path_str}")

            # Настраиваем is_file по умолчанию
            mock.is_file = MagicMock(return_value=True, name=f"is_file_for_{path_str}")

            # Настраиваем with_suffix
            def mock_with_suffix(suffix):
                # Используем pathlib для корректной замены суффикса
                new_path = Path(path_str).with_suffix(suffix)
                # Возвращаем или создаем мок для нового пути
                return get_mock_path(str(new_path))
            mock.with_suffix = MagicMock(side_effect=mock_with_suffix, name=f"with_suffix_for_{path_str}")

            # Настраиваем iterdir (по умолчанию пустой)
            mock.iterdir = MagicMock(return_value=[], name=f"iterdir_for_{path_str}")

            # Настраиваем mkdir
            mock.mkdir = MagicMock(name=f"mkdir_for_{path_str}")

            # Настраиваем parent (рекурсивно)
            parent_path = Path(path_str).parent
            if parent_path != Path(path_str): # Избегаем бесконечной рекурсии для корня
                # Получаем мок родителя рекурсивно
                mock.parent = get_mock_path(str(parent_path))
            else:
                mock.parent = mock # Корень ссылается сам на себя

            path_mocks[path_str] = mock
        return path_mocks[path_str]

    # Патчим конструктор Path в модуле logic
    with patch('src.logic.Path', side_effect=get_mock_path) as MockPathClass:
        # Возвращаем класс, функцию get_mock_path и словарь path_mocks
        yield MockPathClass, get_mock_path, path_mocks


@pytest.fixture
def mock_pil_image():
    # Определяем классы и константы перед патчем
    try:
        from PIL import Image as PilImage, UnidentifiedImageError as PilUnidentifiedImageError
        _UnidentifiedImageError = PilUnidentifiedImageError
        _Resampling = PilImage.Resampling if hasattr(PilImage, 'Resampling') else MagicMock()
        _LANCZOS = _Resampling.LANCZOS if hasattr(_Resampling, 'LANCZOS') else "LANCZOS_MOCK"
        _ImageSpec = PilImage.Image
    except ImportError:
        class _UnidentifiedImageError(Exception): pass
        _LANCZOS = "LANCZOS_MOCK"
        _ImageSpec = None # Нет спека, если PIL не установлен

    # Создаем мок для всего модуля Image
    MockImageModule = MagicMock(name="MockImageModule")

    # Мок для Image.open
    mock_open = MagicMock(name="MockImageOpen")
    # Мок для Image.new
    mock_new = MagicMock(name="MockImageNew")

    # Мок для инстанса изображения
    mock_img_instance = MagicMock(spec=_ImageSpec, name="MockImageInstance")
    mock_img_instance.convert.return_value = mock_img_instance
    mock_img_instance.resize.return_value = mock_img_instance
    mock_img_instance.paste = MagicMock(name="MockPaste")
    mock_img_instance.save = MagicMock(name="MockSave")
    mock_img_instance.size = (800, 1000) # Размер по умолчанию

    # Настраиваем контекстный менеджер для Image.open
    mock_context = MagicMock(name="MockImageOpenContext")
    mock_context.__enter__.return_value = mock_img_instance
    mock_context.__exit__ = MagicMock(return_value=None)
    mock_open.return_value = mock_context

    # Настраиваем Image.new
    mock_new.return_value = mock_img_instance

    # Присваиваем моки атрибутам мок-модуля
    MockImageModule.open = mock_open
    MockImageModule.new = mock_new
    MockImageModule.Resampling = MagicMock()
    MockImageModule.Resampling.LANCZOS = _LANCZOS
    MockImageModule.UnidentifiedImageError = _UnidentifiedImageError

    # Патчим Image в модуле logic
    with patch('src.logic.Image', MockImageModule):
         yield MockImageModule # Возвращаем мок всего модуля


@pytest.fixture
def mock_time_sleep():
    with patch('src.logic.time.sleep', return_value=None) as mock_sleep:
        yield mock_sleep

@pytest.fixture
def mock_builtin_open():
    # Используем стандартный mock_open
    m = mock_open()
    with patch('builtins.open', m) as mock_open_func:
        yield mock_open_func

@pytest.fixture
def mock_utils():
    # Патчим функции в src.logic.utils
    with patch('src.logic.utils.get_page_number') as mock_get_num, \
         patch('src.logic.utils.is_likely_spread') as mock_is_spread:
        # Возвращаем словарь с моками
        yield {
            "get_page_number": mock_get_num,
            "is_likely_spread": mock_is_spread
        }

@pytest.fixture
def mock_status_callback():
    return MagicMock(name="StatusCallbackMock")

@pytest.fixture
def mock_progress_callback():
    return MagicMock(name="ProgressCallbackMock")

@pytest.fixture
def stop_event():
    return threading.Event()

@pytest.fixture
def handler(mock_status_callback, mock_progress_callback, stop_event):
    # Передаем реальные коллбэки (моки) и событие
    return LibraryHandler(
        status_callback=mock_status_callback,
        progress_callback=mock_progress_callback,
        stop_event=stop_event
    )

# --- Тесты для LibraryHandler ---
class TestLibraryHandler:

    # --- Тесты _setup_session_with_retry ---
    def test_setup_session_with_retry(self, handler, mock_requests_session, mock_logic_config):
        handler._setup_session_with_retry()
        mock_session_instance = mock_requests_session.return_value
        mock_requests_session.assert_called_once()
        # Проверяем установку заголовка
        assert mock_session_instance.headers['User-Agent'] == mock_logic_config.DEFAULT_USER_AGENT
        # Проверяем mount
        mount_calls = mock_session_instance.mount.call_args_list
        assert len(mount_calls) == 2
        assert mount_calls[0] == call('https://', ANY)
        assert mount_calls[1] == call('http://', ANY)
        # Проверяем параметры Retry внутри адаптера
        adapter_instance = mount_calls[0].args[1]
        assert isinstance(adapter_instance, HTTPAdapter)
        retry_strategy = adapter_instance.max_retries
        assert isinstance(retry_strategy, Retry)
        assert retry_strategy.total == mock_logic_config.MAX_RETRIES
        assert set(retry_strategy.status_forcelist) == set(mock_logic_config.RETRY_ON_HTTP_CODES)
        # Проверяем, что сессия сохранена
        assert handler.session is mock_session_instance
        # Проверяем повторный вызов (сессия не должна создаваться заново)
        mock_requests_session.reset_mock()
        handler._setup_session_with_retry()
        mock_requests_session.assert_not_called()

    # --- Тесты _get_initial_cookies ---
    def test_get_initial_cookies_success(self, handler, mock_requests_session, mock_status_callback, mock_logic_config):
        # Настраиваем успешный ответ и куки
        mock_session = mock_requests_session.return_value
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        # Добавляем куки в CookieJar
        mock_session.cookies.set('sessionid', 'testcookie123', domain='fake.rgo.ru')

        result = handler._get_initial_cookies()

        assert result is True
        mock_session.get.assert_called_once_with(
            mock_logic_config.INITIAL_COOKIE_URL,
            timeout=mock_logic_config.REQUEST_TIMEOUT
        )
        mock_response.raise_for_status.assert_called_once()
        # Проверяем сообщения статуса
        mock_status_callback.assert_any_call(f"Автоматическое получение сессионных куки с {mock_logic_config.INITIAL_COOKIE_URL}...")
        mock_status_callback.assert_any_call("Успешно получены куки: ['sessionid']")

    def test_get_initial_cookies_no_cookies_set(self, handler, mock_requests_session, mock_status_callback, mock_logic_config):
        # Настраиваем успешный ответ, но без кук
        mock_session = mock_requests_session.return_value
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        mock_session.cookies.clear() # Убедимся, что кук нет

        result = handler._get_initial_cookies()

        assert result is False # Ожидаем False, если куки не установлены
        mock_session.get.assert_called_once_with(mock_logic_config.INITIAL_COOKIE_URL, timeout=ANY)
        mock_status_callback.assert_any_call("Предупреждение: Не удалось автоматически получить куки (сервер не установил?).")

    def test_get_initial_cookies_timeout(self, handler, mock_requests_session, mock_status_callback, mock_logic_config):
        # Настраиваем ошибку Timeout
        mock_session = mock_requests_session.return_value
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout error")

        result = handler._get_initial_cookies()

        assert result is False
        mock_session.get.assert_called_once_with(mock_logic_config.INITIAL_COOKIE_URL, timeout=ANY)
        mock_status_callback.assert_any_call(f"Ошибка: Превышено время ожидания при получении куки с {mock_logic_config.INITIAL_COOKIE_URL}.")

    def test_get_initial_cookies_request_exception(self, handler, mock_requests_session, mock_status_callback, mock_logic_config):
        # Настраиваем другую ошибку сети
        mock_session = mock_requests_session.return_value
        error_message = "Network error"
        mock_session.get.side_effect = requests.exceptions.RequestException(error_message)

        result = handler._get_initial_cookies()

        assert result is False
        mock_session.get.assert_called_once_with(mock_logic_config.INITIAL_COOKIE_URL, timeout=ANY)
        mock_status_callback.assert_any_call(f"Ошибка при получении куки: {error_message}.")

    def test_get_initial_cookies_session_setup_fails(self, handler, mock_requests_session, mock_status_callback):
        # Имитируем ошибку при *создании* сессии (внутри _setup_session_with_retry)
        error_message = "Cannot create session"
        mock_requests_session.side_effect = Exception(error_message)
        handler.session = None # Убедимся, что сессии нет

        result = handler._get_initial_cookies()

        assert result is False
        mock_requests_session.assert_called_once() # Попытка создания была
        # Проверяем сообщение об ошибке, которое генерируется в _get_initial_cookies при ошибке setup
        mock_status_callback.assert_any_call(f"Критическая ошибка при настройке сессии: {error_message}")


    # --- Тесты download_pages ---
    @pytest.fixture
    def mock_get_cookies_success(self, handler):
        # Патчим метод _get_initial_cookies у *инстанса* handler
        with patch.object(handler, '_get_initial_cookies', return_value=True) as mock_method:
            yield mock_method

    @pytest.fixture
    def mock_get_cookies_fail(self, handler):
        with patch.object(handler, '_get_initial_cookies', return_value=False) as mock_method:
            yield mock_method

    def test_download_pages_success(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_time_sleep, mock_status_callback, mock_progress_callback, mock_logic_config):
        # ИСПРАВЛЕНО: Получаем path_mocks из фикстуры
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        mock_session = mock_requests_session.return_value

        base_url = "https://test.com/base/"
        url_ids = "book123/"
        pdf_filename = "document.pdf"
        total_pages = 3
        output_dir = "test_output"

        # Убедимся, что мок stat для финальных файлов возвращает > 0 (по умолчанию 1024)
        # Фикстура mock_path_methods уже настраивает это

        success_count, total_count = handler.download_pages(
            base_url, url_ids, pdf_filename, total_pages, output_dir
        )

        assert success_count == total_pages
        assert total_count == total_pages
        mock_get_cookies_success.assert_called_once()
        # Проверяем mkdir на моке выходной директории
        get_mock_path(output_dir).mkdir.assert_called_once_with(parents=True, exist_ok=True)
        assert mock_session.get.call_count == total_pages
        assert mock_builtin_open.call_count == total_pages

        # ИСПРАВЛЕНО: Проверяем общее количество вызовов stat через словарь path_mocks
        total_stat_calls = sum(p.stat.call_count for p in path_mocks.values())
        assert total_stat_calls == total_pages

        # Проверяем URL и имя файла для первой страницы
        page_string_0 = f"{pdf_filename}/0"
        page_b64_0 = base64.b64encode(page_string_0.encode('utf-8')).decode('utf-8')
        expected_url_0 = f"{base_url}{url_ids}{page_b64_0}"
        expected_filename_0_str = os.path.join(output_dir, "page_000.jpeg") # .jpeg из Content-Type

        mock_session.get.assert_any_call(expected_url_0, timeout=mock_logic_config.REQUEST_TIMEOUT)
        mock_builtin_open.assert_any_call(expected_filename_0_str, 'wb')
        mock_file_handle = mock_builtin_open()
        mock_file_handle.write.assert_any_call(b'fakedata')

        assert mock_progress_callback.call_count == total_pages + 1
        mock_progress_callback.assert_has_calls([call(i, total_pages) for i in range(total_pages + 1)])
        assert mock_time_sleep.call_count == total_pages
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: {total_pages} из {total_pages}.")

    def test_download_pages_interrupted(self, handler, stop_event, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_time_sleep, mock_status_callback, mock_progress_callback):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        mock_session = mock_requests_session.return_value
        total_pages = 5
        interrupt_before_page_index = 2 # Прервать перед скачиванием страницы с индексом 2 (т.е. 3-й страницы)

        # ИСПРАВЛЕНО: Модифицируем side_effect для stop_event
        original_get = mock_session.get
        call_counter = 0
        def get_side_effect(*args, **kwargs):
            nonlocal call_counter
            current_page_index = call_counter
            call_counter += 1
            # Устанавливаем событие *перед* вызовом, который должен быть прерван
            if current_page_index == interrupt_before_page_index:
                stop_event.set()
                # Важно: не кидаем исключение здесь, цикл должен сам проверить stop_event
            # Возвращаем нормальный ответ, если событие не установлено
            return original_get(*args, **kwargs)

        mock_session.get.side_effect = get_side_effect

        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        # ИСПРАВЛЕНО: Ожидаем 2 успешных скачивания (индексы 0 и 1)
        expected_success = interrupt_before_page_index
        assert success_count == expected_success
        assert total_count == total_pages
        # Вызвали get дважды успешно
        assert mock_session.get.call_count == expected_success
        assert mock_builtin_open.call_count == expected_success
        # Проверяем stat для скачанных файлов
        total_stat_calls = sum(p.stat.call_count for p in path_mocks.values())
        assert total_stat_calls == expected_success

        mock_status_callback.assert_any_call("--- Скачивание прервано пользователем ---")
        # Прогресс: 0/5, 1/5, 2/5
        assert mock_progress_callback.call_count == expected_success + 1
        mock_progress_callback.assert_has_calls([call(i, total_pages) for i in range(expected_success + 1)])
        assert mock_time_sleep.call_count == expected_success
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: {expected_success} из {total_pages}.")

    def test_download_pages_http_error(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_status_callback, mock_progress_callback, mock_logic_config):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        mock_session = mock_requests_session.return_value
        total_pages = 3

        # Настраиваем ответы: OK, Error, OK
        mock_response_ok = MagicMock(spec=requests.Response, status_code=200, headers={'Content-Type': 'image/jpeg'}, content=b'ok')
        mock_response_ok.raise_for_status.return_value = None
        mock_response_err = MagicMock(spec=requests.Response, status_code=404)
        # Связываем ответ с исключением
        http_error = requests.exceptions.HTTPError("Not Found", response=mock_response_err)
        mock_response_err.raise_for_status.side_effect = http_error

        mock_session.get.side_effect = [mock_response_ok, mock_response_err, mock_response_ok]

        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        # ИСПРАВЛЕНО: Ожидаем 2 успешных скачивания
        assert success_count == 2
        assert total_count == total_pages
        assert mock_session.get.call_count == 3
        assert mock_builtin_open.call_count == 2
        # Проверяем stat только для успешных
        total_stat_calls = sum(p.stat.call_count for p in path_mocks.values())
        assert total_stat_calls == 2

        mock_status_callback.assert_any_call(f"Ошибка HTTP 404 на стр. 2 (после {mock_logic_config.MAX_RETRIES} попыток): Not Found")
        mock_progress_callback.assert_has_calls([call(i, total_pages) for i in range(total_pages + 1)])
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 2 из {total_pages}.")

    def test_download_pages_empty_file(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_status_callback, mock_progress_callback):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        mock_session = mock_requests_session.return_value
        # Ответ сервера успешный
        mock_response = MagicMock(spec=requests.Response, status_code=200, headers={'Content-Type': 'image/gif'}, content=b'empty_but_present')
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        total_pages = 1
        output_dir = "out"
        # ИСПРАВЛЕНО: Настраиваем stat для конкретного файла, который будет создан
        # Имя файла определяется Content-Type и индексом
        output_filename_str = os.path.join(output_dir, "page_000.gif")
        mock_file_path = get_mock_path(output_filename_str)
        # Устанавливаем размер 0 через мок stat
        mock_file_path.stat.return_value.st_size = 0

        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, output_dir)

        # ИСПРАВЛЕНО: Ожидаем 0 успешных скачиваний, так как файл пустой
        assert success_count == 0
        assert total_count == total_pages
        # Файл должен быть открыт и записан
        assert mock_builtin_open.call_count == 1
        mock_builtin_open.assert_called_with(output_filename_str, 'wb')
        mock_builtin_open().write.assert_called_with(b'empty_but_present')
        # Stat должен быть вызван для проверки размера
        mock_file_path.stat.assert_called_once()
        mock_status_callback.assert_any_call("Предупреждение: Файл page_000.gif пустой.")
        mock_progress_callback.assert_has_calls([call(0, 1), call(1, 1)])
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 0 из {total_pages}.")


    def test_download_pages_unknown_content_type(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_status_callback):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        mock_session = mock_requests_session.return_value
        # Неизвестный Content-Type
        mock_response = MagicMock(spec=requests.Response, status_code=200, headers={'Content-Type': 'application/octet-stream'}, content=b'data')
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        output_dir = "test_output_unknown"
        total_pages = 1
        handler.download_pages("b/", "i/", "p", total_pages, output_dir)

        # ИСПРАВЛЕНО: Ожидаем расширение .jpg по умолчанию
        expected_filename_str = os.path.join(output_dir, "page_000.jpg")
        # Проверяем вызов open
        mock_builtin_open.assert_called_once_with(expected_filename_str, 'wb')
        mock_builtin_open().write.assert_called_with(b'data')
        # Проверяем stat
        mock_file_path = get_mock_path(expected_filename_str)
        mock_file_path.stat.assert_called_once()
        # Проверяем финальный статус (файл не пустой по умолчанию)
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 1 из {total_pages}.")


    def test_download_pages_mkdir_error(self, handler, mock_get_cookies_success, mock_path_methods, mock_status_callback):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        output_dir = "out_dir_fail"
        error_message = "Permission denied"
        # Настраиваем ошибку на моке директории
        mock_dir_path = get_mock_path(output_dir)
        mock_dir_path.mkdir.side_effect = OSError(error_message)

        total_pages = 1
        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, output_dir)

        assert success_count == 0
        assert total_count == total_pages
        mock_dir_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_status_callback.assert_any_call(f"Ошибка создания папки для страниц '{output_dir}': {error_message}")
        # Финальный статус НЕ должен вызываться при ошибке mkdir
        final_status_call = call(f"Скачивание завершено. Успешно: 0 из {total_pages}.")
        assert final_status_call not in mock_status_callback.call_args_list


    # --- Тесты process_images ---

    def test_process_images_copy_cover_and_spread(self, handler, mock_path_methods, mock_shutil_copy2, mock_utils, mock_status_callback, mock_progress_callback, mock_logic_config):
        # ИСПРАВЛЕНО: Передаем mock_utils в setup_mock_files
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "/fake/input"
        output_folder = "test_output"

        files_setup = [
            ("page_000.jpg", 0, False, True),       # Обложка
            ("page_001.png", 1, False, True),       # Одиночная, след. разворот -> копируем
            ("page_002_spread.gif", 2, True, True), # Разворот -> копируем
            ("not_an_image.txt", -1, False, True),  # Не изображение
            ("page_003.bmp", 3, False, True),       # Одиночная, последняя -> копируем
            ("subdir", -1, False, False),           # Не файл
        ]
        # ИСПРАВЛЕНО: Передаем mock_utils
        mock_files = setup_mock_files(mock_path_methods, mock_utils, files_setup)
        # Получаем только нумерованные файлы изображений, как в коде
        numbered_files = sorted(
            [f for f in mock_files if mock_utils["get_page_number"](f.name) != -1 and f.suffix.lower() in mock_logic_config.IMAGE_EXTENSIONS],
            key=lambda f: mock_utils["get_page_number"](f.name)
        )
        total_numbered = len(numbered_files) # = 4

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == total_numbered # Обработали все 4 нумерованных файла
        assert created_spread_count == 0 # Только копирование
        get_mock_path(output_folder).mkdir.assert_called_once_with(parents=True, exist_ok=True)
        get_mock_path(input_folder).iterdir.assert_called_once()

        # Проверяем is_likely_spread (вызывается для 1, 2, 3)
        assert mock_utils["is_likely_spread"].call_count == 3
        # Используем ANY для порога
        mock_utils["is_likely_spread"].assert_has_calls([
            call(numbered_files[1], ANY), # page_001.png
            call(numbered_files[2], ANY), # page_002_spread.gif
            call(numbered_files[3], ANY), # page_003.bmp
        ], any_order=True) # Порядок может зависеть от внутренней логики

        # Проверяем copy2
        assert mock_shutil_copy2.call_count == total_numbered
        mock_shutil_copy2.assert_has_calls([
            call(numbered_files[0], get_mock_path(os.path.join(output_folder, "spread_000.jpg"))),
            call(numbered_files[1], get_mock_path(os.path.join(output_folder, "spread_001.png"))),
            call(numbered_files[2], get_mock_path(os.path.join(output_folder, "spread_002.gif"))),
            call(numbered_files[3], get_mock_path(os.path.join(output_folder, "spread_003.bmp"))),
        ], any_order=False) # Порядок важен

        assert mock_progress_callback.call_count == total_numbered + 1
        mock_progress_callback.assert_has_calls([call(i, total_numbered) for i in range(total_numbered + 1)])
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: {total_numbered}. Создано разворотов: 0.")

    def test_process_images_merge_two_singles(self, handler, mock_path_methods, mock_shutil_copy2, mock_pil_image, mock_utils, mock_status_callback, mock_progress_callback, mock_logic_config):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "/fake/input"
        output_folder = "test_output_merge"

        files_setup = [
            ("page_000_cover.jpg", 0, False, True), # Обложка
            ("page_001_left.png", 1, False, True),  # Левая для склейки
            ("page_002_right.bmp", 2, False, True), # Правая для склейки
        ]
        # ИСПРАВЛЕНО: Передаем mock_utils
        mock_files = setup_mock_files(mock_path_methods, mock_utils, files_setup)
        numbered_files = sorted(
            [f for f in mock_files if mock_utils["get_page_number"](f.name) != -1],
            key=lambda f: mock_utils["get_page_number"](f.name)
        )
        total_numbered = len(numbered_files) # = 3

        # Настраиваем моки PIL для склейки
        mock_img_left = MagicMock(spec=Image.Image if Image is not MagicMock else None, size=(800, 1000))
        mock_img_left.convert.return_value = mock_img_left
        mock_img_right = MagicMock(spec=Image.Image if Image is not MagicMock else None, size=(800, 1000))
        mock_img_right.convert.return_value = mock_img_right
        mock_img_cover = MagicMock(spec=Image.Image if Image is not MagicMock else None, size=(800, 1000))

        def mock_image_open_side_effect(path):
            mock_context = MagicMock()
            path_str = str(path) # Используем строку для сравнения
            if path_str == str(numbered_files[1]): mock_context.__enter__.return_value = mock_img_left
            elif path_str == str(numbered_files[2]): mock_context.__enter__.return_value = mock_img_right
            elif path_str == str(numbered_files[0]): mock_context.__enter__.return_value = mock_img_cover
            else: raise FileNotFoundError(f"Unexpected path in Image.open: {path_str}")
            return mock_context
        mock_pil_image.open.side_effect = mock_image_open_side_effect
        # Получаем мок созданного изображения
        mock_spread_img = mock_pil_image.new.return_value

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == total_numbered # Обработали обложку + 2 для склейки
        assert created_spread_count == 1 # Создали один разворот
        # is_likely_spread вызывается для стр. 1 и 2
        assert mock_utils["is_likely_spread"].call_count == 2

        # Копируем обложку
        mock_shutil_copy2.assert_called_once_with(numbered_files[0], get_mock_path(os.path.join(output_folder, "spread_000.jpg")))
        # Открываем файлы для склейки
        mock_pil_image.open.assert_has_calls([call(numbered_files[1]), call(numbered_files[2])], any_order=True)
        # Создаем новое изображение
        mock_pil_image.new.assert_called_once_with('RGB', (1600, 1000), (255, 255, 255))
        # Вставляем части
        mock_spread_img.paste.assert_has_calls([call(mock_img_left, (0, 0)), call(mock_img_right, (800, 0))])
        # Сохраняем результат
        expected_spread_filename_str = os.path.join(output_folder, "spread_001-002.jpg")
        mock_spread_img.save.assert_called_once_with(
            get_mock_path(expected_spread_filename_str),
             "JPEG", quality=mock_logic_config.JPEG_QUALITY, optimize=True
        )

        # Прогресс: 0/3 (старт), 1/3 (после обложки), 3/3 (после склейки 1 и 2)
        assert mock_progress_callback.call_count == 3
        mock_progress_callback.assert_has_calls([call(0, 3), call(1, 3), call(3, 3)])
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 3. Создано разворотов: 1.")

    def test_process_images_merge_different_heights(self, handler, mock_path_methods, mock_pil_image, mock_utils, mock_shutil_copy2, mock_logic_config):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "/fake/input"
        output_folder = "test_output_resize"

        files_setup = [
            ("page_001_short.png", 1, False, True), # Левая для склейки
            ("page_002_tall.bmp", 2, False, True),  # Правая для склейки
        ]
        # ИСПРАВЛЕНО: Передаем mock_utils
        mock_files = setup_mock_files(mock_path_methods, mock_utils, files_setup)
        numbered_files = sorted(
            [f for f in mock_files if mock_utils["get_page_number"](f.name) != -1],
            key=lambda f: mock_utils["get_page_number"](f.name)
        )
        total_numbered = len(numbered_files) # = 2

        # Настраиваем моки PIL с разными размерами
        mock_img_left = MagicMock(spec=Image.Image if Image is not MagicMock else None, size=(800, 1000))
        mock_img_left.convert.return_value = mock_img_left
        mock_img_right = MagicMock(spec=Image.Image if Image is not MagicMock else None, size=(820, 1100)) # Выше
        mock_img_right.convert.return_value = mock_img_right
        # Мок для измененного левого изображения
        target_height = 1100
        ratio_left = target_height / 1000
        expected_w_left = int(800 * ratio_left)
        mock_resized_left = MagicMock(spec=Image.Image if Image is not MagicMock else None, size=(expected_w_left, target_height))
        mock_resized_left.convert.return_value = mock_resized_left
        mock_img_left.resize.return_value = mock_resized_left # Настроим возврат resize

        def mock_image_open_side_effect(path):
            mock_context = MagicMock()
            path_str = str(path)
            if path_str == str(numbered_files[0]): mock_context.__enter__.return_value = mock_img_left
            elif path_str == str(numbered_files[1]): mock_context.__enter__.return_value = mock_img_right
            else: raise FileNotFoundError(f"Unexpected path in Image.open: {path_str}")
            return mock_context
        mock_pil_image.open.side_effect = mock_image_open_side_effect
        mock_spread_img = mock_pil_image.new.return_value

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == total_numbered # Обработали 2 файла для склейки
        assert created_spread_count == 1 # Создали 1 разворот
        mock_shutil_copy2.assert_not_called() # Ничего не копировали

        # Проверяем resize левого изображения
        mock_img_left.resize.assert_called_once_with((expected_w_left, target_height), mock_pil_image.Resampling.LANCZOS)
        mock_img_right.resize.assert_not_called() # Правое не меняли

        # Проверяем создание нового изображения
        total_width = expected_w_left + 820 # Ширина измененного левого + правого
        mock_pil_image.new.assert_called_once_with('RGB', (total_width, target_height), (255, 255, 255))
        # Проверяем вставку (с измененным левым)
        mock_spread_img.paste.assert_has_calls([
            call(mock_resized_left, (0, 0)),
            call(mock_img_right, (expected_w_left, 0))
        ])
        # Проверяем сохранение
        expected_filename_str = os.path.join(output_folder, "spread_001-002.jpg")
        mock_spread_img.save.assert_called_once_with(get_mock_path(expected_filename_str), "JPEG", quality=mock_logic_config.JPEG_QUALITY, optimize=True)

    def test_process_images_single_then_spread(self, handler, mock_path_methods, mock_shutil_copy2, mock_utils, mock_logic_config):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "/fake/input"
        output_folder = "test_output_single_spread"

        files_setup = [
            ("page_001_single.jpg", 1, False, True), # Одиночная
            ("page_002_spread.png", 2, True, True),  # Разворот
        ]
        # ИСПРАВЛЕНО: Передаем mock_utils
        mock_files = setup_mock_files(mock_path_methods, mock_utils, files_setup)
        numbered_files = sorted(
            [f for f in mock_files if mock_utils["get_page_number"](f.name) != -1],
            key=lambda f: mock_utils["get_page_number"](f.name)
        )
        total_numbered = len(numbered_files) # = 2

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == total_numbered # Обработали оба файла
        assert created_spread_count == 0 # Только копирование
        assert mock_shutil_copy2.call_count == 2
        # Проверяем вызовы с моками путей
        mock_shutil_copy2.assert_has_calls([
            call(numbered_files[0], get_mock_path(os.path.join(output_folder, "spread_001.jpg"))), # Копируем одиночную
            call(numbered_files[1], get_mock_path(os.path.join(output_folder, "spread_002.png"))), # Копируем разворот
        ], any_order=False) # Порядок важен

    def test_process_images_input_dir_not_found(self, handler, mock_path_methods, mock_shutil_copy2, mock_pil_image, mock_status_callback):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "non_existent"
        output_folder = "test_output"
        # Настраиваем ошибку на iterdir
        mock_input_dir = get_mock_path(input_folder)
        mock_input_dir.iterdir.side_effect = FileNotFoundError(f"Dir not found: {input_folder}")

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0
        assert created_spread_count == 0
        get_mock_path(output_folder).mkdir.assert_called_once()
        mock_input_dir.iterdir.assert_called_once()
        mock_status_callback.assert_any_call(f"Ошибка: Папка со страницами '{input_folder}' не найдена.")
        mock_shutil_copy2.assert_not_called()
        mock_pil_image.open.assert_not_called()
        # Финальный статус НЕ вызывается
        final_status_call = call(f"Обработка завершена. Обработано/скопировано: 0. Создано разворотов: 0.")
        assert final_status_call not in mock_status_callback.call_args_list

    def test_process_images_input_dir_read_error(self, handler, mock_path_methods, mock_status_callback):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "input_permission_denied"
        output_folder = "test_output"
        error_message = "Permission denied"
        mock_input_dir = get_mock_path(input_folder)
        mock_input_dir.iterdir.side_effect = OSError(error_message)

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0
        assert created_spread_count == 0
        get_mock_path(output_folder).mkdir.assert_called_once()
        mock_input_dir.iterdir.assert_called_once()
        mock_status_callback.assert_any_call(f"Ошибка чтения папки '{input_folder}': {error_message}")
        # Финальный статус НЕ вызывается
        final_status_call = call(f"Обработка завершена. Обработано/скопировано: 0. Создано разворотов: 0.")
        assert final_status_call not in mock_status_callback.call_args_list

    def test_process_images_empty_input_dir(self, handler, mock_path_methods, mock_utils, mock_status_callback):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "/fake/input"
        output_folder = "test_output"
        # iterdir вернет пустой список
        # ИСПРАВЛЕНО: Передаем mock_utils
        setup_mock_files(mock_path_methods, mock_utils, [])

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0
        assert created_spread_count == 0
        get_mock_path(output_folder).mkdir.assert_called_once()
        get_mock_path(input_folder).iterdir.assert_called_once()
        mock_status_callback.assert_any_call("В папке не найдено подходящих файлов изображений с номерами.")
        # Финальный статус НЕ вызывается, если нет файлов для обработки
        final_status_call = call(f"Обработка завершена. Обработано/скопировано: 0. Создано разворотов: 0.")
        assert final_status_call not in mock_status_callback.call_args_list

    def test_process_images_no_numbered_files(self, handler, mock_path_methods, mock_utils, mock_status_callback, mock_logic_config):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "/fake/input"
        output_folder = "test_output"
        files_setup = [
            ("cover.jpg", -1, False, True),
            ("image_no_num.png", -1, False, True),
            ("document.pdf", -1, False, True), # Не изображение
        ]
        # ИСПРАВЛЕНО: Передаем mock_utils
        mock_files = setup_mock_files(mock_path_methods, mock_utils, files_setup)

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0
        assert created_spread_count == 0
        get_mock_path(input_folder).iterdir.assert_called_once()
        # get_page_number вызывается для всех файлов из iterdir
        assert mock_utils["get_page_number"].call_count == len(files_setup)
        mock_status_callback.assert_any_call("В папке не найдено подходящих файлов изображений с номерами.")
        # Финальный статус НЕ вызывается
        final_status_call = call(f"Обработка завершена. Обработано/скопировано: 0. Создано разворотов: 0.")
        assert final_status_call not in mock_status_callback.call_args_list

    def test_process_images_merge_error(self, handler, mock_path_methods, mock_pil_image, mock_utils, mock_status_callback, mock_logic_config):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "/fake/input"
        output_folder = "test_output_merge_err"

        files_setup = [
            ("page_001.png", 1, False, True),
            ("page_002_corrupt.bmp", 2, False, True), # Этот файл вызовет ошибку
        ]
        # ИСПРАВЛЕНО: Передаем mock_utils
        mock_files = setup_mock_files(mock_path_methods, mock_utils, files_setup)
        numbered_files = sorted(
            [f for f in mock_files if mock_utils["get_page_number"](f.name) != -1],
            key=lambda f: mock_utils["get_page_number"](f.name)
        )
        total_numbered = len(numbered_files) # = 2

        # Настраиваем ошибку при открытии второго файла
        error_message = "Cannot identify image file"
        mock_img_left = MagicMock(spec=Image.Image if Image is not MagicMock else None, size=(800, 1000))
        mock_img_left.convert.return_value = mock_img_left

        def mock_image_open_side_effect(path):
            mock_context = MagicMock()
            path_str = str(path)
            if path_str == str(numbered_files[0]):
                mock_context.__enter__.return_value = mock_img_left
            elif path_str == str(numbered_files[1]):
                # Используем ошибку из мока Image
                raise mock_pil_image.UnidentifiedImageError(error_message)
            else: raise FileNotFoundError()
            return mock_context
        mock_pil_image.open.side_effect = mock_image_open_side_effect

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        # Ожидаем 2 обработанных файла (т.к. инкремент = 2 при ошибке склейки)
        assert processed_count == 2
        assert created_spread_count == 0
        # Пытались открыть оба файла
        mock_pil_image.open.assert_has_calls([call(numbered_files[0]), call(numbered_files[1])])
        mock_pil_image.new.assert_not_called() # Создание разворота не произошло
        # Проверяем сообщение об ошибке
        mock_status_callback.assert_any_call(
            f"Ошибка при создании разворота для {numbered_files[0].name} и {numbered_files[1].name}: {error_message}"
        )
        # Финальный статус вызывается после завершения цикла
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 2. Создано разворотов: 0.")

    def test_process_images_interrupted(self, handler, stop_event, mock_path_methods, mock_shutil_copy2, mock_pil_image, mock_utils, mock_status_callback, mock_progress_callback, mock_logic_config):
        MockPathClass, get_mock_path, path_mocks = mock_path_methods
        input_folder = "/fake/input"
        output_folder = "test_output_interrupt"

        files_setup = [
            ("page_000.jpg", 0, False, True), # Обложка
            ("page_001.png", 1, False, True), # Одиночная
            ("page_002.bmp", 2, False, True), # Одиночная
        ]
        # ИСПРАВЛЕНО: Передаем mock_utils
        mock_files = setup_mock_files(mock_path_methods, mock_utils, files_setup)
        numbered_files = sorted(
            [f for f in mock_files if mock_utils["get_page_number"](f.name) != -1],
            key=lambda f: mock_utils["get_page_number"](f.name)
        )
        total_numbered = len(numbered_files) # = 3

        # Имитируем остановку *после* копирования первого файла (обложки)
        original_copy = mock_shutil_copy2.side_effect
        def stop_after_first_copy(*args, **kwargs):
            # Вызываем оригинальный copy2
            result = None
            if original_copy:
                 result = original_copy(*args, **kwargs)
            # Устанавливаем флаг *после* первого вызова
            if mock_shutil_copy2.call_count == 1:
                stop_event.set()
            return result
        mock_shutil_copy2.side_effect = stop_after_first_copy

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 1 # Успели обработать только обложку
        assert created_spread_count == 0
        mock_shutil_copy2.assert_called_once() # Скопировали только обложку
        mock_pil_image.open.assert_not_called() # До склейки не дошли
        mock_status_callback.assert_any_call("--- Обработка прервана пользователем ---")
        # Прогресс: 0/3 (старт), 1/3 (после обложки)
        assert mock_progress_callback.call_count == 2
        mock_progress_callback.assert_has_calls([call(0, total_numbered), call(1, total_numbered)])
        # Финальный статус вызывается после прерывания
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 1. Создано разворотов: 0.")