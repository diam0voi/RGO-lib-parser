# tests/test_logic.py
import logging
from pathlib import Path
import threading
from unittest.mock import MagicMock

import pytest
import requests
from requests import structures  # Для spec в headers
from requests.adapters import HTTPAdapter
from requests.cookies import RequestsCookieJar
from urllib3.util.retry import Retry

from src import config, logic, utils
from src.types import ProgressCallback, StatusCallback


# --- Фикстуры ---
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
    mock_sess.headers = mocker.MagicMock(spec=structures.CaseInsensitiveDict)
    mock_sess.headers.update = mocker.MagicMock()
    mock_sess.cookies = mocker.MagicMock(spec=RequestsCookieJar)
    mock_sess.cookies.__len__.return_value = 0
    mock_sess.cookies.keys.return_value = []

    mock_response = mocker.MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.content = b"fake image data"
    mock_response.headers = {"Content-Type": "image/jpeg"}
    mock_response.raise_for_status = mocker.MagicMock()
    mock_sess.get.return_value = mock_response

    mocker.patch("src.logic.requests.Session", return_value=mock_sess)
    mocker.patch("src.logic.Retry", spec=Retry)
    mocker.patch("src.logic.HTTPAdapter", spec=HTTPAdapter)
    return mock_sess


@pytest.fixture
def mock_path(mocker):
    """Фикстура для мока pathlib.Path (без мока open)."""
    mock_p = mocker.patch("src.logic.Path", spec=Path)
    mock_instance = mocker.MagicMock(spec=Path)
    mock_instance.mkdir = mocker.MagicMock()
    mock_stat_result = mocker.MagicMock()
    mock_stat_result.st_size = 100  # По умолчанию файл не пустой
    mock_instance.stat.return_value = mock_stat_result
    mock_instance.with_suffix = mocker.MagicMock(return_value=mock_instance)
    mock_instance.__truediv__.return_value = mock_instance
    mock_instance.name = "mock_file.jpg"
    mock_p.return_value = mock_instance
    return mock_p  # Возвращаем сам мок класса Path


@pytest.fixture
def mock_dependencies(mocker):
    """Фикстура для мока других зависимостей (кроме логгера)."""
    mocker.patch("src.logic.time.sleep")
    mocker.patch(
        "src.logic.image_processing.process_images_in_folders", return_value=(10, 5)
    )


# --- Тесты ---


class TestLibraryHandler:
    # --- Тесты init, setup_session, get_initial_cookies (как были) ---

    def test_init(self, library_handler, mock_callbacks):
        """Тест инициализации LibraryHandler."""
        status_cb = mock_callbacks["status_callback"]
        progress_cb = mock_callbacks["progress_callback"]
        stop_ev = mock_callbacks["stop_event"]

        assert library_handler.status_callback is status_cb
        assert library_handler.progress_callback is progress_cb
        assert library_handler.stop_event is stop_ev
        assert library_handler.session is None
        logic.logger.info.assert_called_once_with("LibraryHandler initialized")

    def test_setup_session_with_retry_new(self, library_handler, mock_session, mocker):
        """Тест создания новой сессии."""
        library_handler.session = None
        library_handler._setup_session_with_retry()

        assert library_handler.session is mock_session
        mock_session.headers.update.assert_called_once_with(
            {"User-Agent": config.DEFAULT_USER_AGENT}
        )
        logic.Retry.assert_called_once_with(
            total=config.MAX_RETRIES,
            status_forcelist=config.RETRY_ON_HTTP_CODES,
            backoff_factor=1,
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        logic.HTTPAdapter.assert_called_once_with(max_retries=logic.Retry.return_value)
        assert mock_session.mount.call_count == 2
        mock_session.mount.assert_any_call("https://", logic.HTTPAdapter.return_value)
        mock_session.mount.assert_any_call("http://", logic.HTTPAdapter.return_value)
        logic.logger.info.assert_called_with(
            f"Requests session created with retry strategy (max={config.MAX_RETRIES}, statuses={config.RETRY_ON_HTTP_CODES})"
        )

    def test_setup_session_with_retry_existing(
        self, library_handler, mock_session, mocker
    ):
        """Тест повторного вызова _setup_session_with_retry с существующей сессией."""
        library_handler.session = mock_session
        library_handler._setup_session_with_retry()

        logic.requests.Session.assert_not_called()
        mock_session.mount.assert_not_called()
        logic.logger.debug.assert_called_once_with("Session already exists. Reusing.")

    def test_get_initial_cookies_success(
        self, library_handler, mock_session, mock_callbacks
    ):
        """Тест успешного получения куки."""
        mock_session.cookies.keys.return_value = ["session_id"]
        mock_session.cookies.__len__.return_value = 1

        result = library_handler._get_initial_cookies()

        assert result is True
        mock_session.get.assert_called_once_with(
            config.INITIAL_COOKIE_URL, timeout=config.REQUEST_TIMEOUT
        )
        mock_session.get.return_value.raise_for_status.assert_called_once()
        mock_callbacks["status_callback"].assert_any_call(
            f"Автоматическое получение сессионных куки с {config.INITIAL_COOKIE_URL}..."
        )
        mock_callbacks["status_callback"].assert_any_call(
            "Успешно получены куки: ['session_id']"
        )
        logic.logger.info.assert_any_call(
            f"Attempting to get initial cookies from {config.INITIAL_COOKIE_URL}"
        )
        logic.logger.info.assert_any_call("Initial cookies obtained: ['session_id']")

    def test_get_initial_cookies_no_cookies_set(
        self, library_handler, mock_session, mock_callbacks
    ):
        """Тест случая, когда сервер не установил куки."""
        mock_session.cookies.keys.return_value = []
        mock_session.cookies.__len__.return_value = 0

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_session.get.assert_called_once_with(
            config.INITIAL_COOKIE_URL, timeout=config.REQUEST_TIMEOUT
        )
        mock_callbacks["status_callback"].assert_any_call(
            "Предупреждение: Не удалось автоматически получить куки (сервер не установил?)."
        )
        logic.logger.warning.assert_called_once_with(
            "Server did not set any cookies during initial request."
        )

    def test_get_initial_cookies_timeout(
        self, library_handler, mock_session, mock_callbacks
    ):
        """Тест таймаута при получении куки."""
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout error")

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call(
            f"Ошибка: Превышено время ожидания при получении куки с {config.INITIAL_COOKIE_URL}."
        )
        logic.logger.error.assert_called_once_with(
            f"Ошибка: Превышено время ожидания при получении куки с {config.INITIAL_COOKIE_URL}."
        )

    def test_get_initial_cookies_request_exception(
        self, library_handler, mock_session, mock_callbacks
    ):
        """Тест другой ошибки запроса при получении куки."""
        error_msg = "Connection failed"
        mock_session.get.side_effect = requests.exceptions.RequestException(error_msg)

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call(
            f"Ошибка при получении куки: {error_msg}."
        )
        logic.logger.error.assert_called_once_with(
            f"Error getting initial cookies: {error_msg}", exc_info=True
        )

    def test_get_initial_cookies_http_error(
        self, library_handler, mock_session, mock_callbacks
    ):
        """Тест HTTP ошибки (4xx/5xx) при получении куки."""
        mock_response = mock_session.get.return_value
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Client Error"
        )

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call(
            "Ошибка при получении куки: 404 Client Error."
        )
        logic.logger.error.assert_called_once_with(
            "Error getting initial cookies: 404 Client Error", exc_info=True
        )

    def test_get_initial_cookies_session_setup_fails(
        self, library_handler, mock_callbacks, mocker
    ):
        """Тест ошибки при настройке сессии во время получения куки."""
        mocker.patch.object(
            library_handler,
            "_setup_session_with_retry",
            side_effect=Exception("Setup failed"),
        )
        library_handler.session = None

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call(
            "Критическая ошибка при настройке сессии: Setup failed"
        )
        logic.logger.error.assert_called_with(
            "Failed to setup session during cookie retrieval: Setup failed",
            exc_info=True,
        )

    def test_get_initial_cookies_session_setup_returns_none(
        self, library_handler, mock_callbacks, mocker
    ):
        """Тест, когда _setup_session_with_retry не создает сессию (гипотетический случай)."""
        mocker.patch.object(library_handler, "_setup_session_with_retry")
        library_handler.session = None

        result = library_handler._get_initial_cookies()

        assert result is False
        mock_callbacks["status_callback"].assert_any_call(
            "Критическая ошибка: Не удалось создать сетевую сессию."
        )
        logic.logger.error.assert_called_with(
            "Failed to setup session in _get_initial_cookies"
        )

    # --- Тесты download_pages (ИСПРАВЛЕННЫЕ) ---

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_success(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест успешного скачивания всех страниц."""
        base_url = "http://example.com/books"
        url_ids = "123/456"
        filename_pdf = "my_book.pdf"
        total_pages = 3
        output_dir = "test_output"

        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)
        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            base_url, url_ids, filename_pdf, total_pages, output_dir
        )

        assert success_count == total_pages
        assert total_count == total_pages
        mock_path.assert_called_once_with(output_dir)
        mock_path.return_value.mkdir.assert_called_once_with(
            parents=True, exist_ok=True
        )

        assert mock_callbacks["status_callback"].call_count == total_pages + 2
        mock_callbacks["status_callback"].assert_any_call(
            f"Начинаем скачивание {total_pages} страниц в '{output_dir}'..."
        )
        # ИСПРАВЛЕНО: Проверяем правильное финальное сообщение
        mock_callbacks["status_callback"].assert_any_call(
            f"Скачивание завершено. Успешно: {total_pages} из {total_pages}."
        )
        assert mock_callbacks["progress_callback"].call_count == total_pages + 1
        mock_callbacks["progress_callback"].assert_any_call(total_pages, total_pages)

        assert mock_session.get.call_count == total_pages
        assert mock_file_open.call_count == total_pages
        expected_path_object = mock_path.return_value
        mock_file_open.assert_any_call(expected_path_object, "wb")
        assert mock_file_open().write.call_count == total_pages
        mock_file_open().write.assert_called_with(b"fake image data")
        assert mock_path.return_value.with_suffix.call_count == total_pages
        mock_path.return_value.with_suffix.assert_called_with(".jpeg")
        assert logic.time.sleep.call_count == total_pages

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_session_setup_fails(
        self, library_handler, mock_callbacks, mocker
    ):
        """Тест ошибки создания сессии перед скачиванием."""
        mocker.patch.object(library_handler, "_setup_session_with_retry")
        library_handler.session = None

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 5, "out"
        )

        assert success_count == 0
        assert total_count == 5
        mock_callbacks["status_callback"].assert_any_call(
            "Критическая ошибка: Не удалось создать сетевую сессию для скачивания."
        )
        logic.logger.error.assert_called_with("Failed to setup session for download.")

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_no_cookies_warning(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест продолжения скачивания после неудачного получения куки."""
        # Мокаем builtins.open, т.к. скачивание продолжается
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=False)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        assert success_count == 1  # Ожидаем успеха, несмотря на предупреждение
        assert total_count == 1
        mock_callbacks["status_callback"].assert_any_call(
            "Продолжаем без автоматических куки (могут быть проблемы)..."
        )
        logic.logger.warning.assert_called_with(
            "Proceeding with download without initial cookies."
        )
        assert mock_session.get.call_count == 1
        assert mock_file_open.call_count == 1  # Файл должен был записаться

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_mkdir_error(
        self, library_handler, mock_callbacks, mock_path, mocker
    ):
        """Тест ошибки создания выходной папки."""
        error_msg = "Permission denied"
        mock_path.return_value.mkdir.side_effect = OSError(error_msg)
        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        # Сессия создается через _get_initial_cookies

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 5, "out_dir"
        )

        assert success_count == 0
        assert total_count == 5
        mock_callbacks["status_callback"].assert_any_call(
            f"Ошибка создания папки для страниц 'out_dir': {error_msg}"
        )
        logic.logger.error.assert_called_with(
            f"Ошибка создания папки для страниц 'out_dir': {error_msg}", exc_info=True
        )

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_stop_event(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест прерывания скачивания по stop_event."""
        total_pages = 5
        stop_at_page = 2  # Успешно скачиваем 2 страницы (i=0, i=1), прерываем перед i=2

        # --- Мокирование зависимостей ---
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        mock_logger_info = mocker.patch("src.logic.logger.info")
        mock_sleep = mocker.patch("src.logic.time.sleep")

        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)

        # Настраиваем side_effect для stop_event.is_set
        call_count = 0
        # Хотим прервать на проверке В НАЧАЛЕ цикла для i = stop_at_page (т.е. i=2)
        # Эта проверка будет (stop_at_page * 2) + 1 = 5-м вызовом is_set()
        target_stop_call = (stop_at_page * 2) + 1

        def stop_side_effect():
            nonlocal call_count
            call_count += 1
            return call_count >= target_stop_call  # Станет True на 5-м вызове

        mock_callbacks["stop_event"].is_set.side_effect = stop_side_effect

        # Настраиваем мок Path(...).stat()
        mock_path.return_value.stat.reset_mock()
        mock_path.return_value.stat.return_value.st_size = 100
        mock_path.return_value.stat.side_effect = (
            None  # Убедимся, что нет лишних side_effect
        )

        # Настраиваем мок session.get
        mock_response = mocker.Mock(spec=requests.Response)  # Лучше использовать spec
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_response.content = b"fakedata"
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response

        # --- Выполнение ---
        # _setup_session_with_retry вызывается внутри download_pages, если session is None
        # library_handler._setup_session_with_retry() # Этот вызов здесь не обязателен

        success_count, total_count = library_handler.download_pages(
            "base_url", "ids_part", "filename.pdf", total_pages, "output_dir"
        )

        # --- Проверки ---
        assert success_count == stop_at_page  # Успешно скачано 2 страницы
        assert total_count == total_pages

        # Проверяем вызовы моков
        assert mock_session.get.call_count == stop_at_page  # Вызван для i=0, i=1
        assert mock_file_open.call_count == stop_at_page  # Вызван для i=0, i=1
        assert mock_file_open().write.call_count == stop_at_page  # Вызван для i=0, i=1

        # Проверяем коллбэки и логи
        mock_callbacks["status_callback"].assert_any_call(
            "--- Скачивание прервано пользователем ---"
        )
        mock_logger_info.assert_any_call("Download interrupted by user.")

        # Проверяем прогресс: вызывается в finally для i=0 и i=1
        assert mock_callbacks["progress_callback"].call_count == stop_at_page + 1
        # Последний вызов был с i=1, т.е. progress_callback(i+1, ...) -> progress_callback(2, ...)
        mock_callbacks["progress_callback"].assert_called_with(
            stop_at_page, total_pages
        )

        # Проверяем sleep: вызывается в finally для i=0 и i=1, т.к. is_set() там был False
        assert mock_sleep.call_count == stop_at_page

        # Дополнительно можно проверить вызовы Path().stat()
        assert (
            mock_path.return_value.stat.call_count == stop_at_page
        )  # Вызван для i=0, i=1

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_b64_encode_error(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест ошибки при кодировании URL в base64."""
        error_msg = "Encoding failed"
        mocker.patch("src.logic.base64.b64encode", side_effect=Exception(error_msg))
        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        assert success_count == 0
        assert total_count == 1
        mock_callbacks["status_callback"].assert_any_call(
            f"Ошибка кодирования URL для стр. 1: {error_msg}"
        )
        logic.logger.error.assert_called_with(
            f"Ошибка кодирования URL для стр. 1: {error_msg}", exc_info=True
        )
        mock_session.get.assert_not_called()

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_http_error(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест ошибки HTTP 404 при скачивании страницы."""
        total_pages = 2
        # Мокаем builtins.open, т.к. первая страница скачивается успешно
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        mock_response_ok = MagicMock(
            spec=requests.Response,
            status_code=200,
            content=b"ok",
            headers={"Content-Type": "image/jpeg"},
        )
        mock_response_ok.raise_for_status = MagicMock()
        mock_response_err = MagicMock(spec=requests.Response, status_code=404)
        http_error = requests.exceptions.HTTPError(
            "404 Not Found", response=mock_response_err
        )
        mock_response_err.raise_for_status.side_effect = http_error
        mock_session.get.side_effect = [mock_response_ok, mock_response_err]

        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", total_pages, "out"
        )

        assert success_count == 1  # Первая страница успешна
        assert total_count == total_pages
        assert mock_session.get.call_count == total_pages
        # Проверяем, что файл был открыт только один раз (для успешной страницы)
        assert mock_file_open.call_count == 1
        assert mock_file_open().write.call_count == 1

        mock_callbacks["status_callback"].assert_any_call(
            f"Ошибка HTTP 404 на стр. 2 (после {config.MAX_RETRIES} попыток): {http_error}"
        )
        failed_url = mock_session.get.call_args_list[1][0][0]
        logic.logger.error.assert_called_with(
            f"Ошибка HTTP 404 на стр. 2 (после {config.MAX_RETRIES} попыток): {http_error} URL: {failed_url}"
        )

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_http_error_403(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест ошибки HTTP 403 (проверка доп. сообщения)."""
        # Мокаем builtins.open на всякий случай, хотя он не должен вызваться
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        mock_response_err = MagicMock(spec=requests.Response, status_code=403)
        http_error = requests.exceptions.HTTPError(
            "403 Forbidden", response=mock_response_err
        )
        mock_response_err.raise_for_status.side_effect = http_error
        mock_session.get.return_value = mock_response_err  # Всегда ошибка

        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        assert success_count == 0
        assert mock_file_open.call_count == 0  # Файл не открывался
        mock_callbacks["status_callback"].assert_any_call(
            f"Ошибка HTTP 403 на стр. 1 (после {config.MAX_RETRIES} попыток): {http_error}"
        )
        mock_callbacks["status_callback"].assert_any_call(
            "   (Возможно, сессия истекла, куки неверны или доступ запрещен)"
        )

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_timeout_error(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест ошибки таймаута при скачивании страницы."""
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout")
        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        assert success_count == 0
        assert mock_file_open.call_count == 0
        mock_callbacks["status_callback"].assert_any_call(
            f"Ошибка: Таймаут при скачивании стр. 1 (после {config.MAX_RETRIES} попыток)."
        )
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.error.assert_called_with(
            f"Ошибка: Таймаут при скачивании стр. 1 (после {config.MAX_RETRIES} попыток). URL: {failed_url}"
        )

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_request_exception(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест другой сетевой ошибки при скачивании страницы."""
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        error_msg = "Connection Error"
        mock_session.get.side_effect = requests.exceptions.RequestException(error_msg)
        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        assert success_count == 0
        assert mock_file_open.call_count == 0
        mock_callbacks["status_callback"].assert_any_call(
            f"Ошибка сети/сервера на стр. 1 (после {config.MAX_RETRIES} попыток): {error_msg}"
        )
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.error.assert_called_with(
            f"Ошибка сети/сервера на стр. 1 (после {config.MAX_RETRIES} попыток): {error_msg} URL: {failed_url}",
            exc_info=True,
        )

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_io_error(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест ошибки записи файла (IOError)."""
        error_msg = "Disk full"

        # Мокаем builtins.open
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)
        # ИСПРАВЛЕНО: Настраиваем write через return_value мока open
        mock_file_open.return_value.write.side_effect = OSError(error_msg)

        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        # Ассерт теперь должен проходить!
        assert success_count == 0
        assert total_count == 1

        # Проверяем, что open был вызван один раз с нужными аргументами
        expected_path_object = mock_path.return_value
        mock_file_open.assert_called_once_with(expected_path_object, "wb")
        # ИСПРАВЛЕНО: Проверяем write через return_value мока open
        mock_file_open.return_value.write.assert_called_once_with(b"fake image data")

        mock_callbacks["status_callback"].assert_any_call(
            f"Ошибка записи файла для стр. 1: {error_msg}"
        )
        # В логе используется объект Path, который мы мокаем
        logic.logger.error.assert_called_with(
            f"Ошибка записи файла для стр. 1: {error_msg} Filename: {expected_path_object}",
            exc_info=True,
        )

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_unexpected_error(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест неожиданной ошибки в цикле скачивания (после записи)."""
        error_msg = "Something weird happened"

        # Мокаем builtins.open (он должен успешно отработать)
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        # Ошибка происходит при вызове stat() на объекте Path
        mock_path.return_value.stat.side_effect = Exception(error_msg)

        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        # Ассерт теперь должен проходить!
        assert success_count == 0
        assert total_count == 1

        # Проверяем, что open и write были вызваны до ошибки
        expected_path_object = mock_path.return_value
        mock_file_open.assert_called_once_with(expected_path_object, "wb")
        mock_file_open().write.assert_called_once_with(b"fake image data")
        # Проверяем, что stat был вызван (и вызвал ошибку)
        mock_path.return_value.stat.assert_called_once()

        mock_callbacks["status_callback"].assert_any_call(
            f"Неожиданная ошибка на стр. 1: {error_msg}"
        )
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.error.assert_called_with(
            f"Неожиданная ошибка на стр. 1: {error_msg} URL: {failed_url}",
            exc_info=True,
        )

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_html_response(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест получения HTML вместо изображения."""
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        mock_response = mock_session.get.return_value
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response.text = "<html><body>Login page</body></html>"
        mock_response.content = mock_response.text.encode("utf-8")
        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        assert success_count == 0
        assert mock_file_open.call_count == 0  # Файл не открывался
        mock_callbacks["status_callback"].assert_any_call(
            "Ошибка на стр. 1: Получен HTML вместо изображения. Проблема с сессией/URL?"
        )
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.error.assert_called_with(
            f"Ошибка на стр. 1: Получен HTML вместо изображения. Проблема с сессией/URL? URL: {failed_url}. Content preview: {mock_response.text[:200]}"
        )

    @pytest.mark.usefixtures("mock_dependencies")
    def test_download_pages_empty_file(
        self, library_handler, mock_session, mock_callbacks, mock_path, mocker
    ):
        """Тест скачивания пустого файла."""
        # Мокаем builtins.open (он должен успешно отработать)
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        # Настраиваем stat().st_size на возврат 0
        mock_path.return_value.stat.return_value.st_size = 0
        # Сбрасываем side_effect у stat, если он был установлен в другом тесте
        mock_path.return_value.stat.side_effect = None

        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        # Ассерт теперь должен проходить!
        assert success_count == 0
        assert total_count == 1

        # Проверяем, что open и write были вызваны
        expected_path_object = mock_path.return_value
        mock_file_open.assert_called_once_with(expected_path_object, "wb")
        mock_file_open().write.assert_called_once_with(b"fake image data")
        # Проверяем, что stat был вызван
        mock_path.return_value.stat.assert_called_once()

        empty_filename = mock_path.return_value.name
        mock_callbacks["status_callback"].assert_any_call(
            f"Предупреждение: Файл {empty_filename} пустой."
        )
        failed_url = mock_session.get.call_args[0][0]
        logic.logger.warning.assert_called_with(
            f"Предупреждение: Файл {empty_filename} пустой. URL: {failed_url}"
        )

        # Сбросим stat для других тестов
        mock_path.return_value.stat.reset_mock()

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
            ("IMAGE/JPEG", ".jpeg"),
            ("image/jpeg; charset=UTF-8", ".jpeg"),
        ],
    )
    def test_download_pages_content_types(
        self,
        library_handler,
        mock_session,
        mock_callbacks,
        mock_path,
        mocker,
        content_type,
        expected_suffix,
    ):
        """Тест определения расширения файла по Content-Type."""
        # Мокаем builtins.open
        mock_file_open = mocker.mock_open()
        mocker.patch("builtins.open", mock_file_open)

        mock_response = mock_session.get.return_value
        mock_response.headers = {"Content-Type": content_type}
        # Сбрасываем stat к значению по умолчанию > 0
        mock_path.return_value.stat.return_value.st_size = 100
        # Сбрасываем side_effect у stat
        mock_path.return_value.stat.side_effect = None

        mocker.patch.object(library_handler, "_get_initial_cookies", return_value=True)
        library_handler._setup_session_with_retry()

        success_count, total_count = library_handler.download_pages(
            "base", "ids", "file", 1, "out"
        )

        assert success_count == 1
        assert total_count == 1

        # Проверяем вызов with_suffix
        mock_path.return_value.with_suffix.assert_called_once_with(expected_suffix)
        # Проверяем, что файл был открыт и записан
        expected_path_object = mock_path.return_value
        mock_file_open.assert_called_once_with(expected_path_object, "wb")
        mock_file_open().write.assert_called_once_with(b"fake image data")

        # Проверяем лог предупреждения для неизвестных типов
        main_content_type = content_type.split(";")[0].strip().lower()
        is_unknown_type = (
            expected_suffix == ".jpg"
            and "jpeg" not in main_content_type
            and "jpg" not in main_content_type
        )
        was_warning_logged = any(
            f"Unknown Content-Type '{main_content_type}'" in call_args[0][0]
            for call_args in logic.logger.warning.call_args_list
        )
        assert was_warning_logged == is_unknown_type

        # Сбросим вызовы моков для следующей итерации parametrize
        mock_path.return_value.with_suffix.reset_mock()
        logic.logger.warning.reset_mock()
        mock_file_open.reset_mock()
        mock_file_open().write.reset_mock()
        mock_path.return_value.stat.reset_mock()

    # --- Тест process_images ---

    @pytest.mark.usefixtures("mock_dependencies")
    def test_process_images(self, library_handler, mock_callbacks):
        """Тест делегирования обработки изображений."""
        input_folder = "input_pages"
        output_folder = "output_spreads"
        expected_result = (10, 5)  # То, что вернет мок

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
            logger=logic.logger,
        )
