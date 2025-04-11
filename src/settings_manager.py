# src/settings_manager.py
import json
import logging
from pathlib import Path

# Импортируем зависимости
from .app_state import AppState
from . import config

logger = logging.getLogger(__name__)

class SettingsManager:
    """Отвечает за загрузку и сохранение настроек приложения."""
    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.settings_file_path = Path(config.SETTINGS_FILE)
        self.initial_settings_dict: dict = {}
        logger.debug(f"SettingsManager initialized. File path: {self.settings_file_path}")

    def load_settings(self) -> None:
        """Загружает настройки из файла и обновляет AppState."""
        loaded_settings = {}
        try:
            if self.settings_file_path.is_file():
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                logger.info(f"Settings loaded successfully from {self.settings_file_path}")
            else:
                logger.info(f"Settings file {self.settings_file_path} not found, using defaults.")
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load or parse settings from {self.settings_file_path}: {e}")
            # Не показываем ошибку пользователю при загрузке

        # Обновляем состояние приложения
        self.app_state.set_from_dict(loaded_settings)
        # Сохраняем начальное состояние для сравнения при выходе
        self.initial_settings_dict = self.app_state.get_settings_dict()
        logger.debug(f"Initial settings captured after load: {self.initial_settings_dict}")

    def save_settings(self) -> bool:
        """
        Сохраняет текущее состояние AppState в файл настроек.
        Возвращает True в случае успеха, False в случае ошибки.
        """
        settings_to_save = self.app_state.get_settings_dict()
        try:
            self.settings_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file_path, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, indent=4, ensure_ascii=False)
            logger.info(f"Settings successfully saved to {self.settings_file_path}")
            # Обновляем initial_settings_dict после успешного сохранения
            self.initial_settings_dict = settings_to_save
            return True
        except IOError as e:
            logger.error(f"Could not save settings to {self.settings_file_path}: {e}", exc_info=True)
            return False
        except Exception as e:
             logger.error(f"Unexpected error saving settings: {e}", exc_info=True)
             return False

    def save_settings_if_changed(self) -> None:
        """Сравнивает текущие настройки с начальными и сохраняет, если есть разница."""
        current_settings = self.app_state.get_settings_dict()
        if current_settings != self.initial_settings_dict:
            logger.info("Settings have changed since last load/save. Saving...")
            if not self.save_settings():
                 # Показываем ошибку пользователю через логгер, т.к. прямого доступа к messagebox нет
                 logger.error("Failed to save settings on exit.")
                 # Можно было бы передать callback для показа ошибки, но усложнит
        else:
            logger.info("Settings are unchanged. Skipping save on exit.")