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

import config

# --- Helpers  ---
def get_page_number(filename):  # Из имени на сайте
    match = re.search(r'\d+', filename)
    return int(match.group()) if match else -1

def is_likely_spread(image_path, threshold):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if height == 0: return False
            aspect_ratio = width / height
            return aspect_ratio > threshold
    except Exception:
        return False

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Логика скачивания и обработки ---
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
            backoff_factor=1  # 1*2, 2*2, 4*2...
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

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
                return True
            else:
                self.status_callback("Предупреждение: Не удалось автоматически получить куки (сервер не установил?).")
                return False
        except requests.exceptions.Timeout:
             self.status_callback(f"Ошибка: Превышено время ожидания при получении куки с {config.INITIAL_COOKIE_URL}.")
             return False
        except requests.exceptions.RequestException as e:
             self.status_callback(f"Ошибка при получении куки: {e}.")
             return False

    def download_pages(self, base_url, url_ids, filename_pdf, total_pages, output_dir):
        self.stop_event.clear()
        self._setup_session_with_retry()
        got_cookies = self._get_initial_cookies()

        self.status_callback(f"Начинаем скачивание {total_pages} страниц в '{output_dir}'...")
        self.progress_callback(0, total_pages)

        success_count = 0
        for i in range(total_pages):
            if self.stop_event.is_set():
                self.status_callback("--- Скачивание прервано пользователем ---")
                break

            page_string = f"{filename_pdf}/{i}"
            page_b64_bytes = base64.b64encode(page_string.encode('utf-8'))
            page_b64_string = page_b64_bytes.decode('utf-8')
            final_url = f"{base_url}{url_ids}{page_b64_string}"
            base_output_filename = os.path.join(output_dir, f"page_{i:03d}")

            status_msg = f"Скачиваю страницу {i+1}/{total_pages}..."
            self.status_callback(status_msg)

            try:
                response = self.session.get(final_url, timeout=(10, 30))
                response.raise_for_status() # Вызовет исключение для 4xx/5xx после ретраев

                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type:
                     self.status_callback(f"Ошибка на стр. {i+1}: Получен HTML вместо изображения. Проблема с сессией?")
                     continue

                extension = ".jpg"
                if 'png' in content_type: extension = ".png"
                elif 'gif' in content_type: extension = ".gif"
                elif 'bmp' in content_type: extension = ".bmp"
                elif 'tiff' in content_type: extension = ".tiff"
                elif 'jpeg' in content_type: extension = ".jpeg"

                final_output_filename = base_output_filename + extension

                with open(final_output_filename, 'wb') as f:
                    f.write(response.content)

                if os.path.getsize(final_output_filename) == 0:
                    self.status_callback(f"Предупреждение: Файл {os.path.basename(final_output_filename)} пустой.")
                else:
                     success_count += 1
                     # self.status_callback(f" -> Сохранено как {os.path.basename(final_output_filename)}") # Для подробного лога

            except requests.exceptions.HTTPError as e:
                 self.status_callback(f"Ошибка HTTP {e.response.status_code} на стр. {i+1} (после {config.MAX_RETRIES} попыток): {e}")
                 if e.response.status_code in [401, 403]:
                     self.status_callback("   (Возможно, сессия истекла или куки неверны)")
            except requests.exceptions.Timeout:
                 self.status_callback(f"Ошибка: Таймаут при скачивании стр. {i+1} (после {config.MAX_RETRIES} попыток).")
            except requests.exceptions.RequestException as e:
                self.status_callback(f"Ошибка сети/сервера на стр. {i+1} (после {config.MAX_RETRIES} попыток): {e}")
            except IOError as e:
                self.status_callback(f"Ошибка записи файла для стр. {i+1}: {e}")
            except Exception as e:
                self.status_callback(f"Неожиданная ошибка на стр. {i+1}: {e}")
                import traceback
                print(f"UNEXPECTED ERROR on page {i+1}:\n{traceback.format_exc()}")

            finally:
                self.progress_callback(i + 1, total_pages)
                if not self.stop_event.is_set():
                    time.sleep(config.DEFAULT_DELAY_SECONDS)

        return success_count, total_pages


    def process_images(self, input_folder, output_folder):
        """Создает развороты из скачанных страниц."""
        self.stop_event.clear()
        self.status_callback(f"Начинаем обработку изображений из '{input_folder}' в '{output_folder}'...")

        try:
            all_files = [f for f in os.listdir(input_folder) if f.lower().endswith(config.IMAGE_EXTENSIONS)]
        except FileNotFoundError:
            self.status_callback(f"Ошибка: Папка '{input_folder}' не найдена.")
            return 0, 0 # Обработано 0 файлов

        sorted_files = sorted([f for f in all_files if get_page_number(f) != -1], key=get_page_number)

        if not sorted_files:
            self.status_callback("В папке не найдено подходящих файлов изображений с номерами.")
            return 0, 0

        total_files_to_process = len(sorted_files)
        self.status_callback(f"Найдено {total_files_to_process} файлов. Создание разворотов...")
        self.progress_callback(0, total_files_to_process) # Сброс прогресс-бара для обработки

        page_index = 0
        processed_count = 0
        created_spread_count = 0

        while page_index < len(sorted_files):
            if self.stop_event.is_set():
                self.status_callback("--- Обработка прервана пользователем ---")
                break

            current_file = sorted_files[page_index]
            current_path = os.path.join(input_folder, current_file)
            current_page_num = get_page_number(current_file)
            current_is_spread = page_index > 0 and is_likely_spread(current_path, config.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD)

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
                except Exception as e:
                    self.status_callback(f"Ошибка при копировании {current_file}: {e}")
                page_index += 1

            # Вариант 2: Текущий файл - одиночная страница
            else:
                # Проверяем, есть ли следующий и является ли он тоже одиночным
                if page_index + 1 < len(sorted_files):
                    next_file = sorted_files[page_index + 1]
                    next_path = os.path.join(input_folder, next_file)
                    next_page_num = get_page_number(next_file)
                    next_is_single = not is_likely_spread(next_path, config.DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD)

                    # Вариант 2.1: Следующий тоже одиночный - СКЛЕИВАЕМ
                    if next_is_single:
                        output_filename = f"spread_{current_page_num:03d}-{next_page_num:03d}.jpg"
                        output_path = os.path.join(output_folder, output_filename)
                        status_msg = f"Создаю разворот: {current_file} + {next_file} -> {output_filename}"
                        self.status_callback(status_msg)
                        try:
                            with Image.open(current_path) as img_left, Image.open(next_path) as img_right:
                                w_left, h_left = img_left.size
                                w_right, h_right = img_right.size

                                if h_left != h_right:
                                    target_height = (h_left + h_right) // 2
                                    # self.status_callback(f"   (Выравниваю высоту до {target_height}px)") # Для подробного лога
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
                        except Exception as e:
                            self.status_callback(f"Ошибка при создании разворота для {current_file} и {next_file}: {e}")
                            processed_increment = 2 # Считаем, что попытались обработать оба
                        page_index += 2

                    # Вариант 2.2: Текущий одиночный, следующий - разворот (или конец) -> Копируем текущий
                    else:
                        _, ext = os.path.splitext(current_file)
                        output_filename = f"spread_{current_page_num:03d}{ext}"
                        output_path = os.path.join(output_folder, output_filename)
                        status_msg = f"Копирую одиночную страницу: {current_file} -> {output_filename}"
                        self.status_callback(status_msg)
                        try:
                            shutil.copy2(current_path, output_path)
                            processed_increment = 1
                        except Exception as e:
                            self.status_callback(f"Ошибка при копировании одиночной {current_file}: {e}")
                        page_index += 1
                # Вариант 2.3: Текущий одиночный - последний файл -> Копируем его
                else:
                    _, ext = os.path.splitext(current_file)
                    output_filename = f"spread_{current_page_num:03d}{ext}"
                    output_path = os.path.join(output_folder, output_filename)
                    status_msg = f"Копирую последнюю одиночную страницу: {current_file} -> {output_filename}"
                    self.status_callback(status_msg)
                    try:
                        shutil.copy2(current_path, output_path)
                        processed_increment = 1
                    except Exception as e:
                        self.status_callback(f"Ошибка при копировании последней одиночной {current_file}: {e}")
                    page_index += 1

            processed_count += processed_increment  # Обновляем прогресс бар по количеству обработанных *исходных* файлов
            self.progress_callback(page_index, total_files_to_process)

        return processed_count, created_spread_count


# --- Класс GUI ---
class JournalDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Загрузчик + склейщик файлов библиотеки РГО. v1.3 by b0s")
        self.root.minsize(600, 650)

        # Иконка
        try:
            window_icon_path = resource_path("window_bnwbook.png")
            pil_icon = Image.open(window_icon_path)
            self.window_icon_image = ImageTk.PhotoImage(pil_icon)
            self.root.iconphoto(True, self.window_icon_image)
        except Exception as e:
            print(f"Warning: Could not set window icon: {e}")

        self.stop_event = threading.Event()
        self.current_thread = None

        self.handler = LibraryHandler(
            status_callback=self._update_status_safe,
            progress_callback=self._update_progress_safe,
            stop_event=self.stop_event
        )

        # Стили
        style = ttk.Style()
        style.configure("TLabel", padding=5)
        style.configure("TButton", padding=5)
        style.configure("TEntry", padding=5)
        style.configure("Stop.TButton", foreground="red", font=('Helvetica', 9, 'bold'))

        # Фрейм ввода
        input_frame = ttk.LabelFrame(root, text="Параметры", padding=10)
        input_frame.pack(padx=10, pady=(10,5), fill=tk.X)

        # Поля ввода
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

        # Пути
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

        # Фрейм управления
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

        # Прогресс-бар
        progress_frame = ttk.Frame(root, padding=(10, 0, 10, 5))
        progress_frame.pack(fill=tk.X)
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True)

        # Лог
        status_frame = ttk.LabelFrame(root, text="Статус", padding=10)
        status_frame.pack(padx=10, pady=(0,10), fill=tk.BOTH, expand=True)
        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.status_text.pack(fill=tk.BOTH, expand=True)

        self.load_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)


    # --- Методы для GUI ---
    def browse_output_pages(self):
        directory = filedialog.askdirectory(initialdir=self.pages_dir_entry.get())
        if directory:
            self.pages_dir_entry.delete(0, tk.END)
            self.pages_dir_entry.insert(0, directory)

    def browse_output_spreads(self):
        directory = filedialog.askdirectory(initialdir=self.spreads_dir_entry.get())
        if directory:
            self.spreads_dir_entry.delete(0, tk.END)
            self.spreads_dir_entry.insert(0, directory)

    def _update_status_safe(self, message):
        if self.root.winfo_exists():
            self.root.after(0, self.update_status, message)

    def update_status(self, message):
        if not self.root.winfo_exists(): return
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

    def stop_action(self):
        self._update_status_safe("Остановка...")
        self.stop_event.set()
        self.stop_button.config(state=tk.DISABLED) # Блокируем кнопку сразу

    def _set_buttons_state(self, task_running):
        if not self.root.winfo_exists(): return
        state = tk.DISABLED if task_running else tk.NORMAL
        stop_state = tk.NORMAL if task_running else tk.DISABLED

        self.download_button.config(state=state)
        self.process_button.config(state=state)
        self.run_all_button.config(state=state)
        self.browse_pages_button.config(state=state)
        self.browse_spreads_button.config(state=state)
        # Кнопка активна только когда задача запущена и еще не остановлена
        if task_running and not self.stop_event.is_set():
             self.stop_button.config(state=tk.NORMAL)
        else:
             self.stop_button.config(state=tk.DISABLED)

    def _validate_download_inputs(self):
        base_url = self.url_base_entry.get().strip()
        url_ids = self.url_ids_entry.get().strip()
        pdf_filename = self.pdf_filename_entry.get().strip()
        pages_dir = self.pages_dir_entry.get().strip()
        total_pages_str = self.total_pages_entry.get().strip()

        if not all([base_url, url_ids, pdf_filename, pages_dir, total_pages_str]):
            messagebox.showerror("Ошибка ввода", "Пожалуйста, заполните все поля URL, ID, имени файла, кол-ва страниц и папки для страниц.")
            return False
        try:
            pages = int(total_pages_str)
            if pages <= 0:
                 messagebox.showerror("Ошибка ввода", "Количество страниц должно быть положительным числом.")
                 return False
        except ValueError:
            messagebox.showerror("Ошибка ввода", "Количество страниц должно быть целым числом.")
            return False
        if not base_url.startswith("http"):
             messagebox.showwarning("Предупреждение", "Базовый URL не похож на веб-адрес.")
        return True

    def _validate_processing_inputs(self, check_dir_exists=True):
        pages_dir = self.pages_dir_entry.get().strip()
        spreads_dir = self.spreads_dir_entry.get().strip()
        if not pages_dir or not spreads_dir:
             messagebox.showerror("Ошибка ввода", "Пожалуйста, укажите папки для страниц и разворотов.")
             return False
        if check_dir_exists:
            if not os.path.isdir(pages_dir):
                 messagebox.showerror("Ошибка папки", f"Папка со страницами '{pages_dir}' не найдена.")
                 return False
            try:
                if not any(f.lower().endswith(config.IMAGE_EXTENSIONS) for f in os.listdir(pages_dir)):
                     messagebox.showwarning("Предупреждение", f"В папке '{pages_dir}' не найдено файлов изображений для обработки.")
                     # Может пользователь знает, что делает
            except Exception as e:
                 messagebox.showerror("Ошибка папки", f"Не удалось прочитать содержимое папки '{pages_dir}': {e}")
                 return False
        return True

    def open_folder(self, folder_path):
        self._update_status_safe(f"Попытка открыть папку: {folder_path}")
        try:
            norm_path = os.path.normpath(folder_path)
            if os.path.isdir(norm_path):
                os.startfile(norm_path)
            else:
                self._update_status_safe(f"Ошибка: Папка не найдена: {norm_path}")
        except Exception as e:
            self._update_status_safe(f"Ошибка при открытии папки '{norm_path}': {e}")

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
        except IOError as e:
            print(f"Warning: Could not save settings to {config.SETTINGS_FILE}: {e}")

    def load_settings(self):
        try:
            if os.path.exists(config.SETTINGS_FILE):
                with open(config.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                # Заполняем поля, если они есть в файле
                self.url_base_entry.insert(0, settings.get('url_base', config.DEFAULT_URL_BASE))
                self.url_ids_entry.insert(0, settings.get('url_ids', config.DEFAULT_URL_IDS))
                self.pdf_filename_entry.insert(0, settings.get('pdf_filename', config.DEFAULT_PDF_FILENAME))
                self.total_pages_entry.insert(0, settings.get('total_pages', config.DEFAULT_TOTAL_PAGES))
                self.pages_dir_entry.insert(0, settings.get('pages_dir', config.DEFAULT_PAGES_DIR))
                self.spreads_dir_entry.insert(0, settings.get('spreads_dir', config.DEFAULT_SPREADS_DIR))
            else:
                self.url_base_entry.insert(0, config.DEFAULT_URL_BASE)
                self.pages_dir_entry.insert(0, config.DEFAULT_PAGES_DIR)
                self.spreads_dir_entry.insert(0, config.DEFAULT_SPREADS_DIR)

        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load settings from {config.SETTINGS_FILE}: {e}")
            self.url_base_entry.insert(0, config.DEFAULT_URL_BASE)
            self.pages_dir_entry.insert(0, config.DEFAULT_PAGES_DIR)
            self.spreads_dir_entry.insert(0, config.DEFAULT_SPREADS_DIR)


    def on_closing(self):
        if self.current_thread and self.current_thread.is_alive():
            if messagebox.askyesno("Выход", "Процесс еще выполняется. Прервать и выйти?"):
                self.stop_event.set()
                self.root.after(500, self.root.destroy)
            else:
                return
        else:
             self.save_settings()
             self.root.destroy()

    # --- Методы запуска задач ---
    def run_download(self):
        if not self._validate_download_inputs(): return
        self.save_settings()
        self.clear_status()
        self._set_buttons_state(task_running=True)
        self.stop_event.clear() # Сброс флага перед запуском

        # Передадим в обработчик
        base_url = self.url_base_entry.get().strip().rstrip('/') + '/'
        url_ids = self.url_ids_entry.get().strip().rstrip('/') + '/'
        filename_pdf = self.pdf_filename_entry.get().strip()
        total_pages = int(self.total_pages_entry.get())
        output_dir = self.pages_dir_entry.get().strip()

        try:
            os.makedirs(output_dir, exist_ok=True)
            self._update_status_safe(f"Папка для страниц: '{output_dir}'")
        except Exception as e:
            self._update_status_safe(f"Ошибка создания папки '{output_dir}': {e}")
            messagebox.showerror("Ошибка папки", f"Не удалось создать папку:\n{output_dir}\n{e}")
            self._set_buttons_state(task_running=False)
            return

        self.current_thread = threading.Thread(
            target=self._thread_wrapper,
            args=(self.handler.download_pages, base_url, url_ids, filename_pdf, total_pages, output_dir),
            daemon=True
        )
        self.current_thread.start()


    def run_processing(self):
        if not self._validate_processing_inputs(): return
        self.save_settings()
        self.clear_status()
        self._set_buttons_state(task_running=True)
        self.stop_event.clear()

        input_folder = self.pages_dir_entry.get().strip()
        output_folder = self.spreads_dir_entry.get().strip()

        try:
            os.makedirs(output_folder, exist_ok=True)
            self._update_status_safe(f"Папка для разворотов: '{output_folder}'")
        except Exception as e:
            self._update_status_safe(f"Ошибка создания папки '{output_folder}': {e}")
            messagebox.showerror("Ошибка папки", f"Не удалось создать папку:\n{output_folder}\n{e}")
            self._set_buttons_state(task_running=False)
            return

        self.current_thread = threading.Thread(
            target=self._thread_wrapper,
            args=(self.handler.process_images, input_folder, output_folder),
            daemon=True
        )
        self.current_thread.start()


    def run_all(self):
        if not self._validate_download_inputs() or not self._validate_processing_inputs(check_dir_exists=False):
             return
        self.save_settings()
        self.clear_status()
        self._set_buttons_state(task_running=True)
        self.stop_event.clear()

        # Получаем параметры
        base_url = self.url_base_entry.get().strip().rstrip('/') + '/'
        url_ids = self.url_ids_entry.get().strip().rstrip('/') + '/'
        filename_pdf = self.pdf_filename_entry.get().strip()
        total_pages = int(self.total_pages_entry.get())
        pages_dir = self.pages_dir_entry.get().strip()
        spreads_dir = self.spreads_dir_entry.get().strip()

        try:
            os.makedirs(pages_dir, exist_ok=True)
            self._update_status_safe(f"Папка для страниц: '{pages_dir}'")
            os.makedirs(spreads_dir, exist_ok=True)
            self._update_status_safe(f"Папка для разворотов: '{spreads_dir}'")
        except Exception as e:
            self._update_status_safe(f"Ошибка создания папки: {e}")
            messagebox.showerror("Ошибка папки", f"Не удалось создать папки:\n{pages_dir}\n{spreads_dir}\n{e}")
            self._set_buttons_state(task_running=False)
            return

        # Обе задачи последовательно в одном потоке
        self.current_thread = threading.Thread(
            target=self._run_all_sequence,
            args=(base_url, url_ids, filename_pdf, total_pages, pages_dir, spreads_dir),
            daemon=True
        )
        self.current_thread.start()

    # --- Обертки для выполнения в потоках ---
    def _thread_wrapper(self, target_func, *args):
        """Обертка для запуска методов handler'а и обработки результатов."""
        result = None
        final_message = "Задача завершена."
        error_occurred = False
        try:
            result = target_func(*args)

            # Сообщение по результату
            if target_func == self.handler.download_pages:
                success_count, total_pages = result
                final_message = f"Скачивание завершено. Успешно скачано {success_count} из {total_pages} страниц."
                if success_count == total_pages:
                     self.root.after(0, lambda: messagebox.showinfo("Успех", "Все страницы успешно скачаны!"))
                elif success_count > 0:
                     self.root.after(0, lambda: messagebox.showwarning("Завершено с ошибками", f"Скачано {success_count} из {total_pages}. Проверьте лог."))
                else:
                     self.root.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось скачать ни одной страницы. Проверьте параметры и лог."))
                if success_count > 0 and not self.stop_event.is_set():
                     output_dir = args[-1]
                     self.root.after(500, lambda p=output_dir: self.open_folder(p))

            elif target_func == self.handler.process_images:
                processed_count, created_spread_count = result
                final_message = f"Обработка завершена. Обработано/скопировано {processed_count} файлов."
                if created_spread_count > 0:
                    final_message += f" Создано {created_spread_count} разворотов."
                self.root.after(0, lambda: messagebox.showinfo("Успех", "Создание разворотов завершено!"))
                if processed_count > 0 and not self.stop_event.is_set():
                     output_folder = args[-1]
                     self.root.after(500, lambda p=output_folder: self.open_folder(p))

        except Exception as e:
            error_occurred = True
            final_message = f"Критическая ошибка при выполнении задачи: {e}"
            import traceback
            traceback_str = traceback.format_exc()
            print(f"CRITICAL TASK ERROR:\n{traceback_str}")
            self.root.after(0, lambda msg=final_message: messagebox.showerror("Критическая ошибка", f"{msg}\n\n(Подробности в консоли)"))
        finally:
            if not self.stop_event.is_set():
                 self._update_status_safe(final_message)
            self.root.after(0, self.update_progress, 0, 1)
            self.root.after(0, lambda: self._set_buttons_state(task_running=False))
            self.current_thread = None


    def _run_all_sequence(self, base_url, url_ids, filename_pdf, total_pages, pages_dir, spreads_dir):
        download_success = False
        try:
            # Скачивание
            self._update_status_safe("--- НАЧАЛО: Скачивание страниц ---")
            success_count, total_dl_pages = self.handler.download_pages(
                base_url, url_ids, filename_pdf, total_pages, pages_dir
            )

            if self.stop_event.is_set():
                self._update_status_safe("--- Скачивание прервано, обработка отменена ---")
                return

            if success_count == 0:
                self._update_status_safe("--- Скачивание не удалось, обработка пропущена ---")
                self.root.after(0, lambda: messagebox.showerror("Ошибка скачивания", "Не удалось скачать ни одной страницы. Обработка не будет запущена."))
                return

            if success_count < total_dl_pages:
                 self._update_status_safe(f"--- Скачивание завершено с ошибками ({success_count}/{total_dl_pages}). Продолжаем обработку... ---")
                 self.root.after(0, lambda: messagebox.showwarning("Скачивание с ошибками", f"Скачано {success_count} из {total_dl_pages} страниц. Обработка будет запущена для скачанных файлов."))
            else:
                 self._update_status_safe("--- Скачивание успешно завершено ---")
                 self.root.after(0, lambda: messagebox.showinfo("Скачивание завершено", "Все страницы успешно скачаны."))

            download_success = True

            if download_success:
                 self.root.after(500, lambda p=pages_dir: self.open_folder(p))

            time.sleep(1)

            # Обработка 
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
            self.root.after(0, lambda: messagebox.showinfo("Обработка завершена", final_message))

            if processed_count > 0:
                 self.root.after(500, lambda p=spreads_dir: self.open_folder(p))

        except Exception as e:
            final_message = f"Критическая ошибка при выполнении 'Скачать и создать': {e}"
            import traceback
            traceback_str = traceback.format_exc()
            print(f"CRITICAL RUN ALL ERROR:\n{traceback_str}")
            self.root.after(0, lambda msg=final_message: messagebox.showerror("Критическая ошибка", f"{msg}\n\n(Подробности в консоли)"))
        finally:
            # Сброс прогресс бара и кнопок в _thread_wrapper
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = JournalDownloaderApp(root)
    root.mainloop()
