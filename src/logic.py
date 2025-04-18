import base64
import logging
from pathlib import Path
import threading
import time
from typing import Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config, image_processing, utils
from .types import ProgressCallback, StatusCallback

logger = logging.getLogger(__name__)


class LibraryHandler:
    """Класс, инкапсулирующий логику скачивания страниц
    и делегирующий обработку изображений.
    """

    def __init__(
        self,
        status_callback: StatusCallback,  # Используем импортированный тип
        progress_callback: ProgressCallback,  # Используем импортированный тип
        stop_event: threading.Event,  # Можно использовать StopEvent из types.py, если он там определен
    ):
        """Инициализация обработчика.

        Args:
            status_callback: Функция для отправки сообщений о статусе (в GUI).
            progress_callback: Функция для обновления прогресса (в GUI).
            stop_event: Событие для сигнализации об остановке операции.
        """
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.stop_event = stop_event
        self.session: Optional[requests.Session] = None
        logger.info("LibraryHandler initialized")

    def _setup_session_with_retry(self) -> None:
        """Настраивает сессию requests с заголовками и стратегией повторов."""
        # ... (код без изменений) ...
        if self.session:
            logger.debug("Session already exists. Reusing.")
            return

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.DEFAULT_USER_AGENT})

        retry_strategy = Retry(
            total=config.MAX_RETRIES,
            status_forcelist=config.RETRY_ON_HTTP_CODES,
            backoff_factor=1,  # Задержка = backoff_factor * (2 ** (попытка - 1))
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        logger.info(
            f"Requests session created with retry strategy (max={config.MAX_RETRIES}, statuses={config.RETRY_ON_HTTP_CODES})"
        )

    def _get_initial_cookies(self) -> bool:
        """Пытается получить начальные сессионные куки с сайта.

        Returns:
            True, если куки успешно получены, иначе False.
        """
        # ... (код без изменений) ...
        try:  # Обертка для перехвата ошибки создания сессии
            if not self.session:
                self._setup_session_with_retry()
                if not self.session:
                    logger.error("Failed to setup session in _get_initial_cookies")
                    self.status_callback(
                        "Критическая ошибка: Не удалось создать сетевую сессию."
                    )
                    return False
        except Exception as setup_exc:
            logger.error(
                f"Failed to setup session during cookie retrieval: {setup_exc}",
                exc_info=True,
            )
            self.status_callback(
                f"Критическая ошибка при настройке сессии: {setup_exc}"
            )
            return False

        self.status_callback(
            f"Автоматическое получение сессионных куки с {config.INITIAL_COOKIE_URL}..."
        )
        logger.info(
            f"Attempting to get initial cookies from {config.INITIAL_COOKIE_URL}"
        )
        try:
            initial_response = self.session.get(
                config.INITIAL_COOKIE_URL, timeout=config.REQUEST_TIMEOUT
            )
            initial_response.raise_for_status()

            if self.session.cookies:
                cookie_names = list(self.session.cookies.keys())
                self.status_callback(f"Успешно получены куки: {cookie_names}")
                logger.info(f"Initial cookies obtained: {cookie_names}")
                return True
            else:
                self.status_callback(
                    "Предупреждение: Не удалось автоматически получить куки (сервер не установил?)."
                )
                logger.warning("Server did not set any cookies during initial request.")
                return False
        except requests.exceptions.Timeout:
            msg = f"Ошибка: Превышено время ожидания при получении куки с {config.INITIAL_COOKIE_URL}."
            self.status_callback(msg)
            logger.error(msg)
            return False
        except requests.exceptions.RequestException as e:
            msg = f"Ошибка при получении куки: {e}."
            self.status_callback(msg)
            logger.error(f"Error getting initial cookies: {e}", exc_info=True)
            return False

    def download_pages(
        self,
        base_url: str,
        url_ids: str,
        filename_pdf: str,
        total_pages: int,
        output_dir: str,
    ) -> Tuple[int, int]:
        """Скачивает все страницы книги.

        Args:
            base_url: Базовый URL до ID.
            url_ids: ID файла (часть URL).
            filename_pdf: Имя файла на сайте (используется для кодирования).
            total_pages: Общее количество страниц.
            output_dir: Папка для сохранения скачанных страниц.

        Returns:
            Кортеж (количество успешно скачанных страниц, общее количество страниц).
        """
        # ... (код без изменений, кроме удаления зависимостей, которые ушли в image_processing) ...
        self.stop_event.clear()
        if not self.session:
            self._setup_session_with_retry()
            if not self.session:
                logger.error("Failed to setup session for download.")
                self.status_callback(
                    "Критическая ошибка: Не удалось создать сетевую сессию для скачивания."
                )
                return 0, total_pages

        got_cookies = self._get_initial_cookies()
        if not got_cookies:
            self.status_callback(
                "Продолжаем без автоматических куки (могут быть проблемы)..."
            )
            logger.warning("Proceeding with download without initial cookies.")

        base_url = base_url.rstrip("/") + "/"
        url_ids = url_ids.rstrip("/") + "/"
        output_path = Path(output_dir)
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Ошибка создания папки для страниц '{output_dir}': {e}"
            self.status_callback(msg)
            logger.error(msg, exc_info=True)
            return 0, total_pages

        self.status_callback(
            f"Начинаем скачивание {total_pages} страниц в '{output_dir}'..."
        )
        logger.info(
            f"Starting download of {total_pages} pages to '{output_dir}'. BaseURL: {base_url}, IDs: {url_ids}, PDFName: {filename_pdf}"
        )
        self.progress_callback(0, total_pages)

        success_count = 0
        for i in range(total_pages):
            if self.stop_event.is_set():
                self.status_callback("--- Скачивание прервано пользователем ---")
                logger.info("Download interrupted by user.")
                break

            page_string = f"{filename_pdf}/{i}"
            try:
                page_b64_bytes = base64.b64encode(page_string.encode("utf-8"))
                page_b64_string = page_b64_bytes.decode("utf-8")
            except Exception as e:
                msg = f"Ошибка кодирования URL для стр. {i + 1}: {e}"
                self.status_callback(msg)
                logger.error(msg, exc_info=True)
                continue

            final_url = f"{base_url}{url_ids}{page_b64_string}"
            # Имя файла будет определено по Content-Type
            base_output_filename = output_path / f"page_{i:03d}"

            status_msg = f"Скачиваю страницу {i + 1}/{total_pages}..."
            self.status_callback(status_msg)
            logger.debug(f"Requesting page {i + 1}: {final_url}")

            try:
                response = self.session.get(final_url, timeout=config.REQUEST_TIMEOUT)
                logger.debug(f"Page {i + 1} response status: {response.status_code}")
                response.raise_for_status()  # Проверка на 4xx/5xx

                content_type = response.headers.get("Content-Type", "").lower()
                if "text/html" in content_type:
                    msg = f"Ошибка на стр. {i + 1}: Получен HTML вместо изображения. Проблема с сессией/URL?"
                    self.status_callback(msg)
                    logger.error(
                        f"{msg} URL: {final_url}. Content preview: {response.text[:200]}"
                    )
                    continue

                # Определяем расширение файла
                extension = ".jpg"
                if "png" in content_type:
                    extension = ".png"
                elif "gif" in content_type:
                    extension = ".gif"
                elif "bmp" in content_type:
                    extension = ".bmp"
                elif "tiff" in content_type:
                    extension = ".tiff"
                elif "jpeg" in content_type:
                    extension = ".jpeg"
                else:
                    logger.warning(
                        f"Unknown Content-Type '{content_type}' for page {i + 1}. Assuming .jpg"
                    )

                final_output_filename = base_output_filename.with_suffix(extension)
                logger.debug(f"Saving page {i + 1} to {final_output_filename}")

                # Записываем файл
                with open(final_output_filename, "wb") as f:
                    f.write(response.content)

                # Проверяем размер файла
                if final_output_filename.stat().st_size == 0:
                    msg = f"Предупреждение: Файл {final_output_filename.name} пустой."
                    self.status_callback(msg)
                    logger.warning(f"{msg} URL: {final_url}")
                else:
                    success_count += 1
                    logger.info(
                        f"Page {i + 1}/{total_pages} downloaded successfully as {final_output_filename.name}"
                    )

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else "N/A"
                msg = f"Ошибка HTTP {status_code} на стр. {i + 1} (после {config.MAX_RETRIES} попыток): {e}"
                self.status_callback(msg)
                logger.error(f"{msg} URL: {final_url}")
                if status_code in [401, 403]:
                    self.status_callback(
                        "   (Возможно, сессия истекла, куки неверны или доступ запрещен)"
                    )
            except requests.exceptions.Timeout:
                msg = f"Ошибка: Таймаут при скачивании стр. {i + 1} (после {config.MAX_RETRIES} попыток)."
                self.status_callback(msg)
                logger.error(f"{msg} URL: {final_url}")
            except requests.exceptions.RequestException as e:
                msg = f"Ошибка сети/сервера на стр. {i + 1} (после {config.MAX_RETRIES} попыток): {e}"
                self.status_callback(msg)
                logger.error(f"{msg} URL: {final_url}", exc_info=True)
            except OSError as e:
                msg = f"Ошибка записи файла для стр. {i + 1}: {e}"
                self.status_callback(msg)
                logger.error(f"{msg} Filename: {final_output_filename}", exc_info=True)
            except Exception as e:
                msg = f"Неожиданная ошибка на стр. {i + 1}: {e}"
                self.status_callback(msg)
                logger.error(f"{msg} URL: {final_url}", exc_info=True)

            finally:
                self.progress_callback(i + 1, total_pages)
                if not self.stop_event.is_set():
                    time.sleep(config.DEFAULT_DELAY_SECONDS)

        logger.info(f"Download finished. Success: {success_count}/{total_pages}")
        self.status_callback(
            f"Скачивание завершено. Успешно: {success_count} из {total_pages}."
        )
        return success_count, total_pages

    def process_images(self, input_folder: str, output_folder: str) -> Tuple[int, int]:
        """Делегирует обработку изображений (создание разворотов)
        специализированной функции.

        Args:
            input_folder: Папка со скачанными страницами.
            output_folder: Папка для сохранения разворотов.

        Returns:
            Кортеж (количество обработанных/скопированных файлов,
                     количество созданных разворотов).
        """
        return image_processing.process_images_in_folders(
            input_folder=input_folder,
            output_folder=output_folder,
            status_callback=self.status_callback,
            progress_callback=self.progress_callback,
            stop_event=self.stop_event,
            config=config,
            utils=utils,
            logger=logger,
        )
