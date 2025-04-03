# --- НАСТРОЙКИ ОБЩИЕ ---
SETTINGS_FILE = "settings.json"
LOG_FILE = "parsing.log"


# --- НАСТРОЙКИ СКАЧИВАНИЯ ---
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
INITIAL_COOKIE_URL = "https://elib.rgo.ru/"
MAX_RETRIES = 3  # Для каждой страницы
RETRY_ON_HTTP_CODES = [500, 502, 503, 504]  # HTTP статусы для повтора
DEFAULT_DELAY_SECONDS = 0.5  # Между запросами к серверу (секунд)
RETRY_DELAY = 2  # Задержка перед повторной попыткой (секунд)
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')


# --- НАСТРОЙКИ РАЗВОРОТОВ ---
DEFAULT_SPREAD_ASPECT_RATIO_THRESHOLD = 1.1 # (ширина / высота)
JPEG_QUALITY = 95


# --- ПУТИ ПО УМОЛЧАНИЮ ---
DEFAULT_PAGES_DIR = "C:/downloaded_pages"
DEFAULT_SPREADS_DIR = "C:/final_spreads"
DEFAULT_URL_BASE = "https://elib.rgo.ru/safe-view/"
DEFAULT_URL_IDS = ""
DEFAULT_PDF_FILENAME = ""
DEFAULT_TOTAL_PAGES = ""
