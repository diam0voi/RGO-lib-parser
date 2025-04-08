import base64
import logging
import os
import shutil
import time
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple
import requests
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config, utils

logger = logging.getLogger(__name__)


StatusCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]


class LibraryHandler:
    """
    Класс, инкапсулирующий логику скачивания страниц
    и обработки изображений (создания разворотов).
    """
    def __init__(
        self,
        status_callback: StatusCallback,
        progress_callback: ProgressCallback,
        stop_event: threading.Event
    ):
        """
        Инициализация обработчика.

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
        if self.session:
            logger.debug("Session already exists. Reusing.")
            return

        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.DEFAULT_USER_AGENT})

        retry_strategy = Retry(
            total=config.MAX_RETRIES,
            status_forcelist=config.RETRY_ON_HTTP_CODES,
            backoff_factor=1, # Задержка = backoff_factor * (2 ** (попытка - 1))
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        logger.info(f"Requests session created with retry strategy (max={config.MAX_RETRIES}, statuses={config.RETRY_ON_HTTP_CODES})")


    def _get_initial_cookies(self) -> bool:
        """
        Пытается получить начальные сессионные куки с сайта.

        Returns:
            True, если куки успешно получены, иначе False.
        """
        try: # Обертка для перехвата ошибки создания сессии
            if not self.session:
                self._setup_session_with_retry()
                if not self.session:
                    logger.error("Failed to setup session in _get_initial_cookies")
                    self.status_callback("Критическая ошибка: Не удалось создать сетевую сессию.")
                    return False
        except Exception as setup_exc:
            logger.error(f"Failed to setup session during cookie retrieval: {setup_exc}", exc_info=True)
            self.status_callback(f"Критическая ошибка при настройке сессии: {setup_exc}")
            return False


        self.status_callback(f"Автоматическое получение сессионных куки с {config.INITIAL_COOKIE_URL}...")
        logger.info(f"Attempting to get initial cookies from {config.INITIAL_COOKIE_URL}")
        try:
            initial_response = self.session.get(config.INITIAL_COOKIE_URL, timeout=config.REQUEST_TIMEOUT)
            initial_response.raise_for_status()

            if self.session.cookies:
                cookie_names = list(self.session.cookies.keys())
                self.status_callback(f"Успешно получены куки: {cookie_names}")
                logger.info(f"Initial cookies obtained: {cookie_names}")
                return True
            else:
                self.status_callback("Предупреждение: Не удалось автоматически получить куки (сервер не установил?).")
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
        output_dir: str
    ) -> Tuple[int, int]:
        """
        Скачивает все страницы книги.

        Args:
            base_url: Базовый URL до ID.
            url_ids: ID файла (часть URL).
            filename_pdf: Имя файла на сайте (используется для кодирования).
            total_pages: Общее количество страниц.
            output_dir: Папка для сохранения скачанных страниц.

        Returns:
            Кортеж (количество успешно скачанных страниц, общее количество страниц).
        """
        self.stop_event.clear()
        if not self.session:
            self._setup_session_with_retry()
            if not self.session:
                logger.error("Failed to setup session for download.")
                self.status_callback("Критическая ошибка: Не удалось создать сетевую сессию для скачивания.")
                return 0, total_pages

        got_cookies = self._get_initial_cookies()
        if not got_cookies:
             self.status_callback("Продолжаем без автоматических куки (могут быть проблемы)...")
             logger.warning("Proceeding with download without initial cookies.")

        base_url = base_url.rstrip('/') + '/'
        url_ids = url_ids.rstrip('/') + '/'
        output_path = Path(output_dir)
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Ошибка создания папки для страниц '{output_dir}': {e}"
            self.status_callback(msg)
            logger.error(msg, exc_info=True)
            return 0, total_pages

        self.status_callback(f"Начинаем скачивание {total_pages} страниц в '{output_dir}'...")
        logger.info(f"Starting download of {total_pages} pages to '{output_dir}'. BaseURL: {base_url}, IDs: {url_ids}, PDFName: {filename_pdf}")
        self.progress_callback(0, total_pages)

        success_count = 0
        for i in range(total_pages):
            if self.stop_event.is_set():
                self.status_callback("--- Скачивание прервано пользователем ---")
                logger.info("Download interrupted by user.")
                break

            page_string = f"{filename_pdf}/{i}"
            try:
                page_b64_bytes = base64.b64encode(page_string.encode('utf-8'))
                page_b64_string = page_b64_bytes.decode('utf-8')
            except Exception as e:
                msg = f"Ошибка кодирования URL для стр. {i+1}: {e}"
                self.status_callback(msg)
                logger.error(msg, exc_info=True)
                continue

            final_url = f"{base_url}{url_ids}{page_b64_string}"
            # Имя файла будет определено по Content-Type
            base_output_filename = output_path / f"page_{i:03d}"

            status_msg = f"Скачиваю страницу {i+1}/{total_pages}..."
            self.status_callback(status_msg)
            logger.debug(f"Requesting page {i+1}: {final_url}")

            try:
                response = self.session.get(final_url, timeout=config.REQUEST_TIMEOUT)
                logger.debug(f"Page {i+1} response status: {response.status_code}")
                response.raise_for_status() # Проверка на 4xx/5xx

                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type:
                     msg = f"Ошибка на стр. {i+1}: Получен HTML вместо изображения. Проблема с сессией/URL?"
                     self.status_callback(msg)
                     logger.error(f"{msg} URL: {final_url}. Content preview: {response.text[:200]}")
                     continue

                # Определяем расширение файла
                extension = ".jpg"
                if 'png' in content_type: extension = ".png"
                elif 'gif' in content_type: extension = ".gif"
                elif 'bmp' in content_type: extension = ".bmp"
                elif 'tiff' in content_type: extension = ".tiff"
                elif 'jpeg' in content_type: extension = ".jpeg"
                else:
                    logger.warning(f"Unknown Content-Type '{content_type}' for page {i+1}. Assuming .jpg")

                final_output_filename = base_output_filename.with_suffix(extension)
                logger.debug(f"Saving page {i+1} to {final_output_filename}")

                # Записываем файл
                with open(final_output_filename, 'wb') as f:
                    f.write(response.content)

                # Проверяем размер файла
                if final_output_filename.stat().st_size == 0:
                    msg = f"Предупреждение: Файл {final_output_filename.name} пустой."
                    self.status_callback(msg)
                    logger.warning(f"{msg} URL: {final_url}")
                else:
                     success_count += 1
                     logger.info(f"Page {i+1}/{total_pages} downloaded successfully as {final_output_filename.name}")

            except requests.exceptions.HTTPError as e:
                 status_code = e.response.status_code if e.response else 'N/A'
                 msg = f"Ошибка HTTP {status_code} на стр. {i+1} (после {config.MAX_RETRIES} попыток): {e}"
                 self.status_callback(msg)
                 logger.error(f"{msg} URL: {final_url}")
                 if status_code in [401, 403]:
                     self.status_callback("   (Возможно, сессия истекла, куки неверны или доступ запрещен)")
            except requests.exceptions.Timeout:
                 msg = f"Ошибка: Таймаут при скачивании стр. {i+1} (после {config.MAX_RETRIES} попыток)."
                 self.status_callback(msg)
                 logger.error(f"{msg} URL: {final_url}")
            except requests.exceptions.RequestException as e:
                msg = f"Ошибка сети/сервера на стр. {i+1} (после {config.MAX_RETRIES} попыток): {e}"
                self.status_callback(msg)
                logger.error(f"{msg} URL: {final_url}", exc_info=True)
            except IOError as e:
                msg = f"Ошибка записи файла для стр. {i+1}: {e}"
                self.status_callback(msg)
                logger.error(f"{msg} Filename: {final_output_filename}", exc_info=True)
            except Exception as e:
                msg = f"Неожиданная ошибка на стр. {i+1}: {e}"
                self.status_callback(msg)
                logger.error(f"{msg} URL: {final_url}", exc_info=True)

            finally:
                self.progress_callback(i + 1, total_pages)
                if not self.stop_event.is_set():
                    time.sleep(config.DEFAULT_DELAY_SECONDS)

        logger.info(f"Download finished. Success: {success_count}/{total_pages}")
        self.status_callback(f"Скачивание завершено. Успешно: {success_count} из {total_pages}.")
        return success_count, total_pages


    def process_images(self, input_folder: str, output_folder: str) -> Tuple[int, int]:
        """
        Обрабатывает скачанные изображения: копирует обложки/развороты,
        склеивает одиночные страницы.

        Args:
            input_folder: Папка со скачанными страницами.
            output_folder: Папка для сохранения разворотов.

        Returns:
            Кортеж (количество обработанных/скопированных файлов,
                     количество созданных разворотов).
        """
        self.stop_event.clear()
        input_path = Path(input_folder)
        output_path = Path(output_folder)

        self.status_callback(f"Начинаем обработку изображений из '{input_folder}' в '{output_folder}'...")
        logger.info(f"Starting image processing. Input: '{input_path}', Output: '{output_path}'")

        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Ошибка создания папки для разворотов '{output_folder}': {e}"
            self.status_callback(msg)
            logger.error(msg, exc_info=True)
            return 0, 0

        try:
            all_files = [
                f for f in input_path.iterdir()
                if f.is_file() and f.suffix.lower() in config.IMAGE_EXTENSIONS
            ]
            logger.info(f"Found {len(all_files)} potential image files in {input_path}.")
        except FileNotFoundError:
            msg = f"Ошибка: Папка со страницами '{input_folder}' не найдена."
            self.status_callback(msg)
            logger.error(msg)
            return 0, 0
        except OSError as e:
            msg = f"Ошибка чтения папки '{input_folder}': {e}"
            self.status_callback(msg)
            logger.error(msg, exc_info=True)
            return 0, 0

        numbered_files = []
        for f in all_files:
            page_num = utils.get_page_number(f.name)
            if page_num != -1:
                numbered_files.append((page_num, f))
            else:
                logger.warning(f"Skipping file without page number: {f.name}")

        sorted_files = [f for _, f in sorted(numbered_files)]
        total_files_to_process = len(sorted_files)
        logger.info(f"Found {total_files_to_process} numbered image files to process.")

        if not sorted_files:
            self.status_callback("В папке не найдено подходящих файлов изображений с номерами.")
            logger.warning(f"No processable image files found in {input_path}")
            return 0, 0

        self.status_callback(f"Найдено {total_files_to_process} файлов. Создание разворотов...")
        self.progress_callback(0, total_files_to_process)

        page_index = 0
        processed_count = 0 # Сколько исходных скопировано или склеено
        created_spread_count = 0 # Сколько новых создано

        while page_index < total_files_to_process:
            if self.stop_event.is_set():
                self.status_callback("--- Обработка прервана пользователем ---")
                logger.info("Processing interrupted by user.")
                break

            current_file_path = sorted_files[page_index]
            current_page_num = utils.get_page_number(current_file_path.name)
            current_is_spread = page_index > 0 and utils.is_likely_spread(
                current_file_path, config.DEFAULT_ASPECT_RATIO_THRESHOLD
            )

            logger.debug(f"Processing index {page_index}: {current_file_path.name} (Page: {current_page_num}, IsSpread: {current_is_spread})")

            processed_increment = 0 # Обработали на итерации

            # --- Вариант 1: Копирование (Обложка или уже готовый разворот) ---
            if page_index == 0 or current_is_spread:
                output_filename = f"spread_{current_page_num:03d}{current_file_path.suffix}"
                output_file_path = output_path / output_filename
                action_desc = 'обложку' if page_index == 0 else 'готовый разворот'
                status_msg = f"Копирую {action_desc}: {current_file_path.name} -> {output_filename}"
                self.status_callback(status_msg)
                logger.info(f"Copying {'cover' if page_index == 0 else 'existing spread'}: {current_file_path.name} -> {output_filename}")
                try:
                    shutil.copy2(current_file_path, output_file_path)
                    processed_increment = 1
                except Exception as e:
                    msg = f"Ошибка при копировании {current_file_path.name}: {e}"
                    self.status_callback(msg)
                    logger.error(msg, exc_info=True)
                page_index += 1

            # --- Вариант 2: Текущий файл - одиночная страница ---
            else:
                # Проверяем, есть ли следующий файл
                if page_index + 1 < total_files_to_process:
                    next_file_path = sorted_files[page_index + 1]
                    next_page_num = utils.get_page_number(next_file_path.name)
                    # Определяем, является ли СЛЕДУЮЩИЙ файл одиночным
                    next_is_single = not utils.is_likely_spread(
                        next_file_path, config.DEFAULT_ASPECT_RATIO_THRESHOLD
                    )
                    logger.debug(f"  Next file: {next_file_path.name} (Page: {next_page_num}, IsSingle: {next_is_single})")

                    # --- Вариант 2.1: Следующий тоже одиночный ---
                    if next_is_single:
                        output_filename = f"spread_{current_page_num:03d}-{next_page_num:03d}.jpg"
                        output_file_path = output_path / output_filename
                        status_msg = f"Создаю разворот: {current_file_path.name} + {next_file_path.name} -> {output_filename}"
                        self.status_callback(status_msg)
                        logger.info(f"Creating spread: {current_file_path.name} + {next_file_path.name} -> {output_filename}")

                        try:
                            with Image.open(current_file_path) as img_left, \
                                 Image.open(next_file_path) as img_right:

                                w_left, h_left = img_left.size
                                w_right, h_right = img_right.size

                                # Приводим к одной высоте по LANCZOS, если нужно
                                if h_left != h_right:
                                    target_height = max(h_left, h_right) # Берем максимальную высоту
                                    logger.debug(f"    Resizing images to target height: {target_height}px (using LANCZOS)")

                                    # Масштабируем левое изображение
                                    ratio_left = target_height / h_left
                                    w_left_final = int(w_left * ratio_left)
                                    img_left_final = img_left.resize((w_left_final, target_height), Image.Resampling.LANCZOS)
                                    logger.debug(f"    Left resized to: {w_left_final}x{target_height}")

                                    # Масштабируем правое изображение
                                    ratio_right = target_height / h_right
                                    w_right_final = int(w_right * ratio_right)
                                    img_right_final = img_right.resize((w_right_final, target_height), Image.Resampling.LANCZOS)
                                    logger.debug(f"    Right resized to: {w_right_final}x{target_height}")
                                else:
                                    target_height = h_left
                                    img_left_final = img_left
                                    img_right_final = img_right
                                    w_left_final = w_left
                                    w_right_final = w_right
                                    logger.debug("    Heights match, no resize needed.")

                                total_width = w_left_final + w_right_final
                                logger.debug(f"    Creating new spread image: {total_width}x{target_height}")
                                spread_img = Image.new('RGB', (total_width, target_height), (255, 255, 255))
                                spread_img.paste(img_left_final.convert('RGB'), (0, 0))
                                spread_img.paste(img_right_final.convert('RGB'), (w_left_final, 0))
                                spread_img.save(output_file_path, "JPEG", quality=config.JPEG_QUALITY, optimize=True)

                                created_spread_count += 1
                                processed_increment = 2
                                logger.info(f"    Spread created successfully: {output_filename}")

                        except Exception as e:
                            msg = f"Ошибка при создании разворота для {current_file_path.name} и {next_file_path.name}: {e}"
                            self.status_callback(msg)
                            logger.error(msg, exc_info=True)
                            # Пропускаем оба файла, но считаем обработанными
                            processed_increment = 2
                        page_index += 2 # Переходим через пару

                    # --- Вариант 2.2: Текущий одиночный, следующий - разворот ---
                    else:
                        output_filename = f"spread_{current_page_num:03d}{current_file_path.suffix}"
                        output_file_path = output_path / output_filename
                        status_msg = f"Копирую одиночную страницу (следующий - разворот): {current_file_path.name} -> {output_filename}"
                        self.status_callback(status_msg)
                        logger.info(f"Copying single page (next is spread): {current_file_path.name} -> {output_filename}")
                        try:
                            shutil.copy2(current_file_path, output_file_path)
                            processed_increment = 1
                        except Exception as e:
                            msg = f"Ошибка при копировании одиночной {current_file_path.name}: {e}"
                            self.status_callback(msg)
                            logger.error(msg, exc_info=True)
                        page_index += 1 # Переходим к следующему файлу (который разворот)

                # --- Вариант 2.3: Текущий одиночный - последний файл ---
                else:
                    output_filename = f"spread_{current_page_num:03d}{current_file_path.suffix}"
                    output_file_path = output_path / output_filename
                    status_msg = f"Копирую последнюю одиночную страницу: {current_file_path.name} -> {output_filename}"
                    self.status_callback(status_msg)
                    logger.info(f"Copying last single page: {current_file_path.name} -> {output_filename}")
                    try:
                        shutil.copy2(current_file_path, output_file_path)
                        processed_increment = 1
                    except Exception as e:
                        msg = f"Ошибка при копировании последней одиночной {current_file_path.name}: {e}"
                        self.status_callback(msg)
                        logger.error(msg, exc_info=True)
                    page_index += 1 # Завершаем цикл

            processed_count += processed_increment
            self.progress_callback(page_index, total_files_to_process)
            # Чтобы GUI успевал обновляться
            time.sleep(0.01)


        logger.info(f"Processing finished. Processed/copied: {processed_count}, Spreads created: {created_spread_count}")
        self.status_callback(f"Обработка завершена. Обработано/скопировано: {processed_count}. Создано разворотов: {created_spread_count}.")
        return processed_count, created_spread_count
