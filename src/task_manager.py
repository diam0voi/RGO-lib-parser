# src/task_manager.py
import threading
import time
import logging
from typing import Callable, Optional, Any

# Импортируем зависимости
from .app_state import AppState
from .logic import LibraryHandler # Или из . import logic
from . import config # Для доступа к LOG_FILE в сообщениях

logger = logging.getLogger(__name__)

# Определяем типы колбэков для удобства
StatusCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]
SetButtonsStateCallback = Callable[[bool], None]
ShowMessageCallback = Callable[[str, str, str], None] # type (info/warn/error), title, message
OpenFolderCallback = Callable[[str], None]

class TaskManager:
    """Управляет запуском, остановкой и мониторингом фоновых задач."""
    def __init__(
        self,
        app_state: AppState,
        handler: LibraryHandler,
        stop_event: threading.Event,
        status_callback: StatusCallback,
        progress_callback: ProgressCallback,
        set_buttons_state_callback: SetButtonsStateCallback,
        show_message_callback: ShowMessageCallback,
        open_folder_callback: OpenFolderCallback,
        root: Optional[Any] # tk.Tk, но избегаем прямого импорта tk для чистоты
    ):
        self.app_state = app_state
        self.handler = handler # Экземпляр LibraryHandler
        self.stop_event = stop_event
        self.current_thread: Optional[threading.Thread] = None
        # Сохраняем колбэки для взаимодействия с GUI
        self.status_cb = status_callback
        self.progress_cb = progress_callback
        self.set_buttons_state_cb = set_buttons_state_callback
        self.show_message_cb = show_message_callback
        self.open_folder_cb = open_folder_callback
        self.root = root # Нужен для root.after
        logger.debug("TaskManager initialized.")

    def is_running(self) -> bool:
        """Проверяет, выполняется ли сейчас какая-либо задача."""
        return self.current_thread is not None and self.current_thread.is_alive()

    def _start_thread(self, target_func: callable, args: tuple, task_name: str):
        """Внутренний метод для запуска потока."""
        if self.is_running():
            logger.warning(f"Task '{task_name}' requested, but another task is already running.")
            self.show_message_cb('warning', "Занято", "Другая операция уже выполняется.")
            return

        logger.info(f"Preparing to start task: {task_name}")
        self.stop_event.clear()
        self.set_buttons_state_cb(True) # Блокируем кнопки

        self.current_thread = threading.Thread(
            target=self._thread_wrapper,
            args=(target_func, *args), # Передаем целевую функцию и ее аргументы
            kwargs={'task_name': task_name},
            daemon=True
        )
        logger.info(f"Starting thread for task: {task_name}")
        self.current_thread.start()

    def start_download(self) -> None:
        """Запускает задачу скачивания."""
        task_name = "Download"
        logger.info(f"'{task_name}' task initiated.")
        # Получаем данные из AppState
        base_url = self.app_state.url_base.get().strip()
        url_ids = self.app_state.url_ids.get().strip()
        filename_pdf = self.app_state.pdf_filename.get().strip()
        total_pages = self.app_state.get_total_pages_int()
        output_dir = self.app_state.pages_dir.get().strip()

        if total_pages is None: # Должно быть отловлено валидацией GUI, но проверим
             logger.error("Invalid page count provided to start_download.")
             self.show_message_cb('error', "Ошибка", "Некорректное количество страниц.")
             return

        self._start_thread(
            target_func=self.handler.download_pages,
            args=(base_url, url_ids, filename_pdf, total_pages, output_dir),
            task_name=task_name
        )

    def start_processing(self) -> None:
        """Запускает задачу обработки изображений."""
        task_name = "Processing"
        logger.info(f"'{task_name}' task initiated.")
        input_folder = self.app_state.pages_dir.get().strip()
        output_folder = self.app_state.spreads_dir.get().strip()

        self._start_thread(
            target_func=self.handler.process_images,
            args=(input_folder, output_folder),
            task_name=task_name
        )

    def start_all(self) -> None:
        """Запускает комбинированную задачу скачивания и обработки."""
        task_name = "Download & Process"
        logger.info(f"'{task_name}' task initiated.")
        base_url = self.app_state.url_base.get().strip()
        url_ids = self.app_state.url_ids.get().strip()
        filename_pdf = self.app_state.pdf_filename.get().strip()
        total_pages = self.app_state.get_total_pages_int()
        pages_dir = self.app_state.pages_dir.get().strip()
        spreads_dir = self.app_state.spreads_dir.get().strip()

        if total_pages is None:
             logger.error("Invalid page count provided to start_all.")
             self.show_message_cb('error', "Ошибка", "Некорректное количество страниц.")
             return

        self._start_thread(
            target_func=self._run_all_sequence, # Целевая функция - внутренняя последовательность
            args=(base_url, url_ids, filename_pdf, total_pages, pages_dir, spreads_dir),
            task_name=task_name
        )

    def stop_task(self) -> None:
        """Сигнализирует текущей задаче об остановке."""
        if self.is_running():
            msg = "--- Получен сигнал СТОП от пользователя ---"
            logger.info(msg)
            self.status_cb(msg) # Обновляем статус через колбэк
            self.stop_event.set()
            # Кнопка СТОП будет выключена через set_buttons_state_cb в finally обертки
        else:
             logger.warning("Stop requested but no active thread found.")

    # --- Обертки выполнения задач ---

    def _thread_wrapper(self, target_func: callable, *args, task_name: str = "Task", **kwargs) -> None:
        """
        Обертка для выполнения целевой функции (download или process) в потоке.
        Обрабатывает результат, ошибки и обновляет GUI через колбэки.
        """
        result = None
        final_message = f"{task_name}: Задача завершена."
        error_occurred = False
        folder_to_open: Optional[str] = None
        success = False

        logger.info(f"Thread started execution for: {task_name}")
        try:
            # Вызываем основную логику (download_pages или process_images)
            result = target_func(*args, **kwargs)

            # Обработка результата в зависимости от задачи
            if target_func == self.handler.download_pages:
                success_count, total_dl_pages = result
                final_message = f"Скачивание завершено. Успешно: {success_count} из {total_dl_pages}."
                if not self.stop_event.is_set():
                    if success_count == total_dl_pages and total_dl_pages > 0:
                         success = True
                         self.show_message_cb('info', "Успех", "Все страницы успешно скачаны!")
                    elif success_count > 0:
                         success = True
                         self.show_message_cb('warning', "Завершено с ошибками", f"Скачано {success_count} из {total_dl_pages} страниц.\nПроверьте лог.")
                    else: # success_count == 0
                         self.show_message_cb('error', "Ошибка", f"Не удалось скачать ни одной страницы.\nПроверьте параметры и лог ({config.LOG_FILE}).")
                    if success_count > 0:
                         folder_to_open = args[-1]  # output_dir

            elif target_func == self.handler.process_images:
                processed_count, created_spread_count = result
                final_message = f"Обработка завершена. Обработано/скопировано: {processed_count}."
                if created_spread_count > 0:
                    final_message += f" Создано разворотов: {created_spread_count}."
                if not self.stop_event.is_set():
                    success = True
                    self.show_message_cb('info', "Успех", f"Создание разворотов завершено!\n{final_message}")
                    if processed_count > 0 or created_spread_count > 0:
                        folder_to_open = args[-1]  # output_folder

        except Exception as e:
            error_occurred = True
            final_message = f"{task_name}: Критическая ошибка при выполнении: {e}"
            logger.critical(f"Critical error in thread ({task_name}): {e}", exc_info=True)
            self.show_message_cb('error', "Критическая ошибка", f"{final_message}\n\nПодробности в лог-файле:\n{config.LOG_FILE}")
        finally:
            if not self.stop_event.is_set():
                 self.status_cb(f"--- {final_message} ---")
                 if folder_to_open and success and self.root:
                     # Используем root.after для вызова GUI-метода из потока
                     self.root.after(500, lambda p=folder_to_open: self.open_folder_cb(p))

            if self.root:
                 # Возвращаем кнопки в нормальное состояние
                 self.root.after(0, lambda: self.set_buttons_state_cb(False))

            self.current_thread = None # Сбрасываем текущий поток
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
        Вызывается как target_func через _start_thread -> _thread_wrapper.
        """
        task_name = "Download & Process"
        logger.info(f"Combined task sequence started: {task_name}")
        download_success_count = 0
        processing_done = False
        final_folder_to_open: Optional[str] = None
        overall_success = False
        error_occurred = False # Флаг для finally

        try:
            # --- Этап 1: Скачивание ---
            self.status_cb("--- НАЧАЛО: Скачивание страниц ---")
            success_count, total_dl_pages = self.handler.download_pages(
                base_url, url_ids, filename_pdf, total_pages, pages_dir
            )
            download_success_count = success_count

            if self.stop_event.is_set():
                self.status_cb("--- Скачивание прервано, обработка отменена ---")
                return # Выход из последовательности

            # Проверяем результат скачивания
            if download_success_count == 0:
                self.status_cb("--- Скачивание не удалось (0 страниц), обработка пропущена ---")
                self.show_message_cb('error', "Ошибка скачивания", f"Не удалось скачать ни одной страницы.\nОбработка не будет запущена.\nПроверьте лог ({config.LOG_FILE}).")
                return # Выход из последовательности

            elif download_success_count < total_dl_pages:
                 msg = f"--- Скачивание завершено с ошибками ({success_count}/{total_dl_pages}). Продолжаем обработку скачанных... ---"
                 self.status_cb(msg)
                 self.show_message_cb('warning', "Скачивание с ошибками", f"Скачано {success_count} из {t} страниц.\nОбработка будет запущена для скачанных файлов.")
            else:
                 self.status_cb(f"--- Скачивание успешно завершено ({success_count}/{total_dl_pages}) ---")

            time.sleep(0.5) # Небольшая пауза для наглядности

            # --- Этап 2: Обработка ---
            self.status_cb("--- НАЧАЛО: Создание разворотов ---")
            processed_count, created_spread_count = self.handler.process_images(
                pages_dir, spreads_dir
            )
            processing_done = True

            if self.stop_event.is_set():
                self.status_cb("--- Обработка прервана ---")
                return # Выход из последовательности

            final_message = f"Скачивание ({download_success_count}/{total_dl_pages}) и обработка ({processed_count} файлов, {created_spread_count} разворотов) завершены."
            self.status_cb(f"--- {final_message} ---")
            self.show_message_cb('info', "Завершено", final_message)
            overall_success = True

            if processed_count > 0 or created_spread_count > 0:
                 final_folder_to_open = spreads_dir

        except Exception as e:
            error_occurred = True
            final_message = f"{task_name}: Критическая ошибка: {e}"
            logger.critical(f"Critical error in combined sequence ({task_name}): {e}", exc_info=True)
            stage = "обработки" if download_success_count > 0 else "скачивания"
            self.show_message_cb('error', "Критическая ошибка", f"Ошибка на этапе {s}:\n{final_message}\n\nПодробности в лог-файле:\n{config.LOG_FILE}")
        # finally здесь не нужен, т.к. эта функция вызывается внутри _thread_wrapper,
        # который имеет свой finally для общих действий (сброс кнопок, потока и т.д.)
        # Но нам нужно обработать открытие папки специфично для этой последовательности

        # Этот код выполнится только если не было исключений и прерываний до этого момента
        if final_folder_to_open and overall_success and not self.stop_event.is_set() and self.root:
            self.root.after(500, lambda p=final_folder_to_open: self.open_folder_cb(p))