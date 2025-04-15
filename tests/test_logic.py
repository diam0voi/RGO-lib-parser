# tests/test_logic.py
import base64
import logging
import threading
import time
from pathlib import Path
# Убрал ANY, т.к. логгер мокается целиком
from unittest.mock import MagicMock, call # , ANY

import pytest
import requests
from requests.adapters import HTTPAdapter
# Добавил импорт RequestsCookieJar для spec
from requests.cookies import RequestsCookieJar
from urllib3.util.retry import Retry

# Импортируем тестируемый модуль и его зависимости, которые будем мокать
from src import logic, config, image_processing, utils
from src.types import StatusCallback, ProgressCallback

# Фикстуры для общих нужд
@pytest.fixture
def mock_callbacks(mocker):
    """Фикстура для создания моков колбэков и стоп-ивента."""
    return {
        "status_callback": mocker.MagicMock(spec=StatusCallback),
        "progress_callback": mocker.MagicMock(spec=ProgressCallback),
        "stop_event": mocker.MagicMock(spec=threading.Event),
    }

@pytest.fixture
def library_handler(mock_callbacks, mocker):
    """Фикстура для создания экземпляра LibraryHandler с моками."""
    # Мокаем логгер модуля *до* инициализации handler
    # Это гарантирует, что handler использует наш мок логгера
    mocker.patch("src.logic.logger", MagicMock(spec=logging.Logger))

    mock_callbacks["stop_event"].is_set.return_value = False
    handler = logic.LibraryHandler(
        status_callback=mock_callbacks["status_callback"],
        progress_callback=mock_callbacks["progress_callback"],
        stop_event=mock_callbacks["stop_event"],
    )
    return handler

@pytest.fixture
def mock_session(mocker):
    """Фикстура для мока requests.Session."""
    mock_sess = mocker.MagicMock(spec=requests.Session)
    mock_sess.headers = {}
    # Исправлена опечатка: mockerMagicMock -> mocker.MagicMock
    mock_sess.cookies = mocker.MagicMock(spec=RequestsCookieJar) # Мок для куки джара

    # Настраиваем мок ответа
    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.content = b"fake image data"
    mock_response.headers = {'Content-Type': 'image/jpeg'}
    mock_response.raise_for_status = mocker.MagicMock() # По умолчанию не рейзит ошибку
    # Устанавливаем get метод сессии, чтобы он возвращал мок ответа
    mock_sess.get.return_value = mock_response

    # Мокаем сам requests.Session, чтобы он возвращал наш мок
    mocker.patch("src.logic.requests.Session", return_value=mock_sess)
    # Мокаем Retry и HTTPAdapter, чтобы _setup_session_with_retry не упал
    mocker.patch("src.logic.Retry", spec=Retry)
    mocker.patch("src.logic.HTTPAdapter", spec=HTTPAdapter)
    return mock_sess

@pytest.fixture
def mock_path(mocker):
    """Фикстура для мока pathlib.Path."""
    mock_p = mocker.patch("src.logic.Path", spec=Path)
    mock_instance = mocker.MagicMock(spec=Path)
    mock_instance.mkdir = mocker.MagicMock()
    # Используем mocker.mock_open для имитации контекстного менеджера файла
    mock_open_func = mocker.mock_open()
    mock_instance.open = mock_open_func
    # Настраиваем stat().st_size
    mock_stat_result = mocker.MagicMock()
    mock_stat_result.st_size = 100 # По умолчанию файл не пустой
    mock_instance.stat.return_value = mock_stat_result
    # Настраиваем with_suffix
    mock_instance.with_suffix.return_value = mock_instance # Возвращаем тот же мок
    mock_instance.name = "mock_file.jpg"
    mock_p.return_value = mock_instance
    # Добавим возможность проверять вызовы open
    mock_p.mock_open_func = mock_open_func
    return mock_p

@pytest.fixture
def mock_dependencies(mocker):
    """Фикстура для мока других зависимостей (кроме логгера)."""
    mocker.patch("src.logic.time.sleep")
    # Оставляем реальный base64, т.к. его ошибка тестируется отдельно
    # mocker.patch("src.logic.base64.b64encode", side_effect=lambda x: base64.b64encode(x))
    mocker.patch("src.logic.image_processing.process_images_in_folders", return_value=(10, 5))
    # Убрали патчинг логгера отсюда
    # mocker.patch("src.logic.logger", MagicMock(spec=logging.Logger))

# --- Тесты ---

class TestLibraryHandler:

    # Используем фикстуру library_handler, которая уже мокает логгер
    def test_init(self, library_handler, mock_callbacks):
        """Тест инициализации LibraryHandler."""
        status_cb = mock_callbacks["status_callback"]
        progress_cb = mock_callbacks["progress_callback"]
        stop_ev = mock_callbacks["stop_event"]

        # Проверяем установку атрибутов
        assert library_handler.status_callback is status_cb
        assert library_handler.progress_callback is progress_cb
        assert library_handler.stop_event is stop_ev
        assert library_handler.session is None

        # Проверяем вызов логгера (теперь он замокан фикстурой library_handler)
        logic.logger.info.assert_called_once_with("LibraryHandler initialized")

    # Добавляем mock_session в аргументы, т.к. он нужен для _setup_session_with_retry
    def test_setup_session_with_retry_new(self, library_handler, mock_session, mocker):
        """Тест создания новой сессии."""
        library_handler.session = None
        library_handler._setup_session_with_retry()

        assert library_handler.session is mock_session
        mock_session.headers.update.assert_called_once_with({'User-Agent': config.DEFAULT_USER_AGENT})
        logic.Retry.assert_called_once_with(
            total=config.MAX_RETRIES,
            status_forcelist=config.RETRY_ON_HTTP_CODES,
            backoff_factor=1,
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        logic.HTTPAdapter.assert_called_once_with(max_retries=logic.Retry.return_value)
        assert mock_session.mount.call_count == 2
        mock_session.mount.assert_any_call("https://", logic.HTTPAdapter.return_value)
        mock_session.mount.assert_any_call("http://", logic.HTTPAdapter.return_value)
        # Проверяем вызов логгера
        logic.logger.info.assert_called_with(f"Requests session created with retry strategy (max={config.MAX_RETRIES}, statuses={config.RETRY_ON_HTTP_CODES})")

    # Добавляем mock_session в аргументы
    def test_setup_session_with_retry_existing(self, library_handler, mock_session, mocker):
        """Тест повторного вызова _setup_session_with_retry с существующей сессией."""
        library_handler.session = mock_session
        library_handler._setup_session_with_retry()

        # Проверяем, что Session() не вызывался (т.к. сессия уже есть)
        logic.requests.Session.assert_not_called()
        mock_session.mount.assert_not_called()
        logic.logger.debug.assert_called_once_with("Session already exists. Reusing.")

    # Добавляем mock_session в аргументы
    def test_get_initial_cookies_success(self, library_handler, mock_session, mock_callbacks):
        """Тест успешного получения куки."""
        # Настраиваем мок сессии для возврата куки
        # Используем set для имитации добавления куки
        mock_session.cookies.keys.return_value = ["session_id"]
        mock_session.cookies.__bool__ = lambda: True # Делаем мок куки "истинным"

        result = library_handler._get_initial_cookies()

        assert result is True
        mock_session.get.assert_called_once_with(config.INITIAL_COOKIE_URL, timeout=config.REQUEST_TIMEOUT)
        mock_session.get.return_value.raise_for_status.assert_called_once()
        mock_callbacks["status_callback"].assert_any_call(f"Автоматическое получение сессионных куки с {config.INITIAL_COOKIE_URL}...")
        mock_callbacks["status_callback"].assert_any_call("Успешно получены куки: ['session_id']")
        logic.logger.info.assert_any_call(f"Attempting to get initial cookies from {config.INITIAL_COOKIE_URL}")
        logic.logger.info.assert_any_call("Initial cookies obtained: ['session_id']")

    # Добавляем mock_session в аргументы
    def test_get_initial_cookies_no_cookies_set(self, library_handler, mock_session, mock_callbacks):
        """Тест случая, когда сервер не установил куки."""
        mock_session.cookies.keys.return_value = [] # Нет ключей
        mock_session.cookies.__bool__ = lambda: False # Мок куки "ложный"

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_session.get.assert_called_once_with(config.INITIAL_COOKIE_URL, timeout=config.REQUEST_TIMEOUT)
        mock_callbacks["status_callback"].assert_any_call("Предупреждение: Не удалось автоматически получить куки (сервер не установил?).")
        logic.logger.warning.assert_called_once_with("Server did not set any cookies during initial request.")

    # Добавляем mock_session в аргументы
    def test_get_initial_cookies_timeout(self, library_handler, mock_session, mock_callbacks):
        """Тест таймаута при получении куки."""
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout error")

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка: Превышено время ожидания при получении куки с {config.INITIAL_COOKIE_URL}.")
        logic.logger.error.assert_called_once_with(f"Ошибка: Превышено время ожидания при получении куки с {config.INITIAL_COOKIE_URL}.")

    # Добавляем mock_session в аргументы
    def test_get_initial_cookies_request_exception(self, library_handler, mock_session, mock_callbacks):
        """Тест другой ошибки запроса при получении куки."""
        error_msg = "Connection failed"
        mock_session.get.side_effect = requests.exceptions.RequestException(error_msg)

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка при получении куки: {error_msg}.")
        logic.logger.error.assert_called_once_with(f"Error getting initial cookies: {error_msg}", exc_info=True)

    # Добавляем mock_session в аргументы
    def test_get_initial_cookies_http_error(self, library_handler, mock_session, mock_callbacks):
        """Тест HTTP ошибки (4xx/5xx) при получении куки."""
        mock_response = mock_session.get.return_value
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка при получении куки: 404 Client Error.")
        logic.logger.error.assert_called_once_with("Error getting initial cookies: 404 Client Error", exc_info=True)

    # mock_session здесь не нужен, т.к. ошибка до его использования
    def test_get_initial_cookies_session_setup_fails(self, library_handler, mock_callbacks, mocker):
        """Тест ошибки при настройке сессии во время получения куки."""
        mocker.patch.object(library_handler, '_setup_session_with_retry', side_effect=Exception("Setup failed"))
        library_handler.session = None

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call("Критическая ошибка при настройке сессии: Setup failed")
        logic.logger.error.assert_called_with("Failed to setup session during cookie retrieval: Setup failed", exc_info=True)

    # mock_session здесь не нужен
    def test_get_initial_cookies_session_setup_returns_none(self, library_handler, mock_callbacks, mocker):
        """Тест, когда _setup_session_with_retry не создает сессию (гипотетический случай)."""
        mocker.patch.object(library_handler, '_setup_session_with_retry')
        library_handler.session = None

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call("Критическая ошибка: Не удалось создать сетевую сессию.")
        logic.logger.error.assert_called_with("Failed to setup session in _get_initial_cookies")


    # --- Тесты download_pages ---

    # Добавляем mock_session в аргументы
    @pytest.mark.usefixtures("mock_dependencies") # mock_path не нужен в usefixtures, если он в аргументах
    def test_download_pages_success(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест успешного скачивания всех страниц."""
        base_url = "http://example.com/books"
        url_ids = "123/456"
        filename_pdf = "my_book.pdf"
        total_pages = 3
        output_dir = "test_output"

        # Мокаем _get_initial_cookies
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages(
            base_url, url_ids, filename_pdf, total_pages, output_dir
        )

        assert success_count == total_pages
        assert total_count == total_pages

        mock_path.assert_called_once_with(output_dir)
        mock_path.return_value.mkdir.assert_called_once_with(parents=True, exist_ok=True)

        assert mock_callbacks["status_callback"].call_count >= total_pages + 3
        mock_callbacks["status_callback"].assert_any_call(f"Начинаем скачивание {total_pages} страниц в '{output_dir}'...")
        # ... (остальные проверки колбэков)

        assert mock_callbacks["progress_callback"].call_count == total_pages + 1
        # ... (остальные проверки колбэков)

        assert mock_session.get.call_count == total_pages
        # ... (остальные проверки вызовов get)

        # Проверяем запись в файлы через мок open из mock_path
        assert mock_path.mock_open_func.call_count == total_pages
        # Проверяем вызов write
        mock_path.mock_open_func().write.assert_called_with(b"fake image data")
        # Проверяем вызов with_suffix
        assert mock_path.return_value.with_suffix.call_count == total_pages
        mock_path.return_value.with_suffix.assert_called_with(".jpeg")

        assert logic.time.sleep.call_count == total_pages

    # mock_session и mock_path здесь не нужны
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_session_setup_fails(self, library_handler, mock_callbacks, mocker):
        """Тест ошибки создания сессии перед скачиванием."""
        mocker.patch.object(library_handler, '_setup_session_with_retry')
        library_handler.session = None

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 5, "out")

        assert success_count == 0
        assert total_count == 5
        mock_callbacks["status_callback"].assert_any_call("Критическая ошибка: Не удалось создать сетевую сессию для скачивания.")
        logic.logger.error.assert_called_with("Failed to setup session for download.")

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_no_cookies_warning(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест продолжения скачивания после неудачного получения куки."""
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=False)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 1, "out")

        assert success_count == 1
        assert total_count == 1
        mock_callbacks["status_callback"].assert_any_call("Продолжаем без автоматических куки (могут быть проблемы)...")
        logic.logger.warning.assert_called_with("Proceeding with download without initial cookies.")
        assert mock_session.get.call_count == 1

    # Добавляем mock_path, mock_session не нужен (ошибка до него)
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_mkdir_error(self, library_handler, mock_callbacks, mock_path, mocker):
        """Тест ошибки создания выходной папки."""
        error_msg = "Permission denied"
        mock_path.return_value.mkdir.side_effect = OSError(error_msg)
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 5, "out_dir")

        assert success_count == 0
        assert total_count == 5
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка создания папки для страниц 'out_dir': {error_msg}")
        logic.logger.error.assert_called_with(f"Ошибка создания папки для страниц 'out_dir': {error_msg}", exc_info=True)

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_stop_event(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест прерывания скачивания по stop_event."""
        total_pages = 5
        stop_at_page = 2

        call_count = 0
        def stop_side_effect():
            nonlocal call_count
            call_count += 1
            # is_set должен вернуть True на проверке *перед* запросом страницы с индексом stop_at_page
            # Цикл идет от 0 до total_pages-1.
            # i=0 -> call_count=1 -> False
            # i=1 -> call_count=2 -> False
            # i=2 -> call_count=3 -> True (останавливаемся перед запросом стр 3, индекс 2)
            return call_count > stop_at_page

        mock_callbacks["stop_event"].is_set.side_effect = stop_side_effect
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", total_pages, "out")

        # Успешно скачали страницы с индексами 0 и 1
        assert success_count == stop_at_page
        assert total_count == total_pages
        # Запросили только страницы 0 и 1
        assert mock_session.get.call_count == stop_at_page
        mock_callbacks["status_callback"].assert_any_call("--- Скачивание прервано пользователем ---")
        logic.logger.info.assert_called_with("Download interrupted by user.")
        # Прогресс вызван для 0, 1, 2 (i+1)
        assert mock_callbacks["progress_callback"].call_count == stop_at_page + 1
        mock_callbacks["progress_callback"].assert_any_call(stop_at_page, total_pages) # Последний вызванный прогресс
        # sleep вызван после страниц 0 и 1
        assert logic.time.sleep.call_count == stop_at_page

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_b64_encode_error(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест ошибки при кодировании URL в base64."""
        error_msg = "Encoding failed"
        mocker.patch("src.logic.base64.b64encode", side_effect=Exception(error_msg))
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 1, "out")

        assert success_count == 0
        assert total_count == 1
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка кодирования URL для стр. 1: {error_msg}")
        logic.logger.error.assert_called_with(f"Ошибка кодирования URL для стр. 1: {error_msg}", exc_info=True)
        # Убедимся, что get не вызывался, так как ошибка произошла до него
        library_handler.session.get.assert_not_called() # Теперь должно работать!

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_http_error(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест ошибки HTTP 404 при скачивании страницы."""
        total_pages = 2
        mock_response_ok = MagicMock(spec=requests.Response, status_code=200, content=b"ok", headers={'Content-Type': 'image/jpeg'})
        mock_response_ok.raise_for_status = MagicMock()
        mock_response_err = MagicMock(spec=requests.Response, status_code=404)
        http_error = requests.exceptions.HTTPError("404 Not Found", response=mock_response_err)
        mock_response_err.raise_for_status.side_effect = http_error
        # Настраиваем side_effect для session.get
        mock_session.get.side_effect = [mock_response_ok, mock_response_err]

        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", total_pages, "out")

        assert success_count == 1
        assert total_count == total_pages
        assert mock_session.get.call_count == total_pages
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка HTTP 404 на стр. 2 (после {config.MAX_RETRIES} попыток): {http_error}")
        # Проверяем URL во втором вызове get
        failed_url = mock_session.get.call_args_list[1][0][0]
        logic.logger.error.assert_called_with(f"Ошибка HTTP 404 на стр. 2 (после {config.MAX_RETRIES} попыток): {http_error} URL: {failed_url}")

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_http_error_403(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест ошибки HTTP 403 (проверка доп. сообщения)."""
        mock_response_err = MagicMock(spec=requests.Response, status_code=403)
        http_error = requests.exceptions.HTTPError("403 Forbidden", response=mock_response_err)
        mock_response_err.raise_for_status.side_effect = http_error
        mock_session.get.return_value = mock_response_err # Всегда ошибка

        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)
        success_count, total_count = library_handler.download_pages("base", "ids", "file", 1, "out")

        assert success_count == 0
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка HTTP 403 на стр. 1 (после {config.MAX_RETRIES} попыток): {http_error}")
        mock_callbacks["status_callback"].assert_any_call("   (Возможно, сессия истекла, куки неверны или доступ запрещен)")

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_timeout_error(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест ошибки таймаута при скачивании страницы."""
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout")
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 1, "out")

        assert success_count == 0
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка: Таймаут при скачивании стр. 1 (после {config.MAX_RETRIES} попыток).")
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.error.assert_called_with(f"Ошибка: Таймаут при скачивании стр. 1 (после {config.MAX_RETRIES} попыток). URL: {failed_url}")

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_request_exception(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест другой сетевой ошибки при скачивании страницы."""
        error_msg = "Connection Error"
        mock_session.get.side_effect = requests.exceptions.RequestException(error_msg)
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 1, "out")

        assert success_count == 0
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка сети/сервера на стр. 1 (после {config.MAX_RETRIES} попыток): {error_msg}")
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.error.assert_called_with(f"Ошибка сети/сервера на стр. 1 (после {config.MAX_RETRIES} попыток): {error_msg} URL: {failed_url}", exc_info=True)

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_io_error(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест ошибки записи файла (IOError)."""
        error_msg = "Disk full"
        # Настраиваем мок open на выброс IOError при записи
        mock_path.mock_open_func().write.side_effect = IOError(error_msg)
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 1, "out")

        assert success_count == 0
        mock_callbacks["status_callback"].assert_any_call(f"Ошибка записи файла для стр. 1: {error_msg}")
        # Получаем имя файла, которое пытались открыть
        failed_filename = mock_path.return_value.with_suffix.return_value
        logic.logger.error.assert_called_with(f"Ошибка записи файла для стр. 1: {error_msg} Filename: {failed_filename}", exc_info=True)

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_unexpected_error(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест неожиданной ошибки в цикле скачивания."""
        error_msg = "Something weird happened"
        # Имитируем ошибку, например, при вызове stat() после записи файла
        mock_path.return_value.stat.side_effect = Exception(error_msg)
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 1, "out")

        assert success_count == 0
        mock_callbacks["status_callback"].assert_any_call(f"Неожиданная ошибка на стр. 1: {error_msg}")
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.error.assert_called_with(f"Неожиданная ошибка на стр. 1: {error_msg} URL: {failed_url}", exc_info=True)

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_html_response(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест получения HTML вместо изображения."""
        mock_response = mock_session.get.return_value
        mock_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
        mock_response.text = "<html><body>Login page</body></html>"
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 1, "out")

        assert success_count == 0
        mock_callbacks["status_callback"].assert_any_call("Ошибка на стр. 1: Получен HTML вместо изображения. Проблема с сессией/URL?")
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.error.assert_called_with(f"Ошибка на стр. 1: Получен HTML вместо изображения. Проблема с сессией/URL? URL: {failed_url}. Content preview: {mock_response.text[:200]}")
        # Файл не должен был быть открыт для записи
        mock_path.mock_open_func.assert_not_called()

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_empty_file(self, library_handler, mock_session, mock_callbacks, mock_path, mocker):
        """Тест скачивания пустого файла."""
        # Настраиваем stat().st_size на возврат 0
        mock_path.return_value.stat.return_value.st_size = 0
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        success_count, total_count = library_handler.download_pages("base", "ids", "file", 1, "out")

        assert success_count == 0
        # Получаем имя файла из мока path
        empty_filename = mock_path.return_value.name
        mock_callbacks["status_callback"].assert_any_call(f"Предупреждение: Файл {empty_filename} пустой.")
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.warning.assert_called_with(f"Предупреждение: Файл {empty_filename} пустой. URL: {failed_url}")

    # Добавляем mock_session и mock_path
    @pytest.mark.usefixtures("mock_dependencies")
    @pytest.mark.parametrize(
        "content_type, expected_suffix",
        [
            ("image/png", ".png"),
            ("image/gif", ".gif"),
            ("image/bmp", ".bmp"),
            ("image/tiff", ".tiff"),
            ("image/jpeg", ".jpeg"),
            ("application/octet-stream", ".jpg"),
            ("text/plain", ".jpg"),
            ("IMAGE/JPEG", ".jpeg"), # Проверка регистра
        ]
    )
    def test_download_pages_content_types(self, library_handler, mock_session, mock_callbacks, mock_path, mocker, content_type, expected_suffix):
        """Тест определения расширения файла по Content-Type."""
        mock_response = mock_session.get.return_value
        mock_response.headers = {'Content-Type': content_type}
        mocker.patch.object(library_handler, '_get_initial_cookies', return_value=True)

        library_handler.download_pages("base", "ids", "file", 1, "out")

        mock_path.return_value.with_suffix.assert_called_once_with(expected_suffix)
        # Проверяем лог предупреждения для неизвестных типов
        if expected_suffix == ".jpg" and 'jpeg' not in content_type.lower() and 'jpg' not in content_type.lower():
             logic.logger.warning.assert_called_with(f"Unknown Content-Type '{content_type.lower()}' for page 1. Assuming .jpg")
        else:
            # Убедимся, что предупреждение НЕ было вызвано для известных типов
             for call_args in logic.logger.warning.call_args_list:
                 assert "Unknown Content-Type" not in call_args[0][0]


    # --- Тест process_images ---

    @pytest.mark.usefixtures("mock_dependencies")
    def test_process_images(self, library_handler, mock_callbacks):
        """Тест делегирования обработки изображений."""
        input_folder = "input_pages"
        output_folder = "output_spreads"
        expected_result = (10, 5) # То, что вернет мок

        result = library_handler.process_images(input_folder, output_folder)

        assert result == expected_result
        logic.image_processing.process_images_in_folders.assert_called_once_with(
            input_folder=input_folder,
            output_folder=output_folder,
            status_callback=mock_callbacks["status_callback"],
            progress_callback=mock_callbacks["progress_callback"],
            stop_event=mock_callbacks["stop_event"],
            config=config,
            utils=utils,
            logger=logic.logger # Передаем замоканный логгер модуля
        )