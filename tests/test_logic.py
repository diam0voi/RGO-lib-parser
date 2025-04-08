# tests/test_logic.py
import pytest
from unittest.mock import patch, MagicMock, mock_open, call, ANY
import os
import base64
import logging
import threading
import stat # <-- Импорт был здесь, все ок
from io import BytesIO
from pathlib import Path

# Импортируем тестируемый класс и зависимости
from src.logic import LibraryHandler
import src.logic # Импортируем модуль для патчинга config и utils
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from PIL import Image
except ImportError:
    Image = MagicMock()
    Image.Resampling = MagicMock()
    Image.Resampling.LANCZOS = "LANCZOS_MOCK"

# --- Константы и фейковый конфиг ---
FAKE_CONFIG_DATA = {
    "DEFAULT_USER_AGENT": "Test Agent/1.0",
    "INITIAL_COOKIE_URL": "https://fake.rgo.ru/cookie",
    "MAX_RETRIES": 2,
    "RETRY_ON_HTTP_CODES": [500, 502],
    "DEFAULT_DELAY_SECONDS": 0.01,
    # "RETRY_DELAY": 0.02, # Не используется напрямую в коде, можно убрать
    "REQUEST_TIMEOUT": (10, 30),
    "IMAGE_EXTENSIONS": ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'),
    "DEFAULT_ASPECT_RATIO_THRESHOLD": 1.1,
    "JPEG_QUALITY": 90,
}

# --- Фикстуры для test_logic ---

@pytest.fixture(autouse=True)
def disable_logging():
    # Отключаем логирование на время тестов, чтобы не засорять вывод
    # Используем уровень выше CRITICAL
    logging.disable(logging.CRITICAL + 10)
    yield
    logging.disable(logging.NOTSET) # Включаем обратно после теста

@pytest.fixture(autouse=True)
def mock_logic_config():
    # Патчим весь модуль config внутри logic
    with patch('src.logic.config', MagicMock(**FAKE_CONFIG_DATA)) as mock_conf:
        # Добавляем атрибуты, если они используются не только через FAKE_CONFIG_DATA
        mock_conf.DEFAULT_ASPECT_RATIO_THRESHOLD = FAKE_CONFIG_DATA['DEFAULT_ASPECT_RATIO_THRESHOLD']
        mock_conf.JPEG_QUALITY = FAKE_CONFIG_DATA['JPEG_QUALITY']
        mock_conf.IMAGE_EXTENSIONS = FAKE_CONFIG_DATA['IMAGE_EXTENSIONS']
        mock_conf.MAX_RETRIES = FAKE_CONFIG_DATA['MAX_RETRIES']
        mock_conf.REQUEST_TIMEOUT = FAKE_CONFIG_DATA['REQUEST_TIMEOUT']
        mock_conf.DEFAULT_DELAY_SECONDS = FAKE_CONFIG_DATA['DEFAULT_DELAY_SECONDS']
        yield mock_conf

@pytest.fixture
def mock_requests_session():
    with patch('src.logic.requests.Session') as MockSession:
        mock_instance = MockSession.return_value
        # Настраиваем стандартный успешный ответ
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.content = b'fakedata'
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.raise_for_status.return_value = None
        mock_instance.get.return_value = mock_response
        mock_instance.cookies = requests.cookies.RequestsCookieJar() # Используем реальный объект
        mock_instance.mount = MagicMock() # Мокаем mount
        mock_instance.headers = {} # Инициализируем headers
        yield MockSession

@pytest.fixture
def mock_shutil_copy2():
    with patch('src.logic.shutil.copy2') as mock_copy:
        yield mock_copy

@pytest.fixture
def mock_path_methods():
    # Патчим методы Path, которые используются в logic.py
    with patch('src.logic.Path.mkdir') as mock_mkdir, \
         patch('src.logic.Path.iterdir') as mock_iterdir, \
         patch('src.logic.Path.stat') as mock_stat, \
         patch('src.logic.Path.is_file') as mock_is_file, \
         patch('src.logic.Path.suffix') as mock_suffix, \
         patch('src.logic.Path.name', new_callable=MagicMock) as mock_name, \
         patch('src.logic.Path.with_suffix') as mock_with_suffix: # Добавлен with_suffix

        # Настройка mock_stat по умолчанию
        stat_result = MagicMock()
        stat_result.st_mode = stat.S_IFREG | 0o666
        stat_result.st_size = 1024 # Не пустой по умолчанию
        mock_stat.return_value = stat_result

        # Настройка mock_is_file по умолчанию
        mock_is_file.return_value = True

        # Настройка mock_suffix и mock_name по умолчанию (можно переопределить в тестах)
        mock_suffix.__get__ = MagicMock(return_value=".jpg") # Используем __get__ для свойства
        mock_name.__get__ = MagicMock(return_value="default_name.jpg")

        # Настройка mock_with_suffix
        def with_suffix_side_effect(suffix):
            # Возвращаем новый мок Path с измененным суффиксом
            new_path_mock = MagicMock(spec=Path)
            # Копируем имя и меняем суффикс (упрощенно)
            base_name = mock_name.__get__(new_path_mock, Path).rsplit('.', 1)[0]
            new_name = f"{base_name}{suffix}"
            new_path_mock.name = new_name
            new_path_mock.suffix = suffix
            new_path_mock.__str__ = MagicMock(return_value=f"/fake/path/{new_name}")
            return new_path_mock
        mock_with_suffix.side_effect = with_suffix_side_effect


        yield {
            "mkdir": mock_mkdir,
            "iterdir": mock_iterdir,
            "stat": mock_stat,
            "is_file": mock_is_file,
            "suffix": mock_suffix,
            "name": mock_name,
            "with_suffix": mock_with_suffix
        }


@pytest.fixture
def mock_pil_image():
    # Используем настоящий Image, если он доступен, иначе полный мок
    try:
        from PIL import Image as PilImage
        # Патчим только open, new, и Resampling, если нужно
        with patch('src.logic.Image.open') as mock_open, \
             patch('src.logic.Image.new') as mock_new:
            # Настройка моков для open и new
            mock_img_instance = MagicMock(spec=PilImage.Image)
            mock_img_instance.convert.return_value = mock_img_instance
            mock_img_instance.resize.return_value = mock_img_instance
            mock_img_instance.paste = MagicMock()
            mock_img_instance.save = MagicMock()
            mock_img_instance.size = (800, 1000) # Размер по умолчанию

            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_img_instance
            mock_open.return_value = mock_context
            mock_new.return_value = mock_img_instance # new тоже возвращает image

            # Создаем мок для Resampling, даже если PIL установлен
            MockImage = MagicMock()
            MockImage.open = mock_open
            MockImage.new = mock_new
            MockImage.Resampling = MagicMock()
            MockImage.Resampling.LANCZOS = PilImage.Resampling.LANCZOS if hasattr(PilImage, 'Resampling') else "LANCZOS_MOCK"

            # Патчим класс Image в logic на наш настроенный мок
            with patch('src.logic.Image', MockImage):
                 yield MockImage

    except ImportError:
        # Полный мок, если PIL не установлен
        with patch('src.logic.Image', new_callable=MagicMock) as MockImage:
            mock_img_instance = MagicMock()
            mock_img_instance.convert.return_value = mock_img_instance
            mock_img_instance.resize.return_value = mock_img_instance
            mock_img_instance.paste = MagicMock()
            mock_img_instance.save = MagicMock()
            mock_img_instance.size = (800, 1000)

            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_img_instance
            MockImage.open.return_value = mock_context
            MockImage.new.return_value = mock_img_instance
            MockImage.Resampling = MagicMock()
            MockImage.Resampling.LANCZOS = "LANCZOS_MOCK"
            yield MockImage


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
    # Патчим функции из utils, используемые в logic
    with patch('src.logic.utils.get_page_number') as mock_get_num, \
         patch('src.logic.utils.is_likely_spread') as mock_is_spread:
        # Настройка по умолчанию (можно переопределить в тестах)
        mock_get_num.return_value = -1
        mock_is_spread.return_value = False
        yield {
            "get_page_number": mock_get_num,
            "is_likely_spread": mock_is_spread
        }

@pytest.fixture
def mock_status_callback():
    return MagicMock()

@pytest.fixture
def mock_progress_callback():
    return MagicMock()

@pytest.fixture
def stop_event():
    return threading.Event()

@pytest.fixture
def handler(mock_status_callback, mock_progress_callback, stop_event):
    # Создаем экземпляр с моками
    return LibraryHandler(
        status_callback=mock_status_callback,
        progress_callback=mock_progress_callback,
        stop_event=stop_event
    )

# --- Тесты для LibraryHandler ---
class TestLibraryHandler:

    # --- Тесты _setup_session_with_retry ---
    def test_setup_session_with_retry(self, handler, mock_requests_session):
        handler._setup_session_with_retry()
        mock_session_instance = mock_requests_session.return_value
        mock_requests_session.assert_called_once()
        # ИСПРАВЛЕНО: Проверяем обновление словаря headers
        assert mock_session_instance.headers['User-Agent'] == FAKE_CONFIG_DATA['DEFAULT_USER_AGENT']
        # Проверяем вызовы mount
        mount_calls = mock_session_instance.mount.call_args_list
        assert len(mount_calls) == 2
        assert mount_calls[0] == call("https://", ANY)
        assert mount_calls[1] == call("http://", ANY)
        # Проверяем параметры Retry стратегии у адаптера
        adapter_instance = mount_calls[0].args[1]
        assert isinstance(adapter_instance, HTTPAdapter)
        retry_strategy = adapter_instance.max_retries
        assert isinstance(retry_strategy, Retry)
        assert retry_strategy.total == FAKE_CONFIG_DATA['MAX_RETRIES']
        assert set(retry_strategy.status_forcelist) == set(FAKE_CONFIG_DATA['RETRY_ON_HTTP_CODES'])
        assert retry_strategy.backoff_factor == 1
        assert set(retry_strategy.allowed_methods) == {"HEAD", "GET", "OPTIONS"}
        assert handler.session is mock_session_instance

        # Проверяем, что сессия не создается повторно
        mock_requests_session.reset_mock()
        handler._setup_session_with_retry()
        mock_requests_session.assert_not_called()

    # --- Тесты _get_initial_cookies ---
    def test_get_initial_cookies_success(self, handler, mock_requests_session, mock_status_callback):
        handler._setup_session_with_retry() # Убедимся, что сессия создана
        mock_session = mock_requests_session.return_value
        mock_response = mock_session.get.return_value # Используем мок ответа из фикстуры
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        # Имитируем установку куки сервером
        mock_session.cookies.set('sessionid', 'testcookie123', domain='fake.rgo.ru')

        result = handler._get_initial_cookies()

        assert result is True
        mock_session.get.assert_called_once_with(
            FAKE_CONFIG_DATA['INITIAL_COOKIE_URL'],
            timeout=FAKE_CONFIG_DATA['REQUEST_TIMEOUT']
        )
        mock_response.raise_for_status.assert_called_once()
        mock_status_callback.assert_any_call("Автоматическое получение сессионных куки с https://fake.rgo.ru/cookie...")
        mock_status_callback.assert_any_call("Успешно получены куки: ['sessionid']")

    def test_get_initial_cookies_no_cookies_set(self, handler, mock_requests_session, mock_status_callback):
        handler._setup_session_with_retry()
        mock_session = mock_requests_session.return_value
        mock_response = mock_session.get.return_value
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_session.cookies.clear() # Убедимся, что куки пусты

        result = handler._get_initial_cookies()

        assert result is False # ИСПРАВЛЕНО: Должно быть False, если куки не установлены
        mock_session.get.assert_called_once()
        mock_status_callback.assert_any_call("Предупреждение: Не удалось автоматически получить куки (сервер не установил?).")

    def test_get_initial_cookies_timeout(self, handler, mock_requests_session, mock_status_callback):
        handler._setup_session_with_retry()
        mock_session = mock_requests_session.return_value
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout error")

        result = handler._get_initial_cookies()

        assert result is False
        mock_session.get.assert_called_once()
        mock_status_callback.assert_any_call(f"Ошибка: Превышено время ожидания при получении куки с {FAKE_CONFIG_DATA['INITIAL_COOKIE_URL']}.")

    def test_get_initial_cookies_request_exception(self, handler, mock_requests_session, mock_status_callback):
        handler._setup_session_with_retry()
        mock_session = mock_requests_session.return_value
        error_message = "Network error"
        mock_session.get.side_effect = requests.exceptions.RequestException(error_message)

        result = handler._get_initial_cookies()

        assert result is False
        mock_session.get.assert_called_once()
        mock_status_callback.assert_any_call(f"Ошибка при получении куки: {error_message}.")

    def test_get_initial_cookies_http_error(self, handler, mock_requests_session, mock_status_callback):
        handler._setup_session_with_retry()
        mock_session = mock_requests_session.return_value
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 404
        error = requests.exceptions.HTTPError("Not Found", response=mock_response)
        mock_response.raise_for_status.side_effect = error
        mock_session.get.return_value = mock_response

        result = handler._get_initial_cookies()

        assert result is False
        mock_session.get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        mock_status_callback.assert_any_call(f"Ошибка при получении куки: {error}.")

    def test_get_initial_cookies_session_setup_fails(self, handler, mock_requests_session, mock_status_callback):
        # Имитируем ошибку при создании сессии
        mock_requests_session.side_effect = Exception("Cannot create session")
        handler.session = None # Убедимся, что сессии нет

        result = handler._get_initial_cookies()

        assert result is False
        mock_requests_session.assert_called_once() # Попытка создания была
        mock_status_callback.assert_any_call("Критическая ошибка: Не удалось создать сетевую сессию.")


    # --- Тесты download_pages ---

    # Используем фикстуру для мока _get_initial_cookies
    @pytest.fixture
    def mock_get_cookies_success(self):
        with patch.object(LibraryHandler, '_get_initial_cookies', return_value=True) as mock_method:
            yield mock_method

    @pytest.fixture
    def mock_get_cookies_fail(self):
         with patch.object(LibraryHandler, '_get_initial_cookies', return_value=False) as mock_method:
            yield mock_method

    def test_download_pages_success(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_time_sleep, mock_status_callback, mock_progress_callback):
        mock_session = mock_requests_session.return_value
        # mock_response настроен в фикстуре mock_requests_session
        # mock_path_methods["stat"] настроен в фикстуре mock_path_methods

        base_url = "https://test.com/base/"
        url_ids = "book123/"
        pdf_filename = "document.pdf"
        total_pages = 3
        output_dir = "test_output"
        output_path = Path(output_dir) # Для сравнения путей

        success_count, total_count = handler.download_pages(
            base_url, url_ids, pdf_filename, total_pages, output_dir
        )

        assert success_count == total_pages
        assert total_count == total_pages
        mock_get_cookies_success.assert_called_once()
        mock_path_methods["mkdir"].assert_called_once_with(parents=True, exist_ok=True)
        assert mock_session.get.call_count == total_pages
        assert mock_builtin_open.call_count == total_pages
        assert mock_path_methods["stat"].call_count == total_pages # Вызывается для проверки размера

        # Проверяем URL и имя файла для первой страницы
        page_string_0 = f"{pdf_filename}/0"
        page_b64_0 = base64.b64encode(page_string_0.encode('utf-8')).decode('utf-8')
        expected_url_0 = f"{base_url}{url_ids}{page_b64_0}"
        # Имя файла определяется в коде как page_<i>.<ext>, где ext из Content-Type
        expected_filename_0 = output_path / "page_000.jpeg" # Content-Type был image/jpeg

        # Проверяем вызовы для первой страницы
        mock_session.get.assert_any_call(expected_url_0, timeout=FAKE_CONFIG_DATA['REQUEST_TIMEOUT'])
        mock_builtin_open.assert_any_call(expected_filename_0, 'wb')
        # Проверяем запись контента (фиктивного)
        mock_file_handle = mock_builtin_open() # Получаем хендл файла из mock_open
        mock_file_handle.write.assert_any_call(b'fakedata')
        # Проверяем вызов stat для созданного файла
        mock_path_methods["stat"].assert_any_call() # Вызывается на объекте Path(final_output_filename)

        # Проверяем прогресс
        assert mock_progress_callback.call_count == total_pages + 1 # 0..total_pages
        mock_progress_callback.assert_has_calls([
            call(0, total_pages), call(1, total_pages), call(2, total_pages), call(3, total_pages)
        ])
        # Проверяем задержку
        assert mock_time_sleep.call_count == total_pages

        # Проверяем финальный статус
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: {total_pages} из {total_pages}.")


    def test_download_pages_interrupted(self, handler, stop_event, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_time_sleep, mock_status_callback, mock_progress_callback):
        mock_session = mock_requests_session.return_value
        # Ответ по умолчанию успешный
        total_pages = 5
        download_limit = 2 # Скачаем 2 страницы и прервем

        call_counter = 0
        def get_side_effect(*args, **kwargs):
            nonlocal call_counter
            call_counter += 1
            if call_counter > download_limit:
                # Прерываем *перед* третьим запросом
                stop_event.set()
                # Важно: нужно вызвать ошибку или вернуть что-то, чтобы цикл прервался
                # Но в коде прерывание проверяется *перед* запросом, так что можно просто вернуть мок
            return mock_session.get.return_value # Возвращаем стандартный успешный ответ

        mock_session.get.side_effect = get_side_effect

        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        # ИСПРАВЛЕНО: Ожидаем 2 успешных скачивания
        assert success_count == download_limit
        assert total_count == total_pages
        # Вызвали get дважды до прерывания
        assert mock_session.get.call_count == download_limit
        assert mock_builtin_open.call_count == download_limit
        assert mock_path_methods["stat"].call_count == download_limit
        mock_status_callback.assert_any_call("--- Скачивание прервано пользователем ---")
        # ИСПРАВЛЕНО: Ожидаем прогресс 0/5, 1/5, 2/5
        assert mock_progress_callback.call_count == download_limit + 1
        mock_progress_callback.assert_has_calls([call(i, total_pages) for i in range(download_limit + 1)])
        assert mock_time_sleep.call_count == download_limit # Успели поспать после 2х скачиваний


    def test_download_pages_http_error(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_status_callback, mock_progress_callback):
        mock_session = mock_requests_session.return_value
        total_pages = 3

        # Настраиваем ответы: OK, Error 404, OK
        mock_response_ok = MagicMock(spec=requests.Response, status_code=200, headers={'Content-Type': 'image/jpeg'}, content=b'ok')
        mock_response_ok.raise_for_status.return_value = None
        mock_response_err = MagicMock(spec=requests.Response, status_code=404)
        http_error = requests.exceptions.HTTPError("Not Found", response=mock_response_err)
        mock_response_err.raise_for_status.side_effect = http_error

        mock_session.get.side_effect = [mock_response_ok, mock_response_err, mock_response_ok]

        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        # ИСПРАВЛЕНО: Ожидаем 2 успешных скачивания (первое и третье)
        assert success_count == 2
        assert total_count == total_pages
        assert mock_session.get.call_count == 3 # Делаем 3 запроса
        assert mock_builtin_open.call_count == 2 # Открываем файл только для успешных
        assert mock_path_methods["stat"].call_count == 2 # Проверяем размер только для успешных
        # Проверяем сообщение об ошибке для второй страницы
        mock_status_callback.assert_any_call(f"Ошибка HTTP 404 на стр. 2 (после {FAKE_CONFIG_DATA['MAX_RETRIES']} попыток): Not Found")
        # Проверяем прогресс
        mock_progress_callback.assert_has_calls([call(i, total_pages) for i in range(total_pages + 1)])
        # Проверяем финальный статус
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 2 из {total_pages}.")

    def test_download_pages_http_403_error(self, handler, mock_get_cookies_success, mock_requests_session, mock_status_callback):
        """Тест HTTP 403 ошибки и специфичного сообщения в status_callback."""
        mock_session = mock_requests_session.return_value
        total_pages = 1
        mock_response_err = MagicMock(spec=requests.Response, status_code=403)
        http_error = requests.exceptions.HTTPError("Forbidden", response=mock_response_err)
        mock_response_err.raise_for_status.side_effect = http_error
        mock_session.get.return_value = mock_response_err

        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        assert success_count == 0
        mock_status_callback.assert_any_call(f"Ошибка HTTP 403 на стр. 1 (после {FAKE_CONFIG_DATA['MAX_RETRIES']} попыток): Forbidden")
        # ДОБАВЛЕНО: Проверка специфичного сообщения для 401/403
        mock_status_callback.assert_any_call("   (Возможно, сессия истекла, куки неверны или доступ запрещен)")


    def test_download_pages_empty_file(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_status_callback, mock_progress_callback):
        mock_session = mock_requests_session.return_value
        # Ответ успешный, но файл будет пустой
        mock_response = MagicMock(spec=requests.Response, status_code=200, headers={'Content-Type': 'image/gif'}, content=b'empty')
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        # Имитируем нулевой размер файла через мок stat
        mock_path_methods["stat"].return_value.st_size = 0

        total_pages = 1
        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        # ИСПРАВЛЕНО: Успешных скачиваний 0, т.к. файл пустой
        assert success_count == 0
        assert total_count == total_pages
        assert mock_builtin_open.call_count == 1 # Файл создается
        assert mock_path_methods["stat"].call_count == 1 # Размер проверяется
        # Проверяем предупреждение
        # Имя файла будет page_000.gif (т.к. Content-Type был image/gif)
        mock_status_callback.assert_any_call("Предупреждение: Файл page_000.gif пустой.")
        mock_progress_callback.assert_has_calls([call(0, 1), call(1, 1)])
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 0 из {total_pages}.")


    def test_download_pages_unknown_content_type(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods):
        mock_session = mock_requests_session.return_value
        # Неизвестный Content-Type
        mock_response = MagicMock(spec=requests.Response, status_code=200, headers={'Content-Type': 'application/octet-stream'}, content=b'data')
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        output_dir = "test_output_unknown"
        output_path = Path(output_dir)
        handler.download_pages("b/", "i/", "p", 1, output_dir)

        # Ожидаем, что будет использовано расширение .jpg по умолчанию
        expected_filename = output_path / "page_000.jpg"
        mock_builtin_open.assert_called_once_with(expected_filename, 'wb')
        assert mock_path_methods["stat"].call_count == 1 # Размер все равно проверяется

    def test_download_pages_html_response(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_path_methods, mock_status_callback):
        """Тест получения HTML вместо изображения."""
        mock_session = mock_requests_session.return_value
        html_content = b"<html><body>Error</body></html>"
        mock_response = MagicMock(spec=requests.Response, status_code=200, headers={'Content-Type': 'text/html; charset=utf-8'}, content=html_content)
        mock_response.raise_for_status.return_value = None
        mock_response.text = html_content.decode('utf-8') # Добавляем атрибут text
        mock_session.get.return_value = mock_response

        total_pages = 1
        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        assert success_count == 0
        assert mock_builtin_open.call_count == 0 # Файл не должен создаваться
        assert mock_path_methods["stat"].call_count == 0 # Размер не проверяется
        mock_status_callback.assert_any_call("Ошибка на стр. 1: Получен HTML вместо изображения. Проблема с сессией/URL?")
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 0 из {total_pages}.")

    def test_download_pages_timeout_error(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_status_callback):
        """Тест ошибки таймаута при скачивании страницы."""
        mock_session = mock_requests_session.return_value
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout during page download")

        total_pages = 1
        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        assert success_count == 0
        assert mock_builtin_open.call_count == 0
        mock_status_callback.assert_any_call(f"Ошибка: Таймаут при скачивании стр. 1 (после {FAKE_CONFIG_DATA['MAX_RETRIES']} попыток).")
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 0 из {total_pages}.")

    def test_download_pages_request_exception_error(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_status_callback):
        """Тест общей ошибки сети/сервера при скачивании страницы."""
        mock_session = mock_requests_session.return_value
        error_message = "Connection refused"
        mock_session.get.side_effect = requests.exceptions.RequestException(error_message)

        total_pages = 1
        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        assert success_count == 0
        assert mock_builtin_open.call_count == 0
        mock_status_callback.assert_any_call(f"Ошибка сети/сервера на стр. 1 (после {FAKE_CONFIG_DATA['MAX_RETRIES']} попыток): {error_message}")
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 0 из {total_pages}.")

    def test_download_pages_io_error(self, handler, mock_get_cookies_success, mock_requests_session, mock_builtin_open, mock_status_callback):
        """Тест ошибки записи файла."""
        mock_session = mock_requests_session.return_value # Успешный ответ
        error_message = "Disk full"
        # Имитируем ошибку при вызове write()
        mock_file_handle = mock_builtin_open.return_value.__enter__.return_value
        mock_file_handle.write.side_effect = IOError(error_message)

        total_pages = 1
        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        assert success_count == 0
        assert mock_builtin_open.call_count == 1 # Попытка открыть файл была
        mock_file_handle.write.assert_called_once() # Попытка записи была
        mock_status_callback.assert_any_call(f"Ошибка записи файла для стр. 1: {error_message}")
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 0 из {total_pages}.")

    def test_download_pages_mkdir_error(self, handler, mock_get_cookies_success, mock_path_methods, mock_status_callback):
        """Тест ошибки создания выходной директории."""
        error_message = "Permission denied"
        mock_path_methods["mkdir"].side_effect = OSError(error_message)

        total_pages = 1
        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out_dir_fail")

        assert success_count == 0
        assert total_count == total_pages # Общее число страниц известно
        mock_path_methods["mkdir"].assert_called_once()
        mock_status_callback.assert_any_call(f"Ошибка создания папки для страниц 'out_dir_fail': {error_message}")
        # Скачивание не должно было начаться
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 0 из {total_pages}.") # Финальный статус все равно вызывается

    def test_download_pages_b64_encode_error(self, handler, mock_get_cookies_success, mock_status_callback):
        """Тест ошибки кодирования URL в Base64 (маловероятно, но для покрытия)."""
        total_pages = 1
        pdf_filename = "doc.pdf"
        # Имитируем ошибку при кодировании
        with patch('src.logic.base64.b64encode', side_effect=Exception("Encoding failed")):
            success_count, total_count = handler.download_pages("b/", "i/", pdf_filename, total_pages, "out")

        assert success_count == 0
        mock_status_callback.assert_any_call("Ошибка кодирования URL для стр. 1: Encoding failed")
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: 0 из {total_pages}.")

    def test_download_pages_no_initial_cookies(self, handler, mock_get_cookies_fail, mock_requests_session, mock_status_callback):
        """Тест продолжения скачивания, если не удалось получить куки."""
        mock_session = mock_requests_session.return_value # Успешный ответ по умолчанию
        total_pages = 1

        success_count, total_count = handler.download_pages("b/", "i/", "p", total_pages, "out")

        assert success_count == total_pages # Скачивание должно пройти успешно
        mock_get_cookies_fail.assert_called_once()
        mock_status_callback.assert_any_call("Продолжаем без автоматических куки (могут быть проблемы)...")
        assert mock_session.get.call_count == total_pages
        mock_status_callback.assert_any_call(f"Скачивание завершено. Успешно: {total_pages} из {total_pages}.")


    # --- Тесты process_images ---

    def _setup_mock_files(self, mock_path_methods, mock_utils, file_list):
        """Вспомогательная функция для настройки моков файлов."""
        mock_files = []
        page_num_map = {}
        is_spread_map = {}

        for name, page_num, is_spread, is_file in file_list:
            mock_file = MagicMock(spec=Path)
            mock_file.name = name
            mock_file.suffix = Path(name).suffix
            mock_file.__str__ = MagicMock(return_value=f"/fake/input/{name}")
            mock_file.is_file.return_value = is_file
            mock_files.append(mock_file)
            if page_num != -1:
                page_num_map[name] = page_num
            is_spread_map[mock_file] = is_spread # Используем объект файла как ключ

        mock_path_methods["iterdir"].return_value = mock_files
        mock_utils["get_page_number"].side_effect = lambda fname: page_num_map.get(fname, -1)
        # Используем объект файла для is_likely_spread
        mock_utils["is_likely_spread"].side_effect = lambda fpath, threshold: is_spread_map.get(fpath, False)

        return mock_files # Возвращаем список моков файлов

    def test_process_images_copy_cover_and_spread(self, handler, mock_path_methods, mock_shutil_copy2, mock_utils, mock_status_callback, mock_progress_callback):
        input_folder = "test_input"
        output_folder = "test_output"
        output_path = Path(output_folder)

        # Список файлов: (имя, номер_стр, это_разворот?, это_файл?)
        files_setup = [
            ("page_000.jpg", 0, False, True), # Обложка (не разворот по определению)
            ("page_001.png", 1, False, True), # Одиночная (копируется, т.к. перед разворотом)
            ("page_002_spread.gif", 2, True, True), # Готовый разворот
            ("not_an_image.txt", -1, False, True), # Не изображение (пропускается)
            ("page_003.bmp", 3, False, True), # Одиночная (копируется, т.к. последняя)
            ("subdir", -1, False, False), # Не файл (пропускается)
        ]
        mock_files = self._setup_mock_files(mock_path_methods, mock_utils, files_setup)

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        # ИСПРАВЛЕНО: Ожидаем 4 обработанных файла (0, 1, 2, 3)
        assert processed_count == 4
        assert created_spread_count == 0 # Только копирование
        mock_path_methods["mkdir"].assert_called_once_with(parents=True, exist_ok=True)
        mock_path_methods["iterdir"].assert_called_once()

        # Проверяем вызовы is_likely_spread (вызывается для всех, кроме первого)
        assert mock_utils["is_likely_spread"].call_count == 3
        mock_utils["is_likely_spread"].assert_has_calls([
            call(mock_files[1], FAKE_CONFIG_DATA['DEFAULT_ASPECT_RATIO_THRESHOLD']), # page_001.png
            call(mock_files[2], FAKE_CONFIG_DATA['DEFAULT_ASPECT_RATIO_THRESHOLD']), # page_002_spread.gif
            call(mock_files[4], FAKE_CONFIG_DATA['DEFAULT_ASPECT_RATIO_THRESHOLD']), # page_003.bmp
        ], any_order=False) # Порядок важен

        # Проверяем вызовы copy2
        assert mock_shutil_copy2.call_count == 4
        mock_shutil_copy2.assert_has_calls([
            call(mock_files[0], output_path / "spread_000.jpg"), # Обложка
            call(mock_files[1], output_path / "spread_001.png"), # Одиночная перед разворотом
            call(mock_files[2], output_path / "spread_002.gif"), # Готовый разворот
            call(mock_files[4], output_path / "spread_003.bmp"), # Последняя одиночная
        ])

        # Проверяем прогресс (всего 4 нумерованных файла)
        total_numbered = 4
        assert mock_progress_callback.call_count == total_numbered + 1
        mock_progress_callback.assert_has_calls([
             call(0, total_numbered), # Старт
             call(1, total_numbered), # После стр 0
             call(2, total_numbered), # После стр 1
             call(3, total_numbered), # После стр 2
             call(4, total_numbered)  # После стр 3
        ])
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 4. Создано разворотов: 0.")


    def test_process_images_merge_two_singles(self, handler, mock_path_methods, mock_shutil_copy2, mock_pil_image, mock_utils, mock_status_callback, mock_progress_callback):
        input_folder = "test_input_merge"
        output_folder = "test_output_merge"
        output_path = Path(output_folder)

        files_setup = [
            ("page_000_cover.jpg", 0, False, True), # Обложка
            ("page_001_left.png", 1, False, True),  # Левая одиночная
            ("page_002_right.bmp", 2, False, True), # Правая одиночная
        ]
        mock_files = self._setup_mock_files(mock_path_methods, mock_utils, files_setup)

        # Настраиваем моки PIL
        mock_img_left = MagicMock(size=(800, 1000))
        mock_img_left.convert.return_value = mock_img_left
        mock_img_right = MagicMock(size=(800, 1000))
        mock_img_right.convert.return_value = mock_img_right
        mock_img_cover = MagicMock(size=(800, 1000)) # Не используется для склейки

        def mock_image_open_side_effect(path):
            mock_context = MagicMock()
            # Сравниваем по строковому представлению пути
            path_str = str(path)
            if str(mock_files[1]) in path_str: mock_context.__enter__.return_value = mock_img_left
            elif str(mock_files[2]) in path_str: mock_context.__enter__.return_value = mock_img_right
            elif str(mock_files[0]) in path_str: mock_context.__enter__.return_value = mock_img_cover
            else: raise FileNotFoundError(f"Unexpected path in Image.open: {path_str}")
            return mock_context
        mock_pil_image.open.side_effect = mock_image_open_side_effect

        mock_spread_img = mock_pil_image.new.return_value # Мок для нового изображения

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        # ИСПРАВЛЕНО: Ожидаем 3 обработанных файла (1 скопирован, 2 склеены)
        assert processed_count == 3
        assert created_spread_count == 1 # 1 разворот создан
        assert mock_utils["is_likely_spread"].call_count == 2 # Проверяем стр 1 и 2

        # Копируем обложку
        mock_shutil_copy2.assert_called_once_with(mock_files[0], output_path / "spread_000.jpg")

        # Проверяем открытие файлов для склейки
        mock_pil_image.open.assert_has_calls([call(mock_files[1]), call(mock_files[2])], any_order=True)
        # Проверяем создание нового изображения
        mock_pil_image.new.assert_called_once_with('RGB', (1600, 1000), (255, 255, 255))
        # Проверяем вставку изображений
        mock_spread_img.paste.assert_has_calls([
            call(mock_img_left, (0, 0)),
            call(mock_img_right, (800, 0))
        ])
        # Проверяем сохранение разворота
        expected_spread_filename = output_path / "spread_001-002.jpg"
        mock_spread_img.save.assert_called_once_with(
            expected_spread_filename, "JPEG", quality=FAKE_CONFIG_DATA['JPEG_QUALITY'], optimize=True
        )

        # Проверяем прогресс (3 файла)
        total_numbered = 3
        assert mock_progress_callback.call_count == 3 # 0/3, 1/3 (после обложки), 3/3 (после склейки)
        mock_progress_callback.assert_has_calls([
            call(0, total_numbered), call(1, total_numbered), call(3, total_numbered)
        ])
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 3. Создано разворотов: 1.")


    def test_process_images_merge_different_heights(self, handler, mock_path_methods, mock_pil_image, mock_utils, mock_shutil_copy2):
        input_folder = "test_input_resize"
        output_folder = "test_output_resize"
        output_path = Path(output_folder)

        files_setup = [
            ("page_001_short.png", 1, False, True), # Левая, ниже
            ("page_002_tall.bmp", 2, False, True),  # Правая, выше
        ]
        mock_files = self._setup_mock_files(mock_path_methods, mock_utils, files_setup)

        # Настраиваем моки PIL с разными размерами
        mock_img_left = MagicMock(size=(800, 1000))
        mock_img_left.convert.return_value = mock_img_left
        mock_img_right = MagicMock(size=(820, 1100)) # Выше
        mock_img_right.convert.return_value = mock_img_right

        # Мок для измененного левого изображения
        mock_resized_left = MagicMock(size=(int(800 * 1.1), 1100)) # Ожидаемый размер после resize
        mock_resized_left.convert.return_value = mock_resized_left
        mock_img_left.resize.return_value = mock_resized_left # resize левого вернет этот мок

        def mock_image_open_side_effect(path):
            mock_context = MagicMock()
            path_str = str(path)
            if str(mock_files[0]) in path_str: mock_context.__enter__.return_value = mock_img_left
            elif str(mock_files[1]) in path_str: mock_context.__enter__.return_value = mock_img_right
            else: raise FileNotFoundError(f"Unexpected path in Image.open: {path_str}")
            return mock_context
        mock_pil_image.open.side_effect = mock_image_open_side_effect

        mock_spread_img = mock_pil_image.new.return_value

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        # ИСПРАВЛЕНО: Ожидаем 2 обработанных файла (склеены)
        assert processed_count == 2
        assert created_spread_count == 1

        # Проверяем, что обложка не копировалась
        mock_shutil_copy2.assert_not_called()

        # Проверяем resize левого изображения до высоты правого (1100)
        target_height = 1100
        ratio_left = target_height / 1000
        expected_w_left = int(800 * ratio_left)
        mock_img_left.resize.assert_called_once_with((expected_w_left, target_height), mock_pil_image.Resampling.LANCZOS)
        mock_img_right.resize.assert_not_called() # Правое не меняется

        # Проверяем создание нового изображения с максимальной высотой
        total_width = expected_w_left + 820 # Ширина измененного левого + ширина правого
        mock_pil_image.new.assert_called_once_with('RGB', (total_width, target_height), (255, 255, 255))

        # Проверяем вставку (измененного левого и оригинального правого)
        mock_spread_img.paste.assert_has_calls([
            call(mock_resized_left, (0, 0)), # Вставляем измененное левое
            call(mock_img_right, (expected_w_left, 0)) # Вставляем правое со смещением
        ])
        mock_spread_img.save.assert_called_once() # Проверяем сохранение


    def test_process_images_single_then_spread(self, handler, mock_path_methods, mock_shutil_copy2, mock_utils):
        """Тест: одиночная страница, за которой следует разворот."""
        input_folder = "test_input_single_spread"
        output_folder = "test_output_single_spread"
        output_path = Path(output_folder)

        files_setup = [
            ("page_001_single.jpg", 1, False, True), # Одиночная
            ("page_002_spread.png", 2, True, True),  # Разворот
        ]
        mock_files = self._setup_mock_files(mock_path_methods, mock_utils, files_setup)

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 2 # Оба файла обработаны (скопированы)
        assert created_spread_count == 0 # Ничего не создано

        # Проверяем копирование обоих файлов
        assert mock_shutil_copy2.call_count == 2
        mock_shutil_copy2.assert_has_calls([
            call(mock_files[0], output_path / "spread_001.jpg"), # Копируем одиночную
            call(mock_files[1], output_path / "spread_002.png"), # Копируем разворот
        ])


    def test_process_images_last_single(self, handler, mock_path_methods, mock_shutil_copy2, mock_utils):
        """Тест: последняя страница является одиночной."""
        input_folder = "test_input_last_single"
        output_folder = "test_output_last_single"
        output_path = Path(output_folder)

        files_setup = [
             ("page_001_single.jpg", 1, False, True), # Одиночная - последняя
        ]
        mock_files = self._setup_mock_files(mock_path_methods, mock_utils, files_setup)

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 1 # Обработан один файл
        assert created_spread_count == 0

        # Проверяем копирование этого файла
        mock_shutil_copy2.assert_called_once_with(mock_files[0], output_path / "spread_001.jpg")


    def test_process_images_input_dir_not_found(self, handler, mock_path_methods, mock_shutil_copy2, mock_pil_image, mock_status_callback):
        input_folder = "non_existent"
        output_folder = "test_output"
        # Имитируем ошибку при вызове iterdir
        mock_path_methods["iterdir"].side_effect = FileNotFoundError(f"Dir not found: {input_folder}")

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0
        assert created_spread_count == 0
        mock_path_methods["mkdir"].assert_called_once() # Попытка создать выходную папку была
        mock_path_methods["iterdir"].assert_called_once() # Попытка прочитать входную была
        mock_status_callback.assert_any_call(f"Ошибка: Папка со страницами '{input_folder}' не найдена.")
        mock_shutil_copy2.assert_not_called()
        mock_pil_image.open.assert_not_called()
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 0. Создано разворотов: 0.")


    def test_process_images_input_dir_read_error(self, handler, mock_path_methods, mock_status_callback):
        """Тест ошибки чтения входной директории (не FileNotFoundError)."""
        input_folder = "input_permission_denied"
        output_folder = "test_output"
        error_message = "Permission denied"
        mock_path_methods["iterdir"].side_effect = OSError(error_message)

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0
        assert created_spread_count == 0
        mock_path_methods["mkdir"].assert_called_once()
        mock_path_methods["iterdir"].assert_called_once()
        mock_status_callback.assert_any_call(f"Ошибка чтения папки '{input_folder}': {error_message}")
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 0. Создано разворотов: 0.")


    def test_process_images_empty_input_dir(self, handler, mock_path_methods, mock_status_callback):
        input_folder = "empty_input"
        output_folder = "test_output"
        # iterdir возвращает пустой список
        self._setup_mock_files(mock_path_methods, mock_utils, []) # Передаем пустой список

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0
        assert created_spread_count == 0
        mock_path_methods["mkdir"].assert_called_once()
        mock_path_methods["iterdir"].assert_called_once()
        # ИСПРАВЛЕНО: Проверяем правильное сообщение
        mock_status_callback.assert_any_call("В папке не найдено подходящих файлов изображений с номерами.")
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 0. Создано разворотов: 0.")


    def test_process_images_no_numbered_files(self, handler, mock_path_methods, mock_utils, mock_status_callback):
        """Тест, когда в папке есть файлы, но без номеров."""
        input_folder = "input_no_numbers"
        output_folder = "test_output"
        files_setup = [
            ("cover.jpg", -1, False, True),
            ("image_no_num.png", -1, False, True),
        ]
        self._setup_mock_files(mock_path_methods, mock_utils, files_setup)

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0
        assert created_spread_count == 0
        mock_path_methods["iterdir"].assert_called_once()
        # get_page_number будет вызван для обоих файлов
        assert mock_utils["get_page_number"].call_count == 2
        mock_status_callback.assert_any_call("В папке не найдено подходящих файлов изображений с номерами.")
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 0. Создано разворотов: 0.")


    def test_process_images_interrupted(self, handler, stop_event, mock_path_methods, mock_shutil_copy2, mock_pil_image, mock_utils, mock_status_callback, mock_progress_callback):
        input_folder = "test_input_interrupt"
        output_folder = "test_output_interrupt"

        files_setup = [
            ("page_000.jpg", 0, False, True), # Обложка
            ("page_001.png", 1, False, True), # Одиночная
            ("page_002.bmp", 2, False, True), # Одиночная
        ]
        mock_files = self._setup_mock_files(mock_path_methods, mock_utils, files_setup)

        # Имитируем остановку *после* копирования первого файла (обложки)
        original_copy = mock_shutil_copy2.side_effect
        copy_call_count = 0
        def stop_on_copy(*args, **kwargs):
            nonlocal copy_call_count
            copy_call_count += 1
            if copy_call_count >= 1: # Останавливаем после первого же копирования
                stop_event.set()
            if original_copy:
                 return original_copy(*args, **kwargs)
            return None
        mock_shutil_copy2.side_effect = stop_on_copy

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        # ИСПРАВЛЕНО: Успели обработать только обложку (1 файл)
        assert processed_count == 1
        assert created_spread_count == 0
        mock_shutil_copy2.assert_called_once() # Скопировали только обложку
        mock_pil_image.open.assert_not_called() # До склейки не дошли
        mock_status_callback.assert_any_call("--- Обработка прервана пользователем ---")

        # Проверяем прогресс (3 файла всего)
        total_numbered = 3
        # Прогресс: 0/3 (старт), 1/3 (после обложки)
        assert mock_progress_callback.call_count == 2
        mock_progress_callback.assert_has_calls([call(0, total_numbered), call(1, total_numbered)])
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 1. Создано разворотов: 0.")


    def test_process_images_copy_error(self, handler, mock_path_methods, mock_shutil_copy2, mock_utils, mock_status_callback):
        """Тест ошибки при копировании файла."""
        input_folder = "test_input_copy_err"
        output_folder = "test_output_copy_err"

        files_setup = [ ("page_000.jpg", 0, False, True) ] # Только обложка
        mock_files = self._setup_mock_files(mock_path_methods, mock_utils, files_setup)

        error_message = "Permission denied on output"
        mock_shutil_copy2.side_effect = Exception(error_message)

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0 # Файл не был успешно обработан
        assert created_spread_count == 0
        mock_shutil_copy2.assert_called_once() # Попытка копирования была
        mock_status_callback.assert_any_call(f"Ошибка при копировании {mock_files[0].name}: {error_message}")
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 0. Создано разворотов: 0.")


    def test_process_images_merge_error(self, handler, mock_path_methods, mock_pil_image, mock_utils, mock_status_callback):
        """Тест ошибки при склейке изображений (например, Image.open или save)."""
        input_folder = "test_input_merge_err"
        output_folder = "test_output_merge_err"

        files_setup = [
            ("page_001.png", 1, False, True),
            ("page_002_corrupt.bmp", 2, False, True), # Этот файл вызовет ошибку
        ]
        mock_files = self._setup_mock_files(mock_path_methods, mock_utils, files_setup)

        # Имитируем ошибку при открытии второго файла
        error_message = "Cannot identify image file"
        mock_img_left = MagicMock(size=(800, 1000))
        mock_img_left.convert.return_value = mock_img_left

        def mock_image_open_side_effect(path):
            mock_context = MagicMock()
            path_str = str(path)
            if str(mock_files[0]) in path_str:
                mock_context.__enter__.return_value = mock_img_left
            elif str(mock_files[1]) in path_str:
                raise Image.UnidentifiedImageError(error_message) # Ошибка при открытии второго
            else:
                 raise FileNotFoundError()
            return mock_context
        mock_pil_image.open.side_effect = mock_image_open_side_effect

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        # ИСПРАВЛЕНО: Оба файла считаются "обработанными" в смысле прохода по циклу,
        # но разворот не создан. processed_increment будет 2 из-за ошибки.
        assert processed_count == 2
        assert created_spread_count == 0 # Разворот не создан
        mock_pil_image.open.assert_has_calls([call(mock_files[0]), call(mock_files[1])])
        mock_pil_image.new.assert_not_called() # До создания нового не дошло
        mock_status_callback.assert_any_call(
            f"Ошибка при создании разворота для {mock_files[0].name} и {mock_files[1].name}: {error_message}"
        )
        mock_status_callback.assert_any_call(f"Обработка завершена. Обработано/скопировано: 2. Создано разворотов: 0.")

    def test_process_images_output_mkdir_error(self, handler, mock_path_methods, mock_status_callback):
        """Тест ошибки создания выходной директории в process_images."""
        input_folder = "test_input_out_mkdir"
        output_folder = "test_output_out_mkdir_fail"
        error_message = "Cannot create output dir"
        mock_path_methods["mkdir"].side_effect = OSError(error_message)

        # Не важно, какие файлы на входе, т.к. ошибка до их чтения
        mock_path_methods["iterdir"].return_value = []

        processed_count, created_spread_count = handler.process_images(input_folder, output_folder)

        assert processed_count == 0
        assert created_spread_count == 0
        mock_path_methods["mkdir"].assert_called_once()
        mock_status_callback.assert_any_call(f"Ошибка создания папки для разворотов '{output_folder}': {error_message}")
        mock_path_methods["iterdir"].assert_not_called() # До чтения файлов не доходит
        # Финальный статус не вызывается, т.к. выход происходит раньше