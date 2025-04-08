import json
import logging
import os
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, scrolledtext
from typing import Optional
from PIL import Image, ImageTk

from . import config, logic, utils

logger = logging.getLogger(__name__)

class JournalDownloaderApp:
    """
    Класс графического интерфейса приложения для скачивания и обработки
    файлов библиотеки РГО.
    """
    def __init__(self, root: tk.Tk):
        self.root = root
        self.original_title: str = config.WINDOW_TITLE
        self.root.title(self.original_title)
        self.root.minsize(600, 650)

        # --- Иконка окна ---
        self._set_window_icon()

        # --- Состояния ---
        self.stop_event = threading.Event()
        self.current_thread: Optional[threading.Thread] = None
        # Создаем экземпляр обработчика логики, передавая колбэки и событие
        self.handler = logic.LibraryHandler(
            status_callback=self._update_status_safe,
            progress_callback=self._update_progress_safe,
            stop_event=self.stop_event
        )

        # --- Стили ---
        self._configure_styles()

        # --- Создание виджетов ---
        self._create_input_frame()
        self._create_control_frame()
        self._create_progress_frame()
        self._create_status_frame()

        # --- Загрузка и сохранение настроек ---
        self.initial_settings: dict = {}
        self.load_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        logger.info("GUI initialized successfully.")

    def _set_window_icon(self) -> None:
        """Устанавливает иконку окна."""
        try:
            window_icon_path = utils.resource_path(config.WINDOW_ICON_PATH)
            if Path(window_icon_path).is_file():
                pil_icon = Image.open(window_icon_path)
                self.window_icon_image = ImageTk.PhotoImage(pil_icon)
                self.root.iconphoto(True, self.window_icon_image)
                logger.debug(f"Window icon set from: {window_icon_path}")
            else:
                logger.warning(f"Window icon file not found: {window_icon_path}")
        except Exception as e:
            logger.warning(f"Could not set window icon: {e}", exc_info=True)

    def _configure_styles(self) -> None:
        """Настраивает стили ttk виджетов."""
        style = ttk.Style()
        style.configure("TLabel", padding=5)
        style.configure("TButton", padding=5)
        style.configure("TEntry", padding=5)
        style.configure("Stop.TButton", foreground="red", font=('Helvetica', 9, 'bold'))
        logger.debug("Widget styles configured.")

    def _create_input_frame(self) -> None:
        """Создает фрейм с полями ввода параметров."""
        input_frame = ttk.LabelFrame(self.root, text="Параметры", padding=10)
        input_frame.pack(padx=10, pady=(10,5), fill=tk.X)

        # --- Поля ввода URL и имени файла ---
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

        # --- Выбор папок ---
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

        # Настройка растягивания колонок
        path_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(1, weight=1)
        logger.debug("Input frame created.")

    def _create_control_frame(self) -> None:
        """Создает фрейм с кнопками управления."""
        control_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        control_frame.pack(fill=tk.X)

        self.run_all_button = ttk.Button(control_frame, text="Скачать и создать развороты", command=self.run_all)
        self.run_all_button.pack(side=tk.LEFT, padx=5)
        self.download_button = ttk.Button(control_frame, text="Только скачать страницы", command=self.run_download)
        self.download_button.pack(side=tk.LEFT, padx=5)
        self.process_button = ttk.Button(control_frame, text="Только создать развороты", command=self.run_processing)
        self.process_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(control_frame, text="СТОП", command=self.stop_action, state=tk.DISABLED, style="Stop.TButton")
        self.stop_button.pack(side=tk.RIGHT, padx=15)
        logger.debug("Control frame created.")

    def _create_progress_frame(self) -> None:
        """Создает фрейм с прогресс-баром."""
        progress_frame = ttk.Frame(self.root, padding=(10, 0, 10, 5))
        progress_frame.pack(fill=tk.X)
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True)
        logger.debug("Progress frame created.")

    def _create_status_frame(self) -> None:
        """Создает фрейм с текстовым полем для вывода статуса."""
        status_frame = ttk.LabelFrame(self.root, text="Статус", padding=10)
        status_frame.pack(padx=10, pady=(0,10), fill=tk.BOTH, expand=True)
        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, wrap=tk.WORD, state=tk.DISABLED, bd=0, relief=tk.FLAT)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        logger.debug("Status frame created.")

    # --- Методы для GUI ---
    def browse_output_pages(self) -> None:
        """Открывает диалог выбора папки для скачанных страниц."""
        initial_dir = self.pages_dir_entry.get()
        if not os.path.isdir(initial_dir):
            initial_dir = str(Path.home())
            logger.debug(f"Initial pages dir '{self.pages_dir_entry.get()}' not found, using home: {initial_dir}")
        directory = filedialog.askdirectory(initialdir=initial_dir, title="Выберите папку для скачивания страниц")
        if directory:
            self.pages_dir_entry.delete(0, tk.END)
            self.pages_dir_entry.insert(0, directory)
            logger.info(f"Pages directory selected: {directory}")

    def browse_output_spreads(self) -> None:
        """Открывает диалог выбора папки для готовых разворотов."""
        initial_dir = self.spreads_dir_entry.get()
        if not os.path.isdir(initial_dir):
            initial_dir = str(Path.home())
            logger.debug(f"Initial spreads dir '{self.spreads_dir_entry.get()}' not found, using home: {initial_dir}")
        directory = filedialog.askdirectory(initialdir=initial_dir, title="Выберите папку для сохранения разворотов")
        if directory:
            self.spreads_dir_entry.delete(0, tk.END)
            self.spreads_dir_entry.insert(0, directory)
            logger.info(f"Spreads directory selected: {directory}")

    def _update_status_safe(self, message: str) -> None:
        """
        Безопасно обновляет текстовое поле статуса из другого потока.
        Использует `root.after` для вызова `update_status` в основном потоке GUI.
        """
        if self.root and self.root.winfo_exists():
            self.root.after(0, self.update_status, message)
        else:
            logger.warning(f"GUI root doesn't exist, status update ignored: {message}")

    def update_status(self, message: str) -> None:
        """Обновляет текстовое поле статуса (вызывается из основного потока)."""
        if not self.root or not self.root.winfo_exists(): return

        if isinstance(message, str) and not message.startswith("---"):
             logger.info(f"GUI Status: {message}")

        # Обновляем виджет ScrolledText
        try:
            self.status_text.config(state=tk.NORMAL)
            timestamp = time.strftime("%H:%M:%S")
            self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.status_text.see(tk.END)
            self.status_text.config(state=tk.DISABLED)
        except tk.TclError as e:
             logger.warning(f"TclError updating status text (window closing?): {e}")
        except Exception as e:
             logger.error(f"Unexpected error updating status text: {e}", exc_info=True)


    def _update_progress_safe(self, current_value: int, max_value: int) -> None:
        """Безопасно обновляет прогресс-бар из другого потока."""
        if self.root and self.root.winfo_exists():
            self.root.after(0, self.update_progress, current_value, max_value)
        else:
            logger.warning(f"GUI root doesn't exist, progress update ignored: {current_value}/{max_value}")

    def update_progress(self, current_value: int, max_value: int) -> None:
        """Обновляет прогресс-бар (вызывается из основного потока)."""
        if not self.root or not self.root.winfo_exists(): return
        try:
            if max_value > 0:
                self.progress_bar['maximum'] = max_value
                self.progress_bar['value'] = current_value
            else:
                self.progress_bar['maximum'] = 1
                self.progress_bar['value'] = 0
            # logger.debug(f"Progress bar updated: {current_value}/{max_value}")
        except tk.TclError as e:
             logger.warning(f"TclError updating progress bar (window closing?): {e}")
        except Exception as e:
             logger.error(f"Unexpected error updating progress bar: {e}", exc_info=True)


    def clear_status(self) -> None:
        """Очищает текстовое поле статуса."""
        if not self.root or not self.root.winfo_exists(): return
        try:
            self.status_text.config(state=tk.NORMAL)
            self.status_text.delete(1.0, tk.END)
            self.status_text.config(state=tk.DISABLED)
            logger.info("GUI status log cleared by user.")
        except tk.TclError as e:
             logger.warning(f"TclError clearing status text (window closing?): {e}")

    def stop_action(self) -> None:
        """Обрабатывает нажатие кнопки СТОП."""
        if self.current_thread and self.current_thread.is_alive():
            msg = "--- Получен сигнал СТОП от пользователя ---"
            logger.info(msg)
            self._update_status_safe(msg)
            self.stop_event.set()
            self.stop_button.config(state=tk.DISABLED)
        else:
             logger.warning("Stop button pressed but no active thread found.")


    def _set_buttons_state(self, task_running: bool) -> None:
        """Включает/выключает кнопки управления в зависимости от того, идет ли задача."""
        if not self.root or not self.root.winfo_exists(): return

        action_buttons_state = tk.DISABLED if task_running else tk.NORMAL
        stop_button_state = tk.NORMAL if task_running and not self.stop_event.is_set() else tk.DISABLED

        try:
            # Кнопки под действия
            self.download_button.config(state=action_buttons_state)
            self.process_button.config(state=action_buttons_state)
            self.run_all_button.config(state=action_buttons_state)
            self.browse_pages_button.config(state=action_buttons_state)
            self.browse_spreads_button.config(state=action_buttons_state)
            self.stop_button.config(state=stop_button_state)

            if task_running:
                self.root.title(f"[*Выполняется...] {self.original_title}")
            else:
                self.update_progress(0, 1)
                self.root.title(self.original_title)
            logger.debug(f"Buttons state updated. Task running: {task_running}")
        except tk.TclError as e:
             logger.warning(f"TclError setting button states (window closing?): {e}")
        except Exception as e:
             logger.error(f"Unexpected error setting button states: {e}", exc_info=True)


    def _validate_download_inputs(self) -> bool:
        """Проверяет заполнение полей, необходимых для скачивания."""
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
            messagebox.showerror("Ошибка ввода", "Пожалуйста, заполните поля:\n- " + "\n- ".join(errors), parent=self.root)
            logger.warning(f"Download input validation failed: Missing fields - {', '.join(errors)}")
            return False

        try:
            pages = int(total_pages_str)
            if pages <= 0:
                 messagebox.showerror("Ошибка ввода", "Количество страниц должно быть положительным числом.", parent=self.root)
                 logger.warning(f"Download input validation failed: Non-positive page count ({pages})")
                 return False
        except ValueError:
            messagebox.showerror("Ошибка ввода", "Количество страниц должно быть целым числом.", parent=self.root)
            logger.warning(f"Download input validation failed: Invalid page count ('{total_pages_str}')")
            return False

        # Мягкая проверка URL
        if not base_url.startswith(("http://", "https://")):
             logger.warning(f"Base URL '{base_url}' does not start with http:// or https://")
             if not messagebox.askyesno(
                 "Предупреждение",
                 f"Базовый URL '{base_url}' не похож на веб-адрес.\nПродолжить?",
                 parent=self.root):
                 logger.info("User cancelled due to URL warning.")
                 return False
        logger.debug("Download input validation successful.")
        return True


    def _validate_processing_inputs(self, check_dir_exists: bool = True) -> bool:
        """Проверяет заполнение полей, необходимых для обработки."""
        pages_dir = self.pages_dir_entry.get().strip()
        spreads_dir = self.spreads_dir_entry.get().strip()

        errors = []
        if not pages_dir: errors.append("Папка для страниц")
        if not spreads_dir: errors.append("Папка для разворотов")

        if errors:
             messagebox.showerror("Ошибка ввода", "Пожалуйста, укажите:\n- " + "\n- ".join(errors), parent=self.root)
             logger.warning(f"Processing input validation failed: Missing fields - {', '.join(errors)}")
             return False

        if check_dir_exists:
            pages_path = Path(pages_dir)
            if not pages_path.is_dir():
                 messagebox.showerror("Ошибка папки", f"Папка со страницами '{pages_dir}' не найдена.", parent=self.root)
                 logger.warning(f"Processing input validation failed: Input directory not found '{pages_dir}'")
                 return False
            try:
                if not any(pages_path.iterdir()):
                     messagebox.showwarning("Предупреждение", f"Папка '{pages_dir}' пуста. Обработка невозможна.", parent=self.root)
                     logger.warning(f"Processing input validation failed: Input directory '{pages_dir}' is empty.")
                     return False
            except Exception as e:
                 messagebox.showerror("Ошибка папки", f"Не удалось прочитать содержимое папки '{pages_dir}': {e}", parent=self.root)
                 logger.error(f"Error reading directory '{pages_dir}': {e}", exc_info=True)
                 return False
        logger.debug("Processing input validation successful.")
        return True


    def open_folder(self, folder_path: str) -> None:
        """Открывает указанную папку в системном файловом менеджере."""
        msg = f"Попытка открыть папку: {folder_path}"
        self._update_status_safe(msg)
        logger.info(f"Attempting to open folder: {folder_path}")
        try:
            norm_path = os.path.normpath(folder_path)
            if os.path.isdir(norm_path):
                # Для кроссплатформенности
                os.startfile(norm_path)
                logger.info(f"Opened folder successfully: {norm_path}")
            else:
                msg = f"Ошибка: Папка не найдена: {norm_path}"
                self._update_status_safe(msg)
                logger.error(msg)
                messagebox.showerror("Ошибка", f"Не удалось открыть папку, так как она не найдена:\n{norm_path}", parent=self.root)
        except Exception as e:
            msg = f"Ошибка при открытии папки '{norm_path}': {e}"
            self._update_status_safe(msg)
            logger.error(msg, exc_info=True)
            messagebox.showerror("Ошибка", f"Произошла ошибка при попытке открыть папку:\n{e}", parent=self.root)


    def save_settings(self) -> None:
        """Сохраняет текущие значения полей ввода в JSON-файл."""
        settings = {
            'url_base': self.url_base_entry.get(),
            'url_ids': self.url_ids_entry.get(),
            'pdf_filename': self.pdf_filename_entry.get(),
            'total_pages': self.total_pages_entry.get(),
            'pages_dir': self.pages_dir_entry.get(),
            'spreads_dir': self.spreads_dir_entry.get(),
        }
        try:
            settings_path = Path(config.SETTINGS_FILE)
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            logger.info(f"Settings saved to {settings_path}")
            self.initial_settings = settings.copy()
        except IOError as e:
            logger.warning(f"Could not save settings to {config.SETTINGS_FILE}: {e}")
            messagebox.showwarning("Ошибка сохранения", f"Не удалось сохранить настройки:\n{e}", parent=self.root)
        except Exception as e:
             logger.error(f"Unexpected error saving settings: {e}", exc_info=True)
             messagebox.showerror("Критическая ошибка", f"Не удалось сохранить настройки:\n{e}", parent=self.root)


    def load_settings(self) -> None:
        """Загружает настройки из JSON-файла и заполняет поля ввода."""
        loaded_settings = {}
        settings_path = Path(config.SETTINGS_FILE)
        try:
            if settings_path.is_file():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                logger.info(f"Settings loaded from {settings_path}")
            else:
                logger.info(f"Settings file {settings_path} not found, using defaults.")

        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load or parse settings from {settings_path}: {e}")
            # Не показываем ошибку пользователю при загрузке, просто используем дефолты

        self.url_base_entry.insert(0, loaded_settings.get('url_base', config.DEFAULT_URL_BASE))
        self.url_ids_entry.insert(0, loaded_settings.get('url_ids', config.DEFAULT_URL_IDS))
        self.pdf_filename_entry.insert(0, loaded_settings.get('pdf_filename', config.DEFAULT_PDF_FILENAME))
        self.total_pages_entry.insert(0, loaded_settings.get('total_pages', config.DEFAULT_TOTAL_PAGES))
        self.pages_dir_entry.insert(0, loaded_settings.get('pages_dir', config.DEFAULT_PAGES_DIR))
        self.spreads_dir_entry.insert(0, loaded_settings.get('spreads_dir', config.DEFAULT_SPREADS_DIR))

        # Для сравнения при выходе
        self.initial_settings = {
            'url_base': self.url_base_entry.get(),
            'url_ids': self.url_ids_entry.get(),
            'pdf_filename': self.pdf_filename_entry.get(),
            'total_pages': self.total_pages_entry.get(),
            'pages_dir': self.pages_dir_entry.get(),
            'spreads_dir': self.spreads_dir_entry.get(),
        }
        logger.debug(f"Initial settings captured for comparison: {self.initial_settings}")

    def on_closing(self) -> None:
        """Обработчик события закрытия окна."""
        logger.debug("WM_DELETE_WINDOW event triggered.")
        if self.current_thread and self.current_thread.is_alive():
            if messagebox.askyesno("Выход", "Процесс еще выполняется. Прервать и выйти?", parent=self.root):
                logger.info("User chose to interrupt running process and exit.")
                self.stop_event.set()
                self.root.after(500, self._check_thread_before_destroy)
            else:
                logger.info("User chose not to exit while process is running.")
                return
        else:
             self._save_settings_if_changed()
             self._destroy_root()


    def _save_settings_if_changed(self) -> None:
        """Сравнивает текущие настройки с начальными и сохраняет, если есть разница."""
        current_settings = {
             'url_base': self.url_base_entry.get(),
             'url_ids': self.url_ids_entry.get(),
             'pdf_filename': self.pdf_filename_entry.get(),
             'total_pages': self.total_pages_entry.get(),
             'pages_dir': self.pages_dir_entry.get(),
             'spreads_dir': self.spreads_dir_entry.get(),
        }

        if current_settings != self.initial_settings:
             logger.info("Settings have changed. Saving...")
             self.save_settings()
        else:
             logger.info("Settings are unchanged. Skipping save on exit.")


    def _check_thread_before_destroy(self) -> None:
        """
        Периодически проверяет, завершился ли поток, перед тем как
        уничтожить окно. Вызывается после `on_closing`, если пользователь
        решил прервать задачу.
        """
        if self.current_thread and self.current_thread.is_alive():
            logger.debug("Waiting for background thread to finish before destroying root...")
            self.root.after(100, self._check_thread_before_destroy)
        else:
            logger.info("Background thread finished or not found. Proceeding to destroy root.")
            self._save_settings_if_changed()
            self._destroy_root()


    def _destroy_root(self) -> None:
        """Уничтожает главное окно Tkinter."""
        if self.root:
            try:
                self.root.destroy()
                logger.info("Root window destroyed.")
            except tk.TclError as e:
                 logger.error(f"Error destroying root window: {e}")
            finally:
                 self.root = None


    # --- Методы запуска задач ---
    def _prepare_task_run(self) -> bool:
        """
        Общая подготовка перед запуском любой задачи в потоке.
        Возвращает True, если подготовка успешна, иначе False.
        """
        self.save_settings()
        self.clear_status()
        self.stop_event.clear()
        self._set_buttons_state(task_running=True)
        logger.info("Prepared for new task run.")
        return True


    def run_download(self) -> None:
        """Запускает скачивание страниц в отдельном потоке."""
        logger.info("'Download Only' button pressed.")
        if not self._validate_download_inputs(): return
        if not self._prepare_task_run(): return

        base_url = self.url_base_entry.get().strip()
        url_ids = self.url_ids_entry.get().strip()
        filename_pdf = self.pdf_filename_entry.get().strip()
        total_pages = int(self.total_pages_entry.get())
        output_dir = self.pages_dir_entry.get().strip()

        # Запускаем метод обработчика в потоке
        self.current_thread = threading.Thread(
            target=self._thread_wrapper,
            args=(self.handler.download_pages, base_url, url_ids, filename_pdf, total_pages, output_dir),
            kwargs={'task_name': 'Download'}, # Для логов
            daemon=True # Поток завершится, если завершится основной поток
        )
        logger.info(f"Starting download thread for {total_pages} pages to '{output_dir}'")
        self.current_thread.start()


    def run_processing(self) -> None:
        """Запускает обработку изображений в отдельном потоке."""
        logger.info("'Process Only' button pressed.")
        if not self._validate_processing_inputs(check_dir_exists=True): return
        if not self._prepare_task_run(): return

        input_folder = self.pages_dir_entry.get().strip()
        output_folder = self.spreads_dir_entry.get().strip()

        self.current_thread = threading.Thread(
            target=self._thread_wrapper,
            args=(self.handler.process_images, input_folder, output_folder),
            kwargs={'task_name': 'Processing'},
            daemon=True
        )
        logger.info(f"Starting processing thread from '{input_folder}' to '{output_folder}'")
        self.current_thread.start()


    def run_all(self) -> None:
        """Запускает последовательно скачивание и обработку в отдельном потоке."""
        logger.info("'Download and Process' button pressed.")
        if not self._validate_download_inputs() or not self._validate_processing_inputs(check_dir_exists=False):
             return
        if not self._prepare_task_run(): return

        base_url = self.url_base_entry.get().strip()
        url_ids = self.url_ids_entry.get().strip()
        filename_pdf = self.pdf_filename_entry.get().strip()
        total_pages = int(self.total_pages_entry.get())
        pages_dir = self.pages_dir_entry.get().strip()
        spreads_dir = self.spreads_dir_entry.get().strip()

        self.current_thread = threading.Thread(
            target=self._run_all_sequence,
            args=(base_url, url_ids, filename_pdf, total_pages, pages_dir, spreads_dir),
            daemon=True
        )
        logger.info("Starting combined download and process thread.")
        self.current_thread.start()


    def _thread_wrapper(self, target_func: callable, *args, task_name: str = "Task", **kwargs) -> None:
        """
        Обертка для выполнения целевой функции (download или process) в потоке.
        Обрабатывает результат, ошибки и обновляет GUI.
        """
        result = None
        final_message = f"{task_name}: Задача завершена."
        error_occurred = False
        folder_to_open: Optional[str] = None
        success = False

        logger.info(f"Thread started for: {task_name}")
        try:
            result = target_func(*args, **kwargs)  # download_pages или process_images

            # Обработка результата в зависимости от задачи
            if target_func == self.handler.download_pages:
                success_count, total_dl_pages = result
                final_message = f"Скачивание завершено. Успешно: {success_count} из {total_dl_pages}."
                if not self.stop_event.is_set():
                    if success_count == total_dl_pages and total_dl_pages > 0:
                         success = True
                         self.root.after(0, lambda: messagebox.showinfo("Успех", "Все страницы успешно скачаны!", parent=self.root))
                    elif success_count > 0:
                         success = True
                         self.root.after(0, lambda c=success_count, t=total_dl_pages: messagebox.showwarning("Завершено с ошибками", f"Скачано {c} из {t} страниц.\nПроверьте лог.", parent=self.root))
                    else: # success_count == 0
                         self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось скачать ни одной страницы.\nПроверьте параметры и лог ({config.LOG_FILE}).", parent=self.root))
                    if success_count > 0:
                         folder_to_open = args[-1]  # output_dir

            elif target_func == self.handler.process_images:
                processed_count, created_spread_count = result
                final_message = f"Обработка завершена. Обработано/скопировано: {processed_count}."
                if created_spread_count > 0:
                    final_message += f" Создано разворотов: {created_spread_count}."
                if not self.stop_event.is_set():
                    success = True
                    self.root.after(0, lambda msg=final_message: messagebox.showinfo("Успех", f"Создание разворотов завершено!\n{msg}", parent=self.root))
                    if processed_count > 0 or created_spread_count > 0:
                        folder_to_open = args[-1]  # output_folder

        except Exception as e:
            error_occurred = True
            final_message = f"{task_name}: Критическая ошибка при выполнении: {e}"
            logger.critical(f"Critical error in thread ({task_name}): {e}", exc_info=True)
            self.root.after(0, lambda msg=final_message: messagebox.showerror("Критическая ошибка", f"{msg}\n\nПодробности в лог-файле:\n{config.LOG_FILE}", parent=self.root))
        finally:
            if not self.stop_event.is_set():
                 self._update_status_safe(f"--- {final_message} ---")
                 if folder_to_open and success:
                     self.root.after(500, lambda p=folder_to_open: self.open_folder(p))

            self.root.after(0, lambda: self._set_buttons_state(task_running=False))
            self.current_thread = None
            logger.info(f"Thread finished for: {task_name}. Success: {success}, Interrupted: {self.stop_event.is_set()}, Error: {error_occurred}")


    def _run_all_sequence(
        self,
        base_url: str,
        url_ids: str,
        filename_pdf: str,
        total_pages: int,
        pages_dir: str,
        spreads_dir: str
    ) -> None:
        """
        Последовательно выполняет скачивание и обработку в одном потоке.
        """
        task_name = "Download & Process"
        logger.info(f"Thread started for combined task: {task_name}")
        download_success_count = 0
        processing_done = False
        final_folder_to_open: Optional[str] = None
        overall_success = False

        try:
            # --- Этап 1: Скачивание ---
            self._update_status_safe("--- НАЧАЛО: Скачивание страниц ---")
            success_count, total_dl_pages = self.handler.download_pages(
                base_url, url_ids, filename_pdf, total_pages, pages_dir
            )
            download_success_count = success_count

            if self.stop_event.is_set():
                self._update_status_safe("--- Скачивание прервано, обработка отменена ---")
                return

            # Проверяем результат скачивания
            if download_success_count == 0:
                self._update_status_safe("--- Скачивание не удалось (0 страниц), обработка пропущена ---")
                self.root.after(0, lambda: messagebox.showerror("Ошибка скачивания", f"Не удалось скачать ни одной страницы.\nОбработка не будет запущена.\nПроверьте лог ({config.LOG_FILE}).", parent=self.root))
                return

            # Если скачали не все, но хоть что-то
            elif download_success_count < total_dl_pages:
                 msg = f"--- Скачивание завершено с ошибками ({success_count}/{total_dl_pages}). Продолжаем обработку скачанных... ---"
                 self._update_status_safe(msg)
                 self.root.after(0, lambda c=success_count, t=total_dl_pages: messagebox.showwarning("Скачивание с ошибками", f"Скачано {c} из {t} страниц.\nОбработка будет запущена для скачанных файлов.", parent=self.root))
            else:
                 self._update_status_safe("--- Скачивание успешно завершено ({success_count}/{total_dl_pages}) ---")

            time.sleep(0.5)

            # --- Этап 2: Обработка ---
            self._update_status_safe("--- НАЧАЛО: Создание разворотов ---")
            processed_count, created_spread_count = self.handler.process_images(
                pages_dir, spreads_dir
            )
            processing_done = True

            if self.stop_event.is_set():
                self._update_status_safe("--- Обработка прервана ---")
                return

            final_message = f"Скачивание ({download_success_count}/{total_dl_pages}) и обработка ({processed_count} файлов, {created_spread_count} разворотов) завершены."
            self._update_status_safe(f"--- {final_message} ---")
            self.root.after(0, lambda msg=final_message: messagebox.showinfo("Завершено", msg, parent=self.root))
            overall_success = True

            if processed_count > 0 or created_spread_count > 0:
                 final_folder_to_open = spreads_dir

        except Exception as e:
            final_message = f"{task_name}: Критическая ошибка: {e}"
            logger.critical(f"Critical error in combined thread ({task_name}): {e}", exc_info=True)
            stage = "обработки" if download_success_count > 0 else "скачивания"
            self.root.after(0, lambda msg=final_message, s=stage: messagebox.showerror("Критическая ошибка", f"Ошибка на этапе {s}:\n{msg}\n\nПодробности в лог-файле:\n{config.LOG_FILE}", parent=self.root))
        finally:
            if final_folder_to_open and overall_success and not self.stop_event.is_set():
                 self.root.after(500, lambda p=final_folder_to_open: self.open_folder(p))

            # Возвращаем кнопки в нормальное состояние
            self.root.after(0, lambda: self._set_buttons_state(task_running=False))
            self.current_thread = None
            logger.info(f"Thread finished for: {task_name}. Success: {overall_success}, Interrupted: {self.stop_event.is_set()}")
