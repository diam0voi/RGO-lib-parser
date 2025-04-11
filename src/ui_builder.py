# src/ui_builder.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
from pathlib import Path
from PIL import Image, ImageTk
# Добавляем импорт Optional и других нужных типов
from typing import Dict, Callable, Any, Optional

# Импортируем зависимости
from .app_state import AppState
from . import config, utils # Для resource_path и констант

logger = logging.getLogger(__name__)

# Словарь для хранения ссылок на созданные виджеты
WidgetsDict = Dict[str, tk.Widget]

# Теперь Optional будет найден
def setup_main_window(root: tk.Tk) -> Optional[ImageTk.PhotoImage]:
    """Настраивает основные параметры главного окна (заголовок, размер, иконка, стили)."""
    logger.debug("Setting up main window...")
    root.title(config.WINDOW_TITLE)
    root.minsize(600, 650)

    # --- Иконка окна ---
    window_icon_image = None
    try:
        window_icon_path = utils.resource_path(config.WINDOW_ICON_PATH)
        if Path(window_icon_path).is_file():
            pil_icon = Image.open(window_icon_path)
            # Важно сохранить ссылку на PhotoImage, иначе он будет собран GC
            window_icon_image = ImageTk.PhotoImage(pil_icon)
            root.iconphoto(True, window_icon_image)
            logger.debug(f"Window icon set from: {window_icon_path}")
        else:
            logger.warning(f"Window icon file not found: {window_icon_path}")
    except Exception as e:
        logger.warning(f"Could not set window icon: {e}", exc_info=True)

    # --- Стили ---
    style = ttk.Style()
    style.configure("TLabel", padding=5)
    style.configure("TButton", padding=5)
    style.configure("TEntry", padding=5)
    style.configure("Stop.TButton", foreground="red", font=('Helvetica', 9, 'bold'))
    logger.debug("Widget styles configured.")

    return window_icon_image # Возвращаем, чтобы сохранить ссылку

def create_input_frame(parent: tk.Widget, app_state: AppState, browse_pages_cmd: Callable, browse_spreads_cmd: Callable) -> WidgetsDict:
    """Создает фрейм с полями ввода параметров и кнопками обзора."""
    logger.debug("Creating input frame...")
    widgets: WidgetsDict = {}
    input_frame = ttk.LabelFrame(parent, text="Параметры", padding=10)
    input_frame.pack(padx=10, pady=(10,5), fill=tk.X)

    # --- Поля ввода URL и имени файла ---
    ttk.Label(input_frame, text="Базовый URL (до ID):").grid(row=0, column=0, sticky=tk.W)
    widgets['url_base_entry'] = ttk.Entry(input_frame, width=60, textvariable=app_state.url_base)
    widgets['url_base_entry'].grid(row=0, column=1, columnspan=2, sticky=tk.EW)

    ttk.Label(input_frame, text="ID файла (часть URL):").grid(row=1, column=0, sticky=tk.W)
    widgets['url_ids_entry'] = ttk.Entry(input_frame, width=60, textvariable=app_state.url_ids)
    widgets['url_ids_entry'].grid(row=1, column=1, columnspan=2, sticky=tk.EW)

    ttk.Label(input_frame, text="Имя файла на сайте:").grid(row=2, column=0, sticky=tk.W)
    widgets['pdf_filename_entry'] = ttk.Entry(input_frame, width=60, textvariable=app_state.pdf_filename)
    widgets['pdf_filename_entry'].grid(row=2, column=1, columnspan=2, sticky=tk.EW)

    ttk.Label(input_frame, text="Кол-во страниц:").grid(row=3, column=0, sticky=tk.W)
    widgets['total_pages_entry'] = ttk.Entry(input_frame, width=10, textvariable=app_state.total_pages)
    widgets['total_pages_entry'].grid(row=3, column=1, sticky=tk.W)

    # --- Выбор папок ---
    path_frame = ttk.Frame(input_frame)
    path_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=(10, 0))

    ttk.Label(path_frame, text="Папка для страниц:").grid(row=0, column=0, sticky=tk.W)
    widgets['pages_dir_entry'] = ttk.Entry(path_frame, width=45, textvariable=app_state.pages_dir)
    widgets['pages_dir_entry'].grid(row=0, column=1, sticky=tk.EW, padx=(0, 5))
    widgets['browse_pages_button'] = ttk.Button(path_frame, text="Обзор...", command=browse_pages_cmd)
    widgets['browse_pages_button'].grid(row=0, column=2)

    ttk.Label(path_frame, text="Папка для разворотов:").grid(row=1, column=0, sticky=tk.W)
    widgets['spreads_dir_entry'] = ttk.Entry(path_frame, width=45, textvariable=app_state.spreads_dir)
    widgets['spreads_dir_entry'].grid(row=1, column=1, sticky=tk.EW, padx=(0, 5))
    widgets['browse_spreads_button'] = ttk.Button(path_frame, text="Обзор...", command=browse_spreads_cmd)
    widgets['browse_spreads_button'].grid(row=1, column=2)

    # Настройка растягивания колонок
    path_frame.columnconfigure(1, weight=1)
    input_frame.columnconfigure(1, weight=1)
    logger.debug("Input frame created.")
    return widgets

def create_control_frame(parent: tk.Widget, run_all_cmd: Callable, download_cmd: Callable, process_cmd: Callable, stop_cmd: Callable) -> WidgetsDict:
    """Создает фрейм с кнопками управления."""
    logger.debug("Creating control frame...")
    widgets: WidgetsDict = {}
    control_frame = ttk.Frame(parent, padding=(10, 5, 10, 5))
    control_frame.pack(fill=tk.X)

    widgets['run_all_button'] = ttk.Button(control_frame, text="Скачать и создать развороты", command=run_all_cmd)
    widgets['run_all_button'].pack(side=tk.LEFT, padx=5)
    widgets['download_button'] = ttk.Button(control_frame, text="Только скачать страницы", command=download_cmd)
    widgets['download_button'].pack(side=tk.LEFT, padx=5)
    widgets['process_button'] = ttk.Button(control_frame, text="Только создать развороты", command=process_cmd)
    widgets['process_button'].pack(side=tk.LEFT, padx=5)
    widgets['stop_button'] = ttk.Button(control_frame, text="СТОП", command=stop_cmd, state=tk.DISABLED, style="Stop.TButton")
    widgets['stop_button'].pack(side=tk.RIGHT, padx=15)
    logger.debug("Control frame created.")
    return widgets

def create_progress_frame(parent: tk.Widget) -> WidgetsDict:
    """Создает фрейм с прогресс-баром."""
    logger.debug("Creating progress frame...")
    widgets: WidgetsDict = {}
    progress_frame = ttk.Frame(parent, padding=(10, 0, 10, 5))
    progress_frame.pack(fill=tk.X)
    widgets['progress_bar'] = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
    widgets['progress_bar'].pack(fill=tk.X, expand=True)
    logger.debug("Progress frame created.")
    return widgets

def create_status_frame(parent: tk.Widget) -> WidgetsDict:
    """Создает фрейм с текстовым полем для вывода статуса."""
    logger.debug("Creating status frame...")
    widgets: WidgetsDict = {}
    status_frame = ttk.LabelFrame(parent, text="Статус", padding=10)
    status_frame.pack(padx=10, pady=(0,10), fill=tk.BOTH, expand=True)
    widgets['status_text'] = scrolledtext.ScrolledText(status_frame, height=10, wrap=tk.WORD, state=tk.DISABLED, bd=0, relief=tk.FLAT)
    widgets['status_text'].pack(fill=tk.BOTH, expand=True)
    logger.debug("Status frame created.")
    return widgets