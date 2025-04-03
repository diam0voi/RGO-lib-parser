import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
import base64
import os
import re
import time
import threading
from PIL import Image, ImageTk
import sys
import shutil
import json
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
import logging.handlers

import config

# --- Логирование ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = config.LOG_FILE

try:
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=2*1024*1024, backupCount=2, encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
except Exception as log_e:
    print(f"FATAL: Could not configure file logging to {log_file}: {log_e}")

logging.info("="*20 + " Приложение запущено " + "="*20)


# --- Хелперы ---
def get_page_number(filename):  # Из имени в base64
    match = re.search(r'\d+', filename)
    return int(match.group()) if match else -1


def is_likely_spread(image_path, threshold):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if height == 0: return False
            aspect_ratio = width / height
            return aspect_ratio > threshold
    except Exception as e:
        logging.warning(f"Could not check aspect ratio for {image_path}: {e}")
        return False


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# --- Класс логики ---
class LibraryHandler:
    def __init__(self, status_callback, progress_callback, stop_event):
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.stop_event = stop_event
        self.session = None

    def _setup_session_with_retry(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.DEFAULT_USER_AGENT})

        retry_strategy = Retry(
            total=config.MAX_RETRIES,
            status_forcelist=config.RETRY_ON_HTTP_CODES,
            backoff_factor=1  # Задержка = backoff factor * (2 ** ({number of total retries} - 1))
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        logging.info(f"Requests session created with retry strategy (max={config.MAX_RETRIES}, statuses={config.RETRY_ON_HTTP_CODES})")

    def _get_initial_cookies(self):
        if not self.session:
            self._setup_session_with_retry()

        self.status_callback(f"Автоматическое получение сессионных куки с {config.INITIAL_COOKIE_URL}...")
        try:
            initial_response = self.session.get(config.INITIAL_COOKIE_URL, timeout=(10, 20))
            initial_response.raise_for_status()
            if self.session.cookies:
                cookie_names = list(self.session.cookies.keys())
                self.status_callback(f"Успешно получены куки: {cookie_names}")
                logging.info(f"Initial cookies obtained: {cookie_names}")
                return True
            else:
                self.status_callback("Предупреждение: Не удалось автоматически получить куки (сервер не установил?).")
                logging.warning("Server did not set any cookies during initial request.")
                return False
        except requests.exceptions.Timeout:
             msg = f"Ошибка: Превышено время ожидания при получении куки с {config.INITIAL_COOKIE_URL}."
             self.status_callback(msg)
             logging.error(msg)
             return False
        except requests.exceptions.RequestException as e:
             msg = f"Ошибка при получении куки: {e}."
             self.status_callback(msg)
             logging.error(f"Error getting initial cookies: {e}", exc_info=True)
             return False

    def download_pages(self, base_url, url_ids, filename_pdf, total_pages, output_dir):
        self.stop_event.clear()
        if not self.session:
            self._setup_session_with_retry()
        got_cookies = self._get_initial_cookies()
        if not got_cookies:
             self.status_callback("Продолжаем без автоматических куки (могут быть проблемы)...")

        self.status_callback(f"Начинаем скачивание {total_pages} страниц в '{output_dir}'...")
        logging.info(f"Starting download of {total_pages} pages to '{output_dir}'. BaseURL: {base_url}, IDs: {url_ids}, PDFName: {filename_pdf}")
        self.progress_callback(0, total_pages)

        success_count = 0
        for i in range(total_pages):
            if self.stop_event.is_set():
                self.status_callback("--- Скачивание прервано пользователем ---")
                logging.info("Download interrupted by user.")
                break

            page_string = f"{filename_pdf}/{i}"
            page_b64_bytes = base64.b64encode(page_string.encode('utf-8'))
            page_b64_string = page_b64_bytes.decode('utf-8')
            final_url = f"{base_url}{url_ids}{page_b64_string}"
            base_output_filename = os.path.join(output_dir, f"page_{i:03d}")

            status_msg = f"Скачиваю страницу {i+1}/{total_pages}..."
            self.status_callback(status_msg) # Обновляем GUI лог

            try:
                logging.debug(f"Requesting page {i+1}: {final_url}")
                response = self.session.get(final_url, timeout=(10, 30))
                logging.debug(f"Page {i+1} response status: {response.status_code}")
                response.raise_for_status()

                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type:
                     msg = f"Ошибка на стр. {i+1}: Получен HTML вместо изображения. Проблема с сессией?"
                     self.status_callback(msg)
                     logging.error(f"{msg} URL: {final_url}")
                     continue

                extension = ".jpg"
                if 'png' in content_type: extension = ".png"
                elif 'gif' in content_type: extension = ".gif"
                elif 'bmp' in content_type: extension = ".bmp"
                elif 'tiff' in content_type: extension = ".tiff"
                elif 'jpeg' in content_type: extension = ".jpeg"

                final_output_filename = base_output_filename + extension
                logging.debug(f"Saving page {i+1} to {final_output_filename}")

                with open(final_output_filename, 'wb') as f:
                    f.write(response.content)

                if os.path.getsize(final_output_filename) == 0:
                    msg = f"Предупреждение: Файл {os.path.basename(final_output_filename)} пустой."
                    self.status_callback(msg)
                    logging.warning(f"{msg} URL: {final_url}")
                else:
                     success_count += 1
                     logging.info(f"Page {i+1}/{total_pages} downloaded successfully as {os.path.basename(final_output_filename)}")

            except requests.exceptions.HTTPError as e:
                 msg = f"Ошибка HTTP {e.response.status_code} на стр. {i+1} (после {config.MAX_RETRIES} попыток): {e}"
                 self.status_callback(msg)
                 logging.error(f"{msg} URL: {final_url}")
                 if e.response.status_code in [401, 403]:
                     self.status_callback("   (Возможно, сессия истекла или куки неверны)")
            except requests.exceptions.Timeout:
                 msg = f"Ошибка: Таймаут при скачивании стр. {i+1} (после {config.MAX_RETRIES} попыток)."
                 self.status_callback(msg)
                 logging.error(f"{msg} URL: {final_url}")
            except requests.exceptions.RequestException as e:
                msg = f"Ошибка сети/сервера на стр. {i+1} (после {config.MAX_RETRIES} попыток): {e}"
                self.status_callback(msg)
                logging.error(f"{msg} URL: {final_url}", exc_info=True)
            except IOError as e:
                msg = f"Ошибка записи файла для стр. {i+1}: {e}"
                self.status_callback(msg)
                logging.error(f"{msg} Filename: {final_output_filename}", exc_info=True)
            except Exception as e:
                msg = f"Неожиданная ошибка на стр. {i+1}: {e}"
                self.status_callback(msg)
                logging.error(f"{msg} URL: {final_url}", exc_info=True)

            finally:
                self.progress_callback(i + 1, total_pages)
                if not self.stop_event.is_set():
                    time.sleep(config.DEFAULT_DELAY_SECONDS)

        logging.info(f"Download finished. Success: {success_count}/{total_pages}")
        return success_count, total_pages


    def process_images(self, input_folder, output_folder):
        self.stop_event.clear()
        self.status_callback(f"Начинаем обработку изображений из '{input_folder}' в '{output_folder}'...")
        logging.info(f"Starting image processing. Input: '{input_folder}', Output: '{output_folder}'")

        try:
            all_files = [f for f in os.listdir(input_folder) if f.lower().endswith(config.IMAGE_EXTENSIONS)]
            logging.info(f"Found {len(all_files)} potential image files.")
        except FileNotFoundError:
            msg = f"Ошибка: Папка '{input_folder}' не найдена."
            self.status_callback(msg)
            logging.error(msg)
            return 0, 0

        sorted_files = sorted([f for f in all_files if get_page_number(f) != -1], key=get_page_number)
        total_files_to_process = len(sorted_files)
        logging.info(f"Found {total_files_to_process} numbered image files to process.")

        if not sorted_files:
            self.status_callback("В папке не найдено подходящих файлов изображений с номерами.")
            return 0, 0

        self.status_callback(f"Найдено {total_files_to_process} файлов. Создание разворотов...")
        self.progress_callback(0, total_files_to_process)

        page_index = 0
        processed_count = 0
        created_spread_count = 0

        while page_index < len(sorted_files):
            if self.stop_event.is_set():
                self.status_callback("--- Обработка прервана пользователем ---")
                logging.info("Processing interrupted by user.")
                break

            current_file = sorted_files[page_index]
            current_path = os.path.join(input_folder, current_file)
            current_page_num = get_page_number(current_file)
            current_is_spread = page_index > 0 and is_likely_spread(current_path, config.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD)
            logging.debug(f"Processing index {page_index}: {current_file} (Page: {current_page_num}, IsSpread: {current_is_spread})")

            processed_increment = 0

            # Вариант 1: Копирование обложки или готового разворота
            if current_is_spread or page_index == 0:
                _, ext = os.path.splitext(current_file)
                output_filename = f"spread_{current_page_num:03d}{ext}"
                output_path = os.path.join(output_folder, output_filename)
                status_msg = f"Копирую {'обложку' if page_index == 0 else 'готовый разворот'}: {current_file} -> {output_filename}"
                self.status_callback(status_msg)
                try:
                    shutil.copy2(current_path, output_path)
                    processed_increment = 1
                    logging.info(f"Copied {'cover' if page_index == 0 else 'spread'}: {current_file} -> {output_filename}")
                except Exception as e:
                    msg = f"Ошибка при копировании {current_file}: {e}"
                    self.status_callback(msg)
                    logging.error(msg, exc_info=True)
                page_index += 1

            # Вариант 2: Текущий файл - одиночная страница
            else:
                if page_index + 1 < len(sorted_files):
                    next_file = sorted_files[page_index + 1]
                    next_path = os.path.join(input_folder, next_file)
                    next_page_num = get_page_number(next_file)
                    next_is_single = not is_likely_spread(next_path, config.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD)
                    logging.debug(f"  Next file: {next_file} (Page: {next_page_num}, IsSingle: {next_is_single})")

                    # Вариант 2.1: Следующий тоже одиночный - СКЛЕИВАЕМ
                    if next_is_single:
                        output_filename = f"spread_{current_page_num:03d}-{next_page_num:03d}.jpg"
                        output_path = os.path.join(output_folder, output_filename)
                        status_msg = f"Создаю разворот: {current_file} + {next_file} -> {output_filename}"
                        self.status_callback(status_msg)
                        logging.info(f"Creating spread: {current_file} + {next_file} -> {output_filename}")
                        try:
                            with Image.open(current_path) as img_left, Image.open(next_path) as img_right:
                                w_left, h_left = img_left.size
                                w_right, h_right = img_right.size

                                if h_left != h_right:  # Усредняем по LANCZOS
                                    target_height = (h_left + h_right) // 2
                                    logging.debug(f"    Resizing images to target height: {target_height}px")
                                    ratio_left = target_height / h_left
                                    w_left_final = int(w_left * ratio_left)
                                    img_left_final = img_left.resize((w_left_final, target_height), Image.Resampling.LANCZOS)
                                    ratio_right = target_height / h_right
                                    w_right_final = int(w_right * ratio_right)
                                    img_right_final = img_right.resize((w_right_final, target_height), Image.Resampling.LANCZOS)
                                else:
                                    target_height = h_left
                                    img_left_final = img_left
                                    img_right_final = img_right
                                    w_left_final = w_left
                                    w_right_final = w_right

                                total_width = w_left_final + w_right_final
                                spread_img = Image.new('RGB', (total_width, target_height), (255, 255, 255))
                                spread_img.paste(img_left_final.convert('RGB'), (0, 0))
                                spread_img.paste(img_right_final.convert('RGB'), (w_left_final, 0))
                                spread_img.save(output_path, "JPEG", quality=config.JPEG_QUALITY, optimize=True)

                                created_spread_count += 1
                                processed_increment = 2
                                logging.info(f"    Spread created successfully.")
                        except Exception as e:
                            msg = f"Ошибка при создании разворота для {current_file} и {next_file}: {e}"
                            self.status_callback(msg)
                            logging.error(msg, exc_info=True)
                            processed_increment = 2
                        page_index += 2

                    # Вариант 2.2: Текущий одиночный, следующий - разворот
                    else:
                        _, ext = os.path.splitext(current_file)
                        output_filename = f"spread_{current_page_num:03d}{ext}"
                        output_path = os.path.join(output_folder, output_filename)
                        status_msg = f"Копирую одиночную страницу (следующий - разворот): {current_file} -> {output_filename}"
                        self.status_callback(status_msg)
                        logging.info(f"Copying single page (next is spread): {current_file} -> {output_filename}")
                        try:
                            shutil.copy2(current_path, output_path)
                            processed_increment = 1
                        except Exception as e:
                            msg = f"Ошибка при копировании одиночной {current_file}: {e}"
                            self.status_callback(msg)
                            logging.error(msg, exc_info=True)
                        page_index += 1
                # Вариант 2.3: Текущий одиночный - последний файл
                else:
                    _, ext = os.path.splitext(current_file)
                    output_filename = f"spread_{current_page_num:03d}{ext}"
                    output_path = os.path.join(output_folder, output_filename)
                    status_msg = f"Копирую последнюю одиночную страницу: {current_file} -> {output_filename}"
                    self.status_callback(status_msg)
                    logging.info(f"Copying last single page: {current_file} -> {output_filename}")
                    try:
                        shutil.copy2(current_path, output_path)
                        processed_increment = 1
                    except Exception as e:
                        msg = f"Ошибка при копировании последней одиночной {current_file}: {e}"
                        self.status_callback(msg)
                        logging.error(msg, exc_info=True)
                    page_index += 1

            processed_count += processed_increment
            self.progress_callback(page_index, total_files_to_process)

        logging.info(f"Processing finished. Processed/copied: {processed_count}, Spreads created: {created_spread_count}")
        return processed_count, created_spread_count


# --- Класс GUI ---
class JournalDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.original_title = "Загрузчик + склейщик файлов библиотеки РГО. v1.4 by b0s"
        self.root.title(self.original_title)
        self.root.minsize(600, 650)

        # --- Иконка ---
        try:
            window_icon_path = resource_path("window_bnwbook.png")
            pil_icon = Image.open(window_icon_path)
            self.window_icon_image = ImageTk.PhotoImage(pil_icon)
            self.root.iconphoto(True, self.window_icon_image)
        except Exception as e:
            logging.warning(f"Could not set window icon: {e}", exc_info=True)

        # --- Состояния ---
        self.stop_event = threading.Event()
        self.current_thread = None
        self.handler = LibraryHandler(
            status_callback=self._update_status_safe,
            progress_callback=self._update_progress_safe,
            stop_event=self.stop_event
        )

        # --- Стили ---
        style = ttk.Style()
        style.configure("TLabel", padding=5)
        style.configure("TButton", padding=5)
        style.configure("TEntry", padding=5)
        style.configure("Stop.TButton", foreground="red", font=('Helvetica', 9, 'bold'))

        # --- Фрейм ввода ---
        input_frame = ttk.LabelFrame(root, text="Параметры", padding=10)
        input_frame.pack(padx=10, pady=(10,5), fill=tk.X)

        # --- Поля ввода ---
        ttk.Label(input_frame, text="Базовый URL (до ID):").grid(row=0, column=0, sticky=tk.W)
        self.url_base_entry = ttk.Entry(input_frame, width=60)
        self.url_base_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW)

        ttk.Label(input_frame, text="ID файла (часть URL):").grid(row=1, column=0, sticky=tk.W)
        self.url_ids_entry = ttk.Entry(input_frame, width=60)
        self.url_ids_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW)

        ttk.Label(input_frame, text="Имя файла на сайте:").grid(row=2, column=0, sticky=tk.W)
        self.pdf_filename_entry = ttk.Entry(input_frame, width=60)
        self.pdf_filename_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW)

        ttk.Label(input_frame, text="Кол-во страниц:").grid(row=3, column=0, sticky=tk.W)
        self.total_pages_entry = ttk.Entry(input_frame, width=10)
        self.total_pages_entry.grid(row=3, column=1, sticky=tk.W)

        # --- Пути ---
        path_frame = ttk.Frame(input_frame)
        path_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=(10, 0))

        ttk.Label(path_frame, text="Папка для страниц:").grid(row=0, column=0, sticky=tk.W)
        self.pages_dir_entry = ttk.Entry(path_frame, width=45)
        self.pages_dir_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 5))
        self.browse_pages_button = ttk.Button(path_frame, text="Обзор...", command=self.browse_output_pages)
        self.browse_pages_button.grid(row=0, column=2)

        ttk.Label(path_frame, text="Папка для разворотов:").grid(row=1, column=0, sticky=tk.W)
        self.spreads_dir_entry = ttk.Entry(path_frame, width=45)
        self.spreads_dir_entry.grid(row=1, column=1, sticky=tk.EW, padx=(0, 5))
        self.browse_spreads_button = ttk.Button(path_frame, text="Обзор...", command=self.browse_output_spreads)
        self.browse_spreads_button.grid(row=1, column=2)

        path_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(1, weight=1)

        # --- Фрейм управления ---
        control_frame = ttk.Frame(root, padding=(10, 5, 10, 5))
        control_frame.pack(fill=tk.X)

        self.run_all_button = ttk.Button(control_frame, text="Скачать и создать развороты", command=self.run_all)
        self.run_all_button.pack(side=tk.LEFT, padx=5)
        self.download_button = ttk.Button(control_frame, text="Только скачать страницы", command=self.run_download)
        self.download_button.pack(side=tk.LEFT, padx=5)
        self.process_button = ttk.Button(control_frame, text="Только создать развороты", command=self.run_processing)
        self.process_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(control_frame, text="СТОП", command=self.stop_action, state=tk.DISABLED, style="Stop.TButton")
        self.stop_button.pack(side=tk.RIGHT, padx=15)

        # --- Прогресс-бар ---
        progress_frame = ttk.Frame(root, padding=(10, 0, 10, 5))
        progress_frame.pack(fill=tk.X)
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True)

        # --- Лог ---
        status_frame = ttk.LabelFrame(root, text="Статус", padding=10)
        status_frame.pack(padx=10, pady=(0,10), fill=tk.BOTH, expand=True)
        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.status_text.pack(fill=tk.BOTH, expand=True)

        self.initial_settings = {}
        self.load_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)


    # --- Методы для GUI ---
    def browse_output_pages(self):
        initial_dir = self.pages_dir_entry.get()
        if not os.path.isdir(initial_dir):
            initial_dir = os.path.expanduser("~") # Домашняя директория
        directory = filedialog.askdirectory(initialdir=initial_dir)
        if directory:
            self.pages_dir_entry.delete(0, tk.END)
            self.pages_dir_entry.insert(0, directory)


    def browse_output_spreads(self):
        initial_dir = self.spreads_dir_entry.get()
        if not os.path.isdir(initial_dir):
            initial_dir = os.path.expanduser("~")
        directory = filedialog.askdirectory(initialdir=initial_dir)
        if directory:
            self.spreads_dir_entry.delete(0, tk.END)
            self.spreads_dir_entry.insert(0, directory)


    def _update_status_safe(self, message):
        if self.root.winfo_exists():
            self.root.after(0, self.update_status, message)


    def update_status(self, message):
        if not self.root.winfo_exists(): return

        if isinstance(message, str) and not message.startswith("---"):
             logging.info(message)

        # Обновляем GUI
        self.status_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)


    def _update_progress_safe(self, current_value, max_value):
        if self.root.winfo_exists():
            self.root.after(0, self.update_progress, current_value, max_value)


    def update_progress(self, current_value, max_value):
        if not self.root.winfo_exists(): return
        if max_value > 0:
            self.progress_bar['maximum'] = max_value
            self.progress_bar['value'] = current_value
        else:
            self.progress_bar['value'] = 0


    def clear_status(self):
        if not self.root.winfo_exists(): return
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state=tk.DISABLED)
        logging.info("GUI log cleared by user.")


    def stop_action(self):
        msg = "--- Получен СТОП ---"
        self._update_status_safe(msg)
        self.stop_event.set()
        self.stop_button.config(state=tk.DISABLED)


    def _set_buttons_state(self, task_running):
        if not self.root.winfo_exists(): return
        state = tk.DISABLED if task_running else tk.NORMAL
        stop_state = tk.NORMAL if task_running else tk.DISABLED

        self.download_button.config(state=state)
        self.process_button.config(state=state)
        self.run_all_button.config(state=state)
        self.browse_pages_button.config(state=state)
        self.browse_spreads_button.config(state=state)

        if task_running and not self.stop_event.is_set():
             self.stop_button.config(state=tk.NORMAL)
        else:
             self.stop_button.config(state=tk.DISABLED)

        # Обновление заголовка окна
        try:
            if task_running:
                self.root.title(f"[*Выполняется...] {self.original_title}")
            else:
                self.update_progress(0, 1)
                self.root.title(self.original_title)
        except tk.TclError:
             pass


    def _validate_download_inputs(self):
        base_url = self.url_base_entry.get().strip()
        url_ids = self.url_ids_entry.get().strip()
        pdf_filename = self.pdf_filename_entry.get().strip()
        pages_dir = self.pages_dir_entry.get().strip()
        total_pages_str = self.total_pages_entry.get().strip()

        errors = []
        if not base_url: errors.append("Базовый URL")
        if not url_ids: errors.append("ID файла")
        if not pdf_filename: errors.append("Имя файла на сайте")
        if not pages_dir: errors.append("Папка для страниц")
        if not total_pages_str: errors.append("Кол-во страниц")

        if errors:
            messagebox.showerror("Ошибка ввода", "Пожалуйста, заполните поля:\n- " + "\n- ".join(errors))
            return False

        try:
            pages = int(total_pages_str)
            if pages <= 0:
                 messagebox.showerror("Ошибка ввода", "Количество страниц должно быть положительным числом.")
                 return False
        except ValueError:
            messagebox.showerror("Ошибка ввода", "Количество страниц должно быть целым числом.")
            return False

        if not base_url.startswith(("http://", "https://")):
             if not messagebox.askyesno("Предупреждение", f"Базовый URL '{base_url}' не похож на веб-адрес (не начинается с http:// или https://).\nПродолжить?"):
                 return False
        return True


    def _validate_processing_inputs(self, check_dir_exists=True):
        pages_dir = self.pages_dir_entry.get().strip()
        spreads_dir = self.spreads_dir_entry.get().strip()

        errors = []
        if not pages_dir: errors.append("Папка для страниц")
        if not spreads_dir: errors.append("Папка для разворотов")

        if errors:
             messagebox.showerror("Ошибка ввода", "Пожалуйста, укажите:\n- " + "\n- ".join(errors))
             return False

        if check_dir_exists:
            if not os.path.isdir(pages_dir):
                 messagebox.showerror("Ошибка папки", f"Папка со страницами '{pages_dir}' не найдена.")
                 return False
            try:
                if not os.listdir(pages_dir):
                     messagebox.showwarning("Предупреждение", f"Папка '{pages_dir}' пуста. Обработка невозможна.")
                     return False
            except Exception as e:
                 messagebox.showerror("Ошибка папки", f"Не удалось прочитать содержимое папки '{pages_dir}': {e}")
                 logging.error(f"Error reading directory '{pages_dir}': {e}", exc_info=True)
                 return False
        return True


    def open_folder(self, folder_path):
        msg = f"Попытка открыть папку: {folder_path}"
        self._update_status_safe(msg)
        try:
            norm_path = os.path.normpath(folder_path)
            if os.path.isdir(norm_path):
                os.startfile(norm_path)
                logging.info(f"Opened folder: {norm_path}")
            else:
                msg = f"Ошибка: Папка не найдена: {norm_path}"
                self._update_status_safe(msg)
                logging.error(msg)
        except Exception as e:
            msg = f"Ошибка при открытии папки '{norm_path}': {e}"
            self._update_status_safe(msg)
            logging.error(msg, exc_info=True)


    def save_settings(self):
        settings = {
            'url_base': self.url_base_entry.get(),
            'url_ids': self.url_ids_entry.get(),
            'pdf_filename': self.pdf_filename_entry.get(),
            'total_pages': self.total_pages_entry.get(),
            'pages_dir': self.pages_dir_entry.get(),
            'spreads_dir': self.spreads_dir_entry.get(),
        }
        try:
            with open(config.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            logging.info(f"Settings saved to {config.SETTINGS_FILE}")
        except IOError as e:
            logging.warning(f"Could not save settings to {config.SETTINGS_FILE}: {e}")

    def load_settings(self):
        loaded_settings = {}
        try:
            if os.path.exists(config.SETTINGS_FILE):
                with open(config.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                logging.info(f"Settings loaded from {config.SETTINGS_FILE}")
            else:
                logging.info(f"Settings file {config.SETTINGS_FILE} not found, using defaults.")

        except (IOError, json.JSONDecodeError) as e:
            logging.warning(f"Could not load or parse settings from {config.SETTINGS_FILE}: {e}")

        self.url_base_entry.insert(0, loaded_settings.get('url_base', config.DEFAULT_URL_BASE))
        self.url_ids_entry.insert(0, loaded_settings.get('url_ids', config.DEFAULT_URL_IDS))
        self.pdf_filename_entry.insert(0, loaded_settings.get('pdf_filename', config.DEFAULT_PDF_FILENAME))
        self.total_pages_entry.insert(0, loaded_settings.get('total_pages', config.DEFAULT_TOTAL_PAGES))
        self.pages_dir_entry.insert(0, loaded_settings.get('pages_dir', config.DEFAULT_PAGES_DIR))
        self.spreads_dir_entry.insert(0, loaded_settings.get('spreads_dir', config.DEFAULT_SPREADS_DIR))

        # Чтобы не спамить лишний раз
        self.initial_settings = {
        'url_base': self.url_base_entry.get(),
        'url_ids': self.url_ids_entry.get(),
        'pdf_filename': self.pdf_filename_entry.get(),
        'total_pages': self.total_pages_entry.get(),
        'pages_dir': self.pages_dir_entry.get(),
        'spreads_dir': self.spreads_dir_entry.get(),
        }
        logging.info(f"Initial settings captured for comparison: {self.initial_settings}")

    def on_closing(self):
        if self.current_thread and self.current_thread.is_alive():
            if messagebox.askyesno("Выход", "Процесс еще выполняется. Прервать и выйти?"):
                logging.info("User chose to interrupt running process and exit.")
                self.stop_event.set()
                self.root.after(500, self._check_thread_before_destroy)
            else:
                logging.info("User chose not to exit while process is running.")
                return
        else:
             logging.info("Application closing normally.")

             current_settings = {
                 'url_base': self.url_base_entry.get(),
                 'url_ids': self.url_ids_entry.get(),
                 'pdf_filename': self.pdf_filename_entry.get(),
                 'total_pages': self.total_pages_entry.get(),
                 'pages_dir': self.pages_dir_entry.get(),
                 'spreads_dir': self.spreads_dir_entry.get(),
             }

             if current_settings != self.initial_settings:
                 logging.info("Settings have changed from initial values. Saving...")
                 self.save_settings()
             else:
                 logging.info("Settings are unchanged from initial values. Skipping save.")
             self._destroy_root()


    def _check_thread_before_destroy(self):
        """Ждет завершения потока перед закрытием окна."""
        if self.current_thread and self.current_thread.is_alive():
            self.root.after(100, self._check_thread_before_destroy)
        else:
            self._destroy_root()


    def _destroy_root(self):
        if self.root:
            self.root.destroy()
            self.root = None


    # --- Методы запуска задач ---
    def _prepare_task_run(self):
        self.save_settings()
        self.clear_status()
        self.stop_event.clear()
        self._set_buttons_state(task_running=True)


    def _create_output_dir(self, dir_path, dir_purpose):
        try:
            os.makedirs(dir_path, exist_ok=True)
            msg = f"Папка для {dir_purpose}: '{dir_path}'"
            self._update_status_safe(msg)
            return True
        except Exception as e:
            msg = f"Ошибка создания папки для {dir_purpose} '{dir_path}': {e}"
            self._update_status_safe(msg)
            logging.error(msg, exc_info=True)
            messagebox.showerror("Ошибка папки", f"Не удалось создать папку:\n{dir_path}\n{e}")
            self._set_buttons_state(task_running=False)
            return False


    def run_download(self):
        if not self._validate_download_inputs(): return
        self._prepare_task_run()

        base_url = self.url_base_entry.get().strip().rstrip('/') + '/'
        url_ids = self.url_ids_entry.get().strip().rstrip('/') + '/'
        filename_pdf = self.pdf_filename_entry.get().strip()
        total_pages = int(self.total_pages_entry.get())
        output_dir = self.pages_dir_entry.get().strip()

        if not self._create_output_dir(output_dir, "страниц"): return

        self.current_thread = threading.Thread(
            target=self._thread_wrapper,
            args=(self.handler.download_pages, base_url, url_ids, filename_pdf, total_pages, output_dir),
            daemon=True
        )
        self.current_thread.start()


    def run_processing(self):
        if not self._validate_processing_inputs(check_dir_exists=True): return
        self._prepare_task_run()

        input_folder = self.pages_dir_entry.get().strip()
        output_folder = self.spreads_dir_entry.get().strip()

        if not self._create_output_dir(output_folder, "разворотов"): return

        self.current_thread = threading.Thread(
            target=self._thread_wrapper,
            args=(self.handler.process_images, input_folder, output_folder),
            daemon=True
        )
        self.current_thread.start()


    def run_all(self):
        if not self._validate_download_inputs() or not self._validate_processing_inputs(check_dir_exists=False):
             return
        self._prepare_task_run()

        base_url = self.url_base_entry.get().strip().rstrip('/') + '/'
        url_ids = self.url_ids_entry.get().strip().rstrip('/') + '/'
        filename_pdf = self.pdf_filename_entry.get().strip()
        total_pages = int(self.total_pages_entry.get())
        pages_dir = self.pages_dir_entry.get().strip()
        spreads_dir = self.spreads_dir_entry.get().strip()

        if not self._create_output_dir(pages_dir, "страниц"): return
        if not self._create_output_dir(spreads_dir, "разворотов"): return

        self.current_thread = threading.Thread(
            target=self._run_all_sequence,
            args=(base_url, url_ids, filename_pdf, total_pages, pages_dir, spreads_dir),
            daemon=True
        )
        self.current_thread.start()


    def _thread_wrapper(self, target_func, *args):
        result = None
        final_message = "Задача завершена."
        error_occurred = False
        folder_to_open = None
        try:
            result = target_func(*args)

            if target_func == self.handler.download_pages:
                success_count, total_pages = result
                final_message = f"Скачивание завершено. Успешно скачано {success_count} из {total_pages} страниц."
                if not self.stop_event.is_set():
                    if success_count == total_pages:
                         self.root.after(0, lambda: messagebox.showinfo("Успех", "Все страницы успешно скачаны!"))
                    elif success_count > 0:
                         self.root.after(0, lambda: messagebox.showwarning("Завершено с ошибками", f"Скачано {success_count} из {total_pages}. Проверьте лог."))
                    else:
                         self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось скачать ни одной страницы. Проверьте параметры и лог ({config.LOG_FILE})."))
                    if success_count > 0:
                         folder_to_open = args[-1]

            elif target_func == self.handler.process_images:
                processed_count, created_spread_count = result
                final_message = f"Обработка завершена. Обработано/скопировано {processed_count} файлов."
                if created_spread_count > 0:
                    final_message += f" Создано {created_spread_count} разворотов."
                if not self.stop_event.is_set():
                    self.root.after(0, lambda: messagebox.showinfo("Успех", "Создание разворотов завершено!"))
                    if processed_count > 0:
                        folder_to_open = args[-1]

        except Exception as e:
            error_occurred = True
            final_message = f"Критическая ошибка при выполнении задачи: {e}"
            logging.error(f"Критическая ошибка в потоке: {e}", exc_info=True)
            self.root.after(0, lambda msg=final_message: messagebox.showerror("Критическая ошибка", f"{msg}\n\n(Подробности в лог-файле {config.LOG_FILE})"))
        finally:
            if not self.stop_event.is_set():
                 self._update_status_safe(final_message)
                 if folder_to_open:
                     self.root.after(500, lambda p=folder_to_open: self.open_folder(p))

            self.root.after(0, lambda: self._set_buttons_state(task_running=False))
            self.current_thread = None


    def _run_all_sequence(self, base_url, url_ids, filename_pdf, total_pages, pages_dir, spreads_dir):
        download_success = False
        final_folder_to_open = None
        try:
            # --- Этап 1: Скачивание ---
            self._update_status_safe("--- НАЧАЛО: Скачивание страниц ---")
            success_count, total_dl_pages = self.handler.download_pages(
                base_url, url_ids, filename_pdf, total_pages, pages_dir
            )

            if self.stop_event.is_set():
                self._update_status_safe("--- Скачивание прервано, обработка отменена ---")
                return

            if success_count == 0:
                self._update_status_safe("--- Скачивание не удалось, обработка пропущена ---")
                self.root.after(0, lambda: messagebox.showerror("Ошибка скачивания", f"Не удалось скачать ни одной страницы. Обработка не будет запущена.\nПроверьте лог ({config.LOG_FILE})."))
                return

            if success_count < total_dl_pages:
                 msg = f"--- Скачивание завершено с ошибками ({success_count}/{total_dl_pages}). Продолжаем обработку... ---"
                 self._update_status_safe(msg)
                 self.root.after(0, lambda c=success_count, t=total_dl_pages: messagebox.showwarning("Скачивание с ошибками", f"Скачано {c} из {t} страниц. Обработка будет запущена для скачанных файлов."))
            else:
                 self._update_status_safe("--- Скачивание успешно завершено ---")

            download_success = True

            time.sleep(0.5)

            # --- Этап 2: Обработка ---
            self._update_status_safe("--- НАЧАЛО: Создание разворотов ---")
            processed_count, created_spread_count = self.handler.process_images(
                pages_dir, spreads_dir
            )

            if self.stop_event.is_set():
                self._update_status_safe("--- Обработка прервана ---")
                return

            final_message = f"Обработка завершена. Обработано/скопировано {processed_count} файлов."
            if created_spread_count > 0:
                final_message += f" Создано {created_spread_count} разворотов."
            self._update_status_safe(f"--- {final_message} ---")
            self.root.after(0, lambda msg=final_message: messagebox.showinfo("Завершено", f"Скачивание и обработка завершены.\n{msg}"))

            if processed_count > 0:
                 final_folder_to_open = spreads_dir

        except Exception as e:
            final_message = f"Критическая ошибка при выполнении 'Скачать и создать': {e}"
            logging.error(f"Критическая ошибка в _run_all_sequence: {e}", exc_info=True)
            self.root.after(0, lambda msg=final_message: messagebox.showerror("Критическая ошибка", f"{msg}\n\n(Подробности в лог-файле {config.LOG_FILE})"))
        finally:
            if final_folder_to_open and not self.stop_event.is_set():
                 self.root.after(500, lambda p=final_folder_to_open: self.open_folder(p))
            self.root.after(0, lambda: self._set_buttons_state(task_running=False))
            self.current_thread = None


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = JournalDownloaderApp(root)
        root.mainloop()
    except Exception as main_e:
        try:
            logging.critical(f"Unhandled exception in main GUI loop: {main_e}", exc_info=True)
        except:
            pass
        try:
            messagebox.showerror("Фатальная ошибка", f"Произошла непредвиденная ошибка:\n{main_e}\n\nПриложение будет закрыто.\nПодробности в лог-файле: {config.LOG_FILE}")
        except:
            print(f"FATAL UNHANDLED ERROR: {main_e}")
    finally:
        logging.info("="*20 + " Приложение завершено " + "="*20)
