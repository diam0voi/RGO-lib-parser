# rgo_lib_parser_test.py
import unittest
from unittest.mock import patch, MagicMock, mock_open, call, ANY
import os
import sys
import shutil
import threading
import base64
import logging
from io import BytesIO

# ... (FakeConfig и импорты остаются такими же) ...
class FakeConfig:
    SETTINGS_FILE = "settings_test.json"
    LOG_FILE = "parsing_test.log"
    DEFAULT_USER_AGENT = "Test Agent/1.0"
    INITIAL_COOKIE_URL = "https://fake.rgo.ru/cookie"
    MAX_RETRIES = 2
    RETRY_ON_HTTP_CODES = [500, 502]
    DEFAULT_DELAY_SECONDS = 0.01 # Ускорим тесты
    RETRY_DELAY = 0.02 # Ускорим тесты
    IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')
    DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD = 1.1
    JPEG_QUALITY = 90
    DEFAULT_PAGES_DIR = "test_pages_dir"
    DEFAULT_SPREADS_DIR = "test_spreads_dir"
    DEFAULT_URL_BASE = "https://fake.rgo.ru/base/"
    DEFAULT_URL_IDS = "id123/"
    DEFAULT_PDF_FILENAME = "book.pdf"
    DEFAULT_TOTAL_PAGES = "10"

sys.modules['config'] = FakeConfig()
import rgo_lib_parser_by_b0s as parser
logging.disable(logging.CRITICAL)

# --- Тесты хелперов ---
# (TestHelperFunctions остается без изменений)
class TestHelperFunctions(unittest.TestCase):

    def test_get_page_number_valid(self):
        self.assertEqual(parser.get_page_number("page_001.jpg"), 1)
        self.assertEqual(parser.get_page_number("spread_123-456.png"), 123)
        self.assertEqual(parser.get_page_number("005_image.jpeg"), 5)
        self.assertEqual(parser.get_page_number("img_99.gif"), 99)

    def test_get_page_number_invalid(self):
        self.assertEqual(parser.get_page_number("cover.jpg"), -1)
        self.assertEqual(parser.get_page_number("image.png"), -1)
        self.assertEqual(parser.get_page_number(""), -1)
        self.assertEqual(parser.get_page_number("no_number_here"), -1)

    @patch('rgo_lib_parser_by_b0s.Image.open')
    def test_is_likely_spread_true(self, mock_image_open):
        mock_img = MagicMock()
        mock_img.size = (1200, 1000) # aspect ratio = 1.2 > 1.1
        mock_image_open.return_value.__enter__.return_value = mock_img
        self.assertTrue(parser.is_likely_spread("dummy_path.jpg", FakeConfig.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD))
        mock_image_open.assert_called_once_with("dummy_path.jpg")

    @patch('rgo_lib_parser_by_b0s.Image.open')
    def test_is_likely_spread_false(self, mock_image_open):
        mock_img = MagicMock()
        mock_img.size = (1000, 1000) # aspect ratio = 1.0 < 1.1
        mock_image_open.return_value.__enter__.return_value = mock_img
        self.assertFalse(parser.is_likely_spread("dummy_path.jpg", FakeConfig.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD))

    @patch('rgo_lib_parser_by_b0s.Image.open')
    def test_is_likely_spread_zero_height(self, mock_image_open):
        mock_img = MagicMock()
        mock_img.size = (1000, 0)
        mock_image_open.return_value.__enter__.return_value = mock_img
        self.assertFalse(parser.is_likely_spread("dummy_path.jpg", FakeConfig.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD))

    @patch('rgo_lib_parser_by_b0s.Image.open')
    @patch('rgo_lib_parser_by_b0s.logging') # Мокаем логгер
    def test_is_likely_spread_exception(self, mock_logging, mock_image_open):
        mock_image_open.side_effect = Exception("PIL Error")
        self.assertFalse(parser.is_likely_spread("dummy_path.jpg", FakeConfig.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD))
        mock_logging.warning.assert_called_once() # Проверяем, что было вызвано предупреждение


# --- Тесты LibraryHandler ---

# Декораторы класса остаются
@patch('rgo_lib_parser_by_b0s.requests.Session')
@patch('rgo_lib_parser_by_b0s.shutil.copy2')
@patch('rgo_lib_parser_by_b0s.os.makedirs')
@patch('rgo_lib_parser_by_b0s.os.listdir')
@patch('rgo_lib_parser_by_b0s.os.path.getsize')
@patch('rgo_lib_parser_by_b0s.Image', new_callable=MagicMock)
@patch('rgo_lib_parser_by_b0s.time.sleep', return_value=None)
@patch('builtins.open', new_callable=mock_open)
class TestLibraryHandler(unittest.TestCase):

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    # Убираем аргументы моков из сигнатуры setUp
    def setUp(self):
        # Создаем моки для колбэков и события остановки
        self.mock_status_callback = MagicMock()
        self.mock_progress_callback = MagicMock()
        self.mock_stop_event = MagicMock()
        self.mock_stop_event.is_set.return_value = False # По умолчанию не остановлено

        # Создаем экземпляр LibraryHandler с моками
        self.handler = parser.LibraryHandler(
            status_callback=self.mock_status_callback,
            progress_callback=self.mock_progress_callback,
            stop_event=self.mock_stop_event
        )
        # Моки от декораторов класса (mock_open, MockSession и т.д.)
        # будут доступны как аргументы в test_* методах, но не здесь.

    # --- ВАЖНО: Сигнатуры test_* методов ОСТАЮТСЯ с аргументами моков ---
    def test_init(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        self.assertEqual(self.handler.status_callback, self.mock_status_callback)
        self.assertEqual(self.handler.progress_callback, self.mock_progress_callback)
        self.assertEqual(self.handler.stop_event, self.mock_stop_event)
        self.assertIsNone(self.handler.session)

    def test_setup_session_with_retry(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        mock_session_instance = MockSession.return_value

        self.handler._setup_session_with_retry()

        # Проверки
        MockSession.assert_called_once()
        mock_session_instance.headers.update.assert_called_once_with({'User-Agent': FakeConfig.DEFAULT_USER_AGENT})

        mount_calls = mock_session_instance.mount.call_args_list
        self.assertEqual(len(mount_calls), 2)
        prefixes = {call.args[0] for call in mount_calls}
        self.assertEqual(prefixes, {"http://", "https://"})

        adapter_instance = mount_calls[0].args[1]
        self.assertIsInstance(adapter_instance, parser.requests.adapters.HTTPAdapter)
        self.assertIsInstance(adapter_instance.max_retries, parser.requests.packages.urllib3.util.retry.Retry)

        retry_strategy = adapter_instance.max_retries
        self.assertEqual(retry_strategy.total, FakeConfig.MAX_RETRIES)
        self.assertEqual(set(retry_strategy.status_forcelist), set(FakeConfig.RETRY_ON_HTTP_CODES))
        self.assertEqual(retry_strategy.backoff_factor, 1)

        self.assertIsNotNone(self.handler.session)
        self.assertEqual(self.handler.session, mock_session_instance)

    def test_get_initial_cookies_success(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        mock_session = MockSession.return_value
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        mock_session.cookies = {'sessionid': 'testcookie123'}

        result = self.handler._get_initial_cookies()

        self.assertTrue(result)
        mock_session.get.assert_called_once_with(FakeConfig.INITIAL_COOKIE_URL, timeout=(10, 20))
        mock_response.raise_for_status.assert_called_once()
        self.mock_status_callback.assert_any_call(f"Автоматическое получение сессионных куки с {FakeConfig.INITIAL_COOKIE_URL}...")
        self.mock_status_callback.assert_any_call("Успешно получены куки: ['sessionid']")

    def test_get_initial_cookies_no_cookies_set(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        mock_session = MockSession.return_value
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        mock_session.cookies = {}

        result = self.handler._get_initial_cookies()

        self.assertFalse(result)
        self.mock_status_callback.assert_any_call("Предупреждение: Не удалось автоматически получить куки (сервер не установил?).")

    def test_get_initial_cookies_timeout(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        mock_session = MockSession.return_value
        mock_session.get.side_effect = parser.requests.exceptions.Timeout("Timeout error")

        result = self.handler._get_initial_cookies()

        self.assertFalse(result)
        self.mock_status_callback.assert_any_call(f"Ошибка: Превышено время ожидания при получении куки с {FakeConfig.INITIAL_COOKIE_URL}.")

    def test_get_initial_cookies_request_exception(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        mock_session = MockSession.return_value
        mock_session.get.side_effect = parser.requests.exceptions.RequestException("Network error")

        result = self.handler._get_initial_cookies()

        self.assertFalse(result)
        self.mock_status_callback.assert_any_call("Ошибка при получении куки: Network error.")

    def test_download_pages_success(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        mock_session = MockSession.return_value
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.content = b'fakedata'
        mock_session.get.return_value = mock_response
        mock_getsize.return_value = 10

        with patch.object(self.handler, '_get_initial_cookies', return_value=True) as mock_get_cookies:
            base_url = "https://test.com/base/"
            url_ids = "book123/"
            pdf_filename = "document.pdf"
            total_pages = 3
            output_dir = "test_output"

            success_count, total_count = self.handler.download_pages(
                base_url, url_ids, pdf_filename, total_pages, output_dir
            )

            self.assertEqual(success_count, total_pages)
            self.assertEqual(total_count, total_pages)
            mock_get_cookies.assert_called_once()
            self.assertEqual(mock_session.get.call_count, total_pages)
            self.assertEqual(mock_open.call_count, total_pages)
            self.assertEqual(mock_getsize.call_count, total_pages)

            expected_page_str = f"{pdf_filename}/0"
            expected_b64 = base64.b64encode(expected_page_str.encode('utf-8')).decode('utf-8')
            expected_url = f"{base_url}{url_ids}{expected_b64}"
            expected_filename = os.path.join(output_dir, "page_000.jpeg")

            mock_session.get.assert_any_call(expected_url, timeout=(10, 30))
            mock_open.assert_any_call(expected_filename, 'wb')
            mock_open().write.assert_any_call(b'fakedata')
            mock_getsize.assert_any_call(expected_filename)

            self.mock_status_callback.assert_any_call(f"Начинаем скачивание {total_pages} страниц в '{output_dir}'...")
            self.mock_status_callback.assert_any_call(f"Скачиваю страницу 1/{total_pages}...")
            self.mock_status_callback.assert_any_call(f"Скачиваю страницу 2/{total_pages}...")
            self.mock_status_callback.assert_any_call(f"Скачиваю страницу 3/{total_pages}...")
            self.assertEqual(self.mock_progress_callback.call_count, total_pages + 1)
            self.mock_progress_callback.assert_has_calls([
                call(0, total_pages),
                call(1, total_pages),
                call(2, total_pages),
                call(3, total_pages)
            ])
            mock_sleep.assert_called()

    def test_download_pages_interrupted(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        mock_session = MockSession.return_value
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {'Content-Type': 'image/png'}
        mock_response.content = b'fakedata'
        mock_session.get.return_value = mock_response
        mock_getsize.return_value = 10

        self.mock_stop_event.is_set.side_effect = [False, True, True]

        with patch.object(self.handler, '_get_initial_cookies', return_value=True):
            success_count, total_count = self.handler.download_pages("b/", "i/", "p", 3, "out")

            self.assertEqual(success_count, 1)
            self.assertEqual(total_count, 3)
            self.assertEqual(mock_session.get.call_count, 1)
            self.assertEqual(mock_open.call_count, 1)
            self.mock_status_callback.assert_any_call("--- Скачивание прервано пользователем ---")
            self.assertEqual(self.mock_stop_event.is_set.call_count, 3)
            self.mock_progress_callback.assert_has_calls([call(0, 3), call(1, 3)])

    def test_download_pages_http_error(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        mock_session = MockSession.return_value
        mock_response_ok = MagicMock(headers={'Content-Type': 'image/jpeg'}, content=b'ok')
        mock_response_ok.raise_for_status.return_value = None
        mock_response_err = MagicMock()
        http_error = parser.requests.exceptions.HTTPError("Not Found")
        http_error.response = MagicMock(status_code=404)
        mock_response_err.raise_for_status.side_effect = http_error
        mock_session.get.side_effect = [mock_response_ok, mock_response_err, mock_response_ok]
        mock_getsize.return_value = 10

        with patch.object(self.handler, '_get_initial_cookies', return_value=True):
            success_count, total_count = self.handler.download_pages("b/", "i/", "p", 3, "out")

            self.assertEqual(success_count, 2)
            self.assertEqual(total_count, 3)
            self.assertEqual(mock_session.get.call_count, 3)
            self.assertEqual(mock_open.call_count, 2)
            self.mock_status_callback.assert_any_call(f"Ошибка HTTP 404 на стр. 2 (после {FakeConfig.MAX_RETRIES} попыток): Not Found")

    def test_download_pages_empty_file(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        mock_session = MockSession.return_value
        mock_response = MagicMock(headers={'Content-Type': 'image/gif'}, content=b'empty')
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        mock_getsize.return_value = 0

        with patch.object(self.handler, '_get_initial_cookies', return_value=True):
            success_count, total_count = self.handler.download_pages("b/", "i/", "p", 1, "out")

            self.assertEqual(success_count, 0)
            self.assertEqual(total_count, 1)
            self.assertEqual(mock_open.call_count, 1)
            self.assertEqual(mock_getsize.call_count, 1)
            self.mock_status_callback.assert_any_call("Предупреждение: Файл page_000.gif пустой.")

    # --- Тесты process_images ---

    @patch('rgo_lib_parser_by_b0s.is_likely_spread')
    def test_process_images_copy_cover_and_spread(self, mock_is_likely_spread, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        input_folder = "test_input"
        output_folder = "test_output"
        files = ["page_000.jpg", "page_001.png", "page_002.gif"]
        mock_listdir.return_value = files
        mock_is_likely_spread.side_effect = lambda path, threshold: "page_002" in path

        processed_count, created_spread_count = self.handler.process_images(input_folder, output_folder)

        self.assertEqual(processed_count, 3)
        self.assertEqual(created_spread_count, 0)
        self.assertEqual(mock_is_likely_spread.call_count, 3)
        mock_is_likely_spread.assert_has_calls([
            call(os.path.join(input_folder, "page_001.png"), FakeConfig.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD),
            call(os.path.join(input_folder, "page_002.gif"), FakeConfig.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD),
            call(os.path.join(input_folder, "page_002.gif"), FakeConfig.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD)
        ], any_order=False)
        self.assertEqual(mock_copy2.call_count, 3)
        mock_copy2.assert_has_calls([
            call(os.path.join(input_folder, "page_000.jpg"), os.path.join(output_folder, "spread_000.jpg")),
            call(os.path.join(input_folder, "page_001.png"), os.path.join(output_folder, "spread_001.png")),
            call(os.path.join(input_folder, "page_002.gif"), os.path.join(output_folder, "spread_002.gif"))
        ])
        self.mock_status_callback.assert_any_call(f"Найдено {len(files)} файлов. Создание разворотов...")
        self.mock_status_callback.assert_any_call("Копирую обложку: page_000.jpg -> spread_000.jpg")
        self.mock_status_callback.assert_any_call("Копирую одиночную страницу (следующий - разворот): page_001.png -> spread_001.png")
        self.mock_status_callback.assert_any_call("Копирую готовый разворот: page_002.gif -> spread_002.gif")
        self.assertEqual(self.mock_progress_callback.call_count, len(files) + 1)
        self.mock_progress_callback.assert_has_calls([call(0, 3), call(1, 3), call(2, 3), call(3, 3)])

    @patch('rgo_lib_parser_by_b0s.is_likely_spread', return_value=False)
    def test_process_images_merge_two_singles(self, mock_is_likely_spread, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        input_folder = "test_input"
        output_folder = "test_output"
        files = ["page_000.jpg", "page_001.png", "page_002.bmp"]
        mock_listdir.return_value = files

        mock_img_left = MagicMock()
        mock_img_left.size = (800, 1000)
        mock_img_left.convert.return_value = mock_img_left
        mock_img_right = MagicMock()
        mock_img_right.size = (800, 1000)
        mock_img_right.convert.return_value = mock_img_right
        mock_img_last = MagicMock()
        mock_img_last.size = (800, 1000)

        def mock_image_open_side_effect(path):
            if "page_001" in path: return MagicMock(__enter__=MagicMock(return_value=mock_img_left))
            if "page_002" in path: return MagicMock(__enter__=MagicMock(return_value=mock_img_right))
            if "page_000" in path: return MagicMock(__enter__=MagicMock(return_value=mock_img_last))
            raise FileNotFoundError(f"Unexpected path in mock_image_open: {path}")
        MockImage.open.side_effect = mock_image_open_side_effect

        mock_spread_img = MagicMock()
        MockImage.new.return_value = mock_spread_img

        processed_count, created_spread_count = self.handler.process_images(input_folder, output_folder)

        self.assertEqual(processed_count, 3)
        self.assertEqual(created_spread_count, 1)
        self.assertEqual(mock_is_likely_spread.call_count, 2)
        mock_copy2.assert_called_once_with(
            os.path.join(input_folder, "page_000.jpg"),
            os.path.join(output_folder, "spread_000.jpg")
        )
        MockImage.open.assert_any_call(os.path.join(input_folder, "page_001.png"))
        MockImage.open.assert_any_call(os.path.join(input_folder, "page_002.bmp"))
        MockImage.new.assert_called_once_with('RGB', (1600, 1000), (255, 255, 255))
        mock_spread_img.paste.assert_has_calls([
            call(mock_img_left, (0, 0)),
            call(mock_img_right, (800, 0))
        ])
        expected_spread_filename = os.path.join(output_folder, "spread_001-002.jpg")
        mock_spread_img.save.assert_called_once_with(expected_spread_filename, "JPEG", quality=FakeConfig.JPEG_QUALITY, optimize=True)
        self.mock_status_callback.assert_any_call("Копирую обложку: page_000.jpg -> spread_000.jpg")
        self.mock_status_callback.assert_any_call("Создаю разворот: page_001.png + page_002.bmp -> spread_001-002.jpg")
        self.assertEqual(self.mock_progress_callback.call_count, 3)
        self.mock_progress_callback.assert_has_calls([call(0, 3), call(1, 3), call(3, 3)])

    @patch('rgo_lib_parser_by_b0s.is_likely_spread', return_value=False)
    def test_process_images_merge_different_heights(self, mock_is_likely_spread, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        input_folder = "test_input"
        output_folder = "test_output"
        files = ["page_000.jpg", "page_001.png", "page_002.bmp"]
        mock_listdir.return_value = files

        mock_img_left = MagicMock()
        mock_img_left.size = (800, 1000)
        mock_img_left.convert.return_value = mock_img_left
        mock_img_right = MagicMock()
        mock_img_right.size = (820, 1100)
        mock_img_right.convert.return_value = mock_img_right

        mock_resized_left = MagicMock()
        mock_resized_right = MagicMock()
        mock_resized_left.convert.return_value = mock_resized_left
        mock_resized_right.convert.return_value = mock_resized_right
        mock_img_left.resize.return_value = mock_resized_left
        mock_img_right.resize.return_value = mock_resized_right

        def mock_image_open_side_effect(path):
            if "page_001" in path: return MagicMock(__enter__=MagicMock(return_value=mock_img_left))
            if "page_002" in path: return MagicMock(__enter__=MagicMock(return_value=mock_img_right))
            if "page_000" in path: return MagicMock(__enter__=MagicMock(return_value=MagicMock(size=(800,1000))))
            raise FileNotFoundError(f"Unexpected path in mock_image_open: {path}")
        MockImage.open.side_effect = mock_image_open_side_effect

        mock_spread_img = MagicMock()
        MockImage.new.return_value = mock_spread_img

        self.handler.process_images(input_folder, output_folder)

        target_height = (1000 + 1100) // 2
        mock_img_left.resize.assert_called_once_with((840, target_height), ANY)
        mock_img_right.resize.assert_called_once_with((782, target_height), ANY)
        mock_spread_img.paste.assert_has_calls([
            call(mock_resized_left, (0, 0)),
            call(mock_resized_right, (840, 0))
        ])
        MockImage.new.assert_called_once_with('RGB', (840 + 782, target_height), (255, 255, 255))
        mock_spread_img.save.assert_called_once()

    def test_process_images_input_not_found(self, mock_open, mock_sleep, MockImage, mock_getsize, mock_listdir, mock_makedirs, mock_copy2, MockSession):
        input_folder = "non_existent"
        output_folder = "test_output"
        mock_listdir.side_effect = FileNotFoundError(f"Dir not found: {input_folder}")

        processed_count, created_spread_count = self.handler.process_images(input_folder, output_folder)

        self.assertEqual(processed_count, 0)
        self.assertEqual(created_spread_count, 0)
        mock_listdir.assert_called_once_with(input_folder)
        self.mock_status_callback.assert_any_call(f"Ошибка: Папка '{input_folder}' не найдена.")
        mock_copy2.assert_not_called()
        MockImage.open.assert_not_called()


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False, verbosity=2)
