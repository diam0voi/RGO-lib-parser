import os
from pathlib import Path
import logging

# --- Общее ---
APP_NAME: str = "RGO Lib Parser"
SETTINGS_FILE: str = "settings.json"
LOG_FILE: str = "parsing.log"
LOG_LEVEL: int = logging.INFO
LOG_MAX_BYTES: int = 2 * 1024 * 1024  # 2 MB
LOG_BACKUP_COUNT: int = 2

# --- GUI ---
WINDOW_TITLE: str = f"Загрузчик + склейщик файлов библиотеки РГО. v1.4 by b0s"
WINDOW_ICON_PATH: str = "assets/window_bnwbook.png"
DEFAULT_ASPECT_RATIO_THRESHOLD: float = 1.1  # Порог определения разворота (w / h)
JPEG_QUALITY: int = 95  # Для разворотов

# --- Сеть и Скачивание ---
DEFAULT_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
INITIAL_COOKIE_URL: str = "https://elib.rgo.ru/"
MAX_RETRIES: int = 3  # Для каждой страницы
RETRY_ON_HTTP_CODES: list[int] = [500, 502, 503, 504]
DEFAULT_DELAY_SECONDS: float = 0.5  # Между запросами (секунд)
RETRY_DELAY: float = 2.0  # Перед повтором (секунд)
REQUEST_TIMEOUT: tuple[int, int] = (10, 30)  # Для connect и read
IMAGE_EXTENSIONS: tuple[str, ...] = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')

# --- Пути ---
try:
    HOME_DIR = Path.home()
    DEFAULT_APP_DATA_DIR = HOME_DIR / f".{APP_NAME}_data"
    DEFAULT_APP_DATA_DIR.mkdir(exist_ok=True)
    _default_pages_path = DEFAULT_APP_DATA_DIR / "downloaded_pages"
    _default_spreads_path = DEFAULT_APP_DATA_DIR / "final_spreads"
except Exception:
    _default_pages_path = Path("./downloaded_pages")
    _default_spreads_path = Path("./final_spreads")

DEFAULT_PAGES_DIR: str = str(_default_pages_path)
DEFAULT_SPREADS_DIR: str = str(_default_spreads_path)

# --- Поля ---
DEFAULT_URL_BASE: str = "https://elib.rgo.ru/safe-view/"
DEFAULT_URL_IDS: str = ""
DEFAULT_PDF_FILENAME: str = ""
DEFAULT_TOTAL_PAGES: str = ""

# --- Сборка (для PyInstaller) ---
WIN_ICON_ASSET: str = "assets/winapp_lilacbook.ico"
MAC_ICON_ASSET: str = "assets/macapp_lilacbook.icns"
DATA_ASSET: str = "assets/window_bnwbook.png"
WIN_APP_NAME: str = APP_NAME
MAC_APP_NAME: str = f"{APP_NAME}.app"
LINUX_APP_NAME: str = APP_NAME
