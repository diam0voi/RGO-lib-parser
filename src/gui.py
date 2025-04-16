# src/gui.py
import logging
import os
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable, Dict

# Импортируем новые модули и старые зависимости
from . import (
    config,
    logic,
    ui_builder,  # Импортируем модуль целиком
    )
from .app_state import AppState
from .settings_manager import SettingsManager
from .task_manager import TaskManager

logger = logging.getLogger(__name__)


class JournalDownloaderApp:
    """Класс графического интерфейса приложения.
    Оркестрирует взаимодействие между состоянием (AppState),
    построителем UI (ui_builder), менеджером задач (TaskManager)
    и менеджером настроек (SettingsManager).
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.original_title: str = config.WINDOW_TITLE
        logger.info("Initializing JournalDownloaderApp...")

        # 1. Состояние приложения
        self.state = AppState()

        # 2. Менеджер настроек (работает с AppState)
        self.settings_manager = SettingsManager(self.state)

        # 3. Логика и событие остановки
        self.stop_event = threading.Event()
        # Создаем экземпляр обработчика логики
        self.handler = logic.LibraryHandler(
            status_callback=self._update_status_safe,  # Передаем методы GUI как колбэки
            progress_callback=self._update_progress_safe,
            stop_event=self.stop_event,
        )

        # 4. Менеджер задач (получает зависимости и колбэки)
        self.task_manager = TaskManager(
            app_state=self.state,
            handler=self.handler,
            stop_event=self.stop_event,
            status_callback=self._update_status_safe,
            progress_callback=self._update_progress_safe,
            set_buttons_state_callback=self._set_buttons_state,
            show_message_callback=self._show_message_safe,
            open_folder_callback=self._open_folder_safe,
            root=self.root,  # Передаем root для root.after
        )

        # 5. Построение UI
        # Настройка окна (иконка, стили)
        # Сохраняем ссылку на иконку, чтобы ее не удалил сборщик мусора
        self.window_icon_image = ui_builder.setup_main_window(self.root)

        # Создание виджетов с помощью ui_builder
        self.widgets: Dict[str, tk.Widget] = {}  # Словарь для доступа к виджетам
        self.widgets.update(
            ui_builder.create_input_frame(
                self.root,
                self.state,
                self.browse_output_pages,
                self.browse_output_spreads,
            )
        )
        self.widgets.update(
            ui_builder.create_control_frame(
                self.root,
                self.run_all,
                self.run_download,
                self.run_processing,
                self.stop_action,
            )
        )
        self.widgets.update(ui_builder.create_progress_frame(self.root))
        self.widgets.update(ui_builder.create_status_frame(self.root))

        # 6. Загрузка настроек и установка обработчика закрытия
        self.settings_manager.load_settings()  # Загрузит в self.state, виджеты обновятся
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        logger.info("GUI initialized successfully.")

    # --- Методы обратного вызова для GUI ---

    def browse_output_pages(self) -> None:
        """Открывает диалог выбора папки для скачанных страниц."""
        initial_dir = self.state.pages_dir.get()  # Берем из состояния
        if not os.path.isdir(initial_dir):
            initial_dir = str(Path.home())
        directory = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Выберите папку для скачивания страниц",
            parent=self.root,
        )
        if directory:
            self.state.pages_dir.set(directory)  # Обновляем состояние
            logger.info(f"Pages directory selected: {directory}")

    def browse_output_spreads(self) -> None:
        """Открывает диалог выбора папки для готовых разворотов."""
        initial_dir = self.state.spreads_dir.get()  # Берем из состояния
        if not os.path.isdir(initial_dir):
            initial_dir = str(Path.home())
        directory = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Выберите папку для сохранения разворотов",
            parent=self.root,
        )
        if directory:
            self.state.spreads_dir.set(directory)  # Обновляем состояние
            logger.info(f"Spreads directory selected: {directory}")

    # --- Обновление GUI (вызываются из TaskManager через root.after) ---

    def _update_status_safe(self, message: str) -> None:
        """Безопасно планирует обновление статуса в основном потоке."""
        if self.root and self.root.winfo_exists():
            self.root.after(0, self._update_status, message)
        else:
            logger.warning(f"GUI root doesn't exist, status update ignored: {message}")

    def _update_status(self, message: str) -> None:
        """Обновляет текстовое поле статуса (выполняется в основном потоке)."""
        if not self.root or not self.root.winfo_exists():
            return
        status_text_widget = self.widgets.get("status_text")
        if not isinstance(status_text_widget, scrolledtext.ScrolledText):
            return

        if isinstance(message, str) and not message.startswith("---"):
            logger.info(f"GUI Status Update: {message}")

        try:
            status_text_widget.config(state=tk.NORMAL)
            timestamp = time.strftime("%H:%M:%S")
            status_text_widget.insert(tk.END, f"[{timestamp}] {message}\n")
            status_text_widget.see(tk.END)
            status_text_widget.config(state=tk.DISABLED)
        except tk.TclError as e:
            logger.warning(f"TclError updating status text (window closing?): {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating status text: {e}", exc_info=True)

    def _update_progress_safe(self, current_value: int, max_value: int) -> None:
        """Безопасно планирует обновление прогресс-бара."""
        if self.root and self.root.winfo_exists():
            self.root.after(0, self._update_progress, current_value, max_value)
        else:
            logger.warning(
                f"GUI root doesn't exist, progress update ignored: {current_value}/{max_value}"
            )

    def _update_progress(self, current_value: int, max_value: int) -> None:
        """Обновляет прогресс-бар (выполняется в основном потоке)."""
        if not self.root or not self.root.winfo_exists():
            return
        progress_bar_widget = self.widgets.get("progress_bar")
        if not isinstance(progress_bar_widget, ttk.Progressbar):
            return

        try:
            if max_value > 0:
                progress_bar_widget["maximum"] = max_value
                progress_bar_widget["value"] = current_value
            else:
                progress_bar_widget["maximum"] = 1
                progress_bar_widget["value"] = 0
        except tk.TclError as e:
            logger.warning(f"TclError updating progress bar (window closing?): {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating progress bar: {e}", exc_info=True)

    def _set_buttons_state(self, task_running: bool) -> None:
        """Включает/выключает кнопки управления."""
        if not self.root or not self.root.winfo_exists():
            return

        action_buttons_state = tk.DISABLED if task_running else tk.NORMAL
        # Кнопка Стоп активна только если задача запущена И событие stop_event еще не установлено
        stop_button_state = (
            tk.NORMAL if task_running and not self.stop_event.is_set() else tk.DISABLED
        )

        try:
            # Получаем кнопки из словаря виджетов
            for key in [
                "download_button",
                "process_button",
                "run_all_button",
                "browse_pages_button",
                "browse_spreads_button",
            ]:
                button = self.widgets.get(key)
                if button:
                    button.config(state=action_buttons_state)

            stop_button = self.widgets.get("stop_button")
            if stop_button:
                stop_button.config(state=stop_button_state)

            # Обновляем заголовок окна и сбрасываем прогресс при завершении
            if task_running:
                self.root.title(f"[*Выполняется...] {self.original_title}")
            else:
                self._update_progress(0, 1)  # Сброс прогресс-бара
                self.root.title(self.original_title)
            logger.debug(f"Buttons state updated. Task running: {task_running}")
        except tk.TclError as e:
            logger.warning(f"TclError setting button states (window closing?): {e}")
        except Exception as e:
            logger.error(f"Unexpected error setting button states: {e}", exc_info=True)

    def _show_message_safe(self, msg_type: str, title: str, message: str) -> None:
        """Безопасно планирует показ messagebox."""
        if self.root and self.root.winfo_exists():
            self.root.after(0, self._show_message, msg_type, title, message)
        else:
            logger.warning(
                f"GUI root doesn't exist, message ignored: [{msg_type}] {title} - {message}"
            )

    def _show_message(self, msg_type: str, title: str, message: str) -> None:
        """Показывает messagebox (выполняется в основном потоке)."""
        if not self.root or not self.root.winfo_exists():
            return
        logger.debug(f"Showing message: Type={msg_type}, Title='{title}'")
        try:
            if msg_type == "info":
                messagebox.showinfo(title, message, parent=self.root)
            elif msg_type == "warning":
                messagebox.showwarning(title, message, parent=self.root)
            elif msg_type == "error":
                messagebox.showerror(title, message, parent=self.root)
            else:  # По умолчанию - info
                messagebox.showinfo(title, message, parent=self.root)
        except Exception as e:
            logger.error(f"Failed to show message box: {e}", exc_info=True)

    def _open_folder_safe(self, folder_path: str) -> None:
        """Безопасно планирует открытие папки."""
        if self.root and self.root.winfo_exists():
            self.root.after(100, self._open_folder, folder_path)  # Небольшая задержка
        else:
            logger.warning(
                f"GUI root doesn't exist, open folder ignored: {folder_path}"
            )

    def _open_folder(self, folder_path: str) -> None:
        """Открывает указанную папку в системном файловом менеджере."""
        if not self.root or not self.root.winfo_exists():
            return
        msg = f"Попытка открыть папку: {folder_path}"
        self._update_status(msg)  # Обновляем статус напрямую, т.к. уже в главном потоке
        logger.info(f"Attempting to open folder: {folder_path}")
        try:
            norm_path = os.path.normpath(folder_path)
            if os.path.isdir(norm_path):
                os.startfile(
                    norm_path
                )  # Должно работать на Windows, MacOS, Linux (с xdg-open)
                logger.info(f"Opened folder successfully: {norm_path}")
            else:
                err_msg = f"Ошибка: Папка не найдена: {norm_path}"
                self._update_status(err_msg)
                logger.error(err_msg)
                self._show_message(
                    "error",
                    "Ошибка",
                    f"Не удалось открыть папку, так как она не найдена:\n{norm_path}",
                )
        except Exception as e:
            err_msg = f"Ошибка при открытии папки '{folder_path}': {e}"
            self._update_status(err_msg)
            logger.error(err_msg, exc_info=True)
            self._show_message(
                "error", "Ошибка", f"Произошла ошибка при попытке открыть папку:\n{e}"
            )

    def clear_status(self) -> None:
        """Очищает текстовое поле статуса."""
        if not self.root or not self.root.winfo_exists():
            return
        status_text_widget = self.widgets.get("status_text")
        if not isinstance(status_text_widget, scrolledtext.ScrolledText):
            return
        try:
            status_text_widget.config(state=tk.NORMAL)
            status_text_widget.delete(1.0, tk.END)
            status_text_widget.config(state=tk.DISABLED)
            logger.info("GUI status log cleared by user.")
        except tk.TclError as e:
            logger.warning(f"TclError clearing status text (window closing?): {e}")

    # --- Обработчики действий пользователя ---

    def _validate_and_show_errors(
        self, validation_func: Callable[..., list[str]], *args, **kwargs
    ) -> bool:
        """Общая функция для валидации и показа ошибок."""
        errors = validation_func(*args, **kwargs)
        if errors:
            error_message = "Пожалуйста, исправьте поля:\n- " + "\n- ".join(errors)
            self._show_message("error", "Ошибка ввода", error_message)
            logger.warning(f"Input validation failed: Issues - {', '.join(errors)}")
            return False
        # Мягкая проверка URL (специфична для скачивания)
        if validation_func == self.state.validate_for_download:
            base_url = self.state.url_base.get()
            if not base_url.startswith(("http://", "https://")):
                logger.warning(
                    f"Base URL '{base_url}' does not start with http:// or https://"
                )
                if not messagebox.askyesno(  # Используем messagebox напрямую для синхронного ответа
                    "Предупреждение",
                    f"Базовый URL '{base_url}' не похож на веб-адрес.\nПродолжить?",
                    parent=self.root,
                ):
                    logger.info("User cancelled due to URL warning.")
                    return False
        logger.debug("Input validation successful.")
        return True

    def run_download(self) -> None:
        """Запускает скачивание страниц."""
        if not self._validate_and_show_errors(self.state.validate_for_download):
            return
        # Сохраняем настройки перед запуском задачи
        if not self.settings_manager.save_settings():
            self._show_message(
                "warning",
                "Ошибка сохранения",
                "Не удалось сохранить настройки перед запуском.",
            )
            # Решаем, продолжать ли без сохранения или нет (пока продолжаем)
        self.clear_status()
        self.task_manager.start_download()

    def run_processing(self) -> None:
        """Запускает обработку изображений."""
        # check_dir_exists=True по умолчанию в AppState
        if not self._validate_and_show_errors(self.state.validate_for_processing):
            return
        if not self.settings_manager.save_settings():
            self._show_message(
                "warning",
                "Ошибка сохранения",
                "Не удалось сохранить настройки перед запуском.",
            )
        self.clear_status()
        self.task_manager.start_processing()

    def run_all(self) -> None:
        """Запускает последовательно скачивание и обработку."""
        # Сначала валидация скачивания, потом обработки (без проверки существования папки)
        if not self._validate_and_show_errors(self.state.validate_for_download):
            return
        if not self._validate_and_show_errors(
            self.state.validate_for_processing, check_dir_exists=False
        ):
            return
        if not self.settings_manager.save_settings():
            self._show_message(
                "warning",
                "Ошибка сохранения",
                "Не удалось сохранить настройки перед запуском.",
            )
        self.clear_status()
        self.task_manager.start_all()

    def stop_action(self) -> None:
        """Обрабатывает нажатие кнопки СТОП."""
        self.task_manager.stop_task()

    # --- Управление жизненным циклом окна ---

    def on_closing(self) -> None:
        """Обработчик события закрытия окна."""
        logger.debug("WM_DELETE_WINDOW event triggered.")
        if self.task_manager.is_running():
            if messagebox.askyesno(
                "Выход", "Процесс еще выполняется. Прервать и выйти?", parent=self.root
            ):
                logger.info("User chose to interrupt running process and exit.")
                self.task_manager.stop_task()
                # Ждем завершения потока перед закрытием
                self.root.after(100, self._check_thread_before_destroy)
            else:
                logger.info("User chose not to exit while process is running.")
                return  # Не закрываем окно
        else:
            # Если поток не запущен, просто сохраняем настройки и закрываем
            self.settings_manager.save_settings_if_changed()
            self._destroy_root()

    def _check_thread_before_destroy(self) -> None:
        """Периодически проверяет, завершился ли поток перед закрытием."""
        if self.task_manager.is_running():
            logger.debug(
                "Waiting for background thread to finish before destroying root..."
            )
            self.root.after(100, self._check_thread_before_destroy)  # Проверяем снова
        else:
            logger.info(
                "Background thread finished or not found. Proceeding to destroy root."
            )
            self.settings_manager.save_settings_if_changed()  # Сохраняем на всякий случай
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
                self.root = None  # Явно обнуляем ссылку
