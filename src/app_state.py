import logging
import os
from pathlib import Path
import tkinter as tk
from typing import Optional

# Импортируем config для дефолтных значений
# Предполагаем, что config.py находится уровнем выше или настроен PYTHONPATH
# Если нет, возможно, придется передавать значения config в __init__
from . import config

logger = logging.getLogger(__name__)


class AppState:
    """Хранит состояние приложения (значения полей ввода)."""

    def __init__(self):
        logger.debug("Initializing AppState...")
        self.url_base = tk.StringVar(value=config.DEFAULT_URL_BASE)
        self.url_ids = tk.StringVar(value=config.DEFAULT_URL_IDS)
        self.pdf_filename = tk.StringVar(value=config.DEFAULT_PDF_FILENAME)
        self.total_pages = tk.StringVar(value=config.DEFAULT_TOTAL_PAGES)
        self.pages_dir = tk.StringVar(value=config.DEFAULT_PAGES_DIR)
        self.spreads_dir = tk.StringVar(value=config.DEFAULT_SPREADS_DIR)
        logger.debug("AppState initialized with default values.")

    def get_settings_dict(self) -> dict:
        """Возвращает словарь текущих настроек для сохранения."""
        return {
            "url_base": self.url_base.get(),
            "url_ids": self.url_ids.get(),
            "pdf_filename": self.pdf_filename.get(),
            "total_pages": self.total_pages.get(),
            "pages_dir": self.pages_dir.get(),
            "spreads_dir": self.spreads_dir.get(),
        }

    def set_from_dict(self, settings: dict):
        """Устанавливает значения из словаря (загруженные настройки)."""
        logger.debug(f"Setting AppState from dict: {settings}")
        self.url_base.set(settings.get("url_base", config.DEFAULT_URL_BASE))
        self.url_ids.set(settings.get("url_ids", config.DEFAULT_URL_IDS))
        self.pdf_filename.set(settings.get("pdf_filename", config.DEFAULT_PDF_FILENAME))
        self.total_pages.set(settings.get("total_pages", config.DEFAULT_TOTAL_PAGES))
        self.pages_dir.set(settings.get("pages_dir", config.DEFAULT_PAGES_DIR))
        self.spreads_dir.set(settings.get("spreads_dir", config.DEFAULT_SPREADS_DIR))
        logger.debug("AppState updated from dict.")

    def get_total_pages_int(self) -> Optional[int]:
        """Безопасно возвращает количество страниц как int."""
        try:
            pages = int(self.total_pages.get().strip())
            return pages if pages > 0 else None
        except ValueError:
            return None

    def validate_for_download(self) -> list[str]:
        """Проверяет поля для скачивания, возвращает список имен некорректных полей."""
        errors = []
        if not self.url_base.get().strip():
            errors.append("Базовый URL")
        if not self.url_ids.get().strip():
            errors.append("ID файла")
        if not self.pdf_filename.get().strip():
            errors.append("Имя файла на сайте")
        if not self.pages_dir.get().strip():
            errors.append("Папка для страниц")

        total_pages_str = self.total_pages.get().strip()
        if not total_pages_str:
            errors.append("Кол-во страниц")
        else:
            try:
                pages = int(total_pages_str)
                if pages <= 0:
                    errors.append("Кол-во страниц (должно быть > 0)")
            except ValueError:
                errors.append("Кол-во страниц (должно быть числом)")

        logger.debug(f"Download validation result: {errors}")
        return errors

    def validate_for_processing(self, check_dir_exists: bool = True) -> list[str]:
        """Проверяет поля для обработки, возвращает список имен некорректных полей."""
        errors = []
        pages_dir = self.pages_dir.get().strip()
        spreads_dir = self.spreads_dir.get().strip()

        if not pages_dir:
            errors.append("Папка для страниц")
        if not spreads_dir:
            errors.append("Папка для разворотов")

        if errors:  # Если уже есть ошибки, нет смысла проверять папку
            logger.debug(f"Processing validation result (missing fields): {errors}")
            return errors

        if check_dir_exists:
            pages_path = Path(pages_dir)
            if not pages_path.is_dir():
                errors.append(f"Папка для страниц ('{pages_dir}' не найдена)")
            else:
                try:
                    os.listdir(pages_path)
                    logger.debug(
                        f"Read access check passed for directory: {pages_path}"
                    )
                    pass
                except OSError as e:
                    logger.warning(
                        f"OS error during access check for {pages_path}: {e}",
                        exc_info=True,
                    )
                    errors.append(f"Папка для страниц (ошибка доступа/чтения: {e})")

        logger.debug(f"Processing validation result: {errors}")
        return errors
