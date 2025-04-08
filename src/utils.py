import os
import re
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from PIL import Image

from . import config

logger = logging.getLogger(__name__)

def get_page_number(filename: str) -> int:
    """
    Извлекает номер страницы из имени файла согласно логике сайта.
    Ищет первое число в строке.

    Args:
        filename: Имя файла.

    Returns:
        Номер страницы или -1, если номер не найден.
    """
    if not filename:
        return -1
    match = re.search(r'\d+', filename)
    return int(match.group()) if match else -1


def is_likely_spread(image_path: str | Path, threshold: Optional[float] = None) -> bool:
    """
    Проверяет, может ли изображение уже быть разворотом,
    основываясь на соотношении сторон (ширина / высота).

    Args:
        image_path: Путь к файлу.
        threshold: Пороговое значение соотношения сторон.
                   Если None, используется значение из config.

    Returns:
        True, если соотношение сторон больше порога, иначе False.
    """
    if threshold is None:
        threshold = config.DEFAULT_ASPECT_RATIO_THRESHOLD

    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if height == 0:
                logger.warning(f"Image has zero height: {image_path}")
                return False
            aspect_ratio = width / height
            logger.debug(f"Image: {Path(image_path).name}, Size: {width}x{height}, Ratio: {aspect_ratio:.2f}, Threshold: {threshold}")
            return aspect_ratio > threshold
    except FileNotFoundError:
        logger.error(f"Image file not found for aspect ratio check: {image_path}")
        return False
    except Exception as e:
        logger.warning(f"Could not check aspect ratio for {image_path}: {e}", exc_info=True)
        return False


def resource_path(relative_path: str) -> str:
    """
    Возвращает абсолютный путь к ресурсу, работает как в обычном режиме,
    так и при сборке с помощью PyInstaller (_MEIPASS).

    Args:
        relative_path: Относительный путь к ресурсу (относительно корня проекта).

    Returns:
        Абсолютный путь к ресурсу.
    """
    try:
        base_path = Path(sys._MEIPASS)
        logger.debug(f"Running in PyInstaller bundle, MEIPASS: {base_path}")
    except AttributeError:
        utils_file_path = Path(__file__).resolve()
        src_dir = utils_file_path.parent
        base_path = src_dir.parent
        logger.debug(f"Running as script, calculated project root: {base_path}")

    final_path = base_path / relative_path
    logger.debug(f"Resolved resource path for '{relative_path}': '{final_path}'")
    return str(final_path)


def setup_logging():
    """Настраивает базовую конфигурацию логирования."""
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_file = config.LOG_FILE

    log_dir = Path(log_file).parent
    if not log_dir.is_dir():
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"FATAL: Could not create log directory {log_dir}: {e}")

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(config.LOG_LEVEL)

        root_logger = logging.getLogger()
        root_logger.setLevel(config.LOG_LEVEL) # Минимум для всех хендлеров
        root_logger.addHandler(file_handler)

        # Опционально, себе не засоряю и вам не советую
        # console_handler = logging.StreamHandler(sys.stdout)
        # console_handler.setFormatter(log_formatter)
        # console_handler.setLevel(logging.DEBUG)
        # root_logger.addHandler(console_handler)

        logging.info("="*20 + f" Logging started for {config.APP_NAME} " + "="*20)

    except Exception as log_e:
        print(f"FATAL: Could not configure file logging to {log_file}: {log_e}", file=sys.stderr)
