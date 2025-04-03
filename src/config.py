# --- НАСТРОЙКИ ПОВЕДЕНИЯ ---
DEFAULT_DELAY_SECONDS = 0.5 # Задержка между запросами к серверу (секунды)
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
INITIAL_COOKIE_URL = "https://elib.rgo.ru/" # URL для получения начальных кук
SETTINGS_FILE = "settings.json" # Файл для сохранения настроек GUI
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff') # Расширения обрабатываемых изображений
DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD = 1.1 # Порог определения разворота (ширина / высота)


# --- НАСТРОЙКИ ПОВТОРНЫХ ПОПЫТОК СКАЧИВАНИЯ ---
MAX_RETRIES = 3 # Максимальное количество повторных попыток для одной страницы
RETRY_DELAY = 2 # Задержка перед повторной попыткой (секунды)
RETRY_ON_HTTP_CODES = [500, 502, 503, 504] # HTTP статусы, при которых пытаемся повторить

# --- НАСТРОЙКИ КАЧЕСТВА ---
JPEG_QUALITY = 95 # Качество сохраняемых JPEG разворотов

# --- ПУТИ ПО УМОЛЧАНИЮ (можно оставить пустыми или задать) ---
DEFAULT_PAGES_DIR = "C:/downloaded_pages"
DEFAULT_SPREADS_DIR = "C:/final_spreads"
DEFAULT_URL_BASE = "https://elib.rgo.ru/safe-view/"
DEFAULT_URL_IDS = "" # Оставим пустым, чтобы пользователь вводил сам
DEFAULT_PDF_FILENAME = "" # Оставим пустым
DEFAULT_TOTAL_PAGES = "" # Оставим пустым