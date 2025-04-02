import requests
import base64
import time
import os
from urllib.parse import quote  # Для кодирования имени

''' --- НАСТРОЙКИ --- '''
BASE_URL = "https://elib.rgo.ru/safe-view/123456789/.../1/"  # ID!
FILENAME_PDF = "..."
TOTAL_PAGES = 0  # Количество страниц!
OUTPUT_DIR = "dwnldd_pages"  # Создастся папка с этим названием
COOKIE_STRING = "JSESSIONID=...; ym_uid=...; ym_d=...; ym_isad=..."  # КУКИ!
DELAY_SECONDS = 1  # Антибан
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"


cookies = {c.split('=')[0].strip(): c.split('=')[1].strip() for c in COOKIE_STRING.split(';') if '=' in c}
headers = {
    'User-Agent': USER_AGENT
}
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Начинаем скачивание {TOTAL_PAGES} страниц...")

# Для авто куки, если наши собъются
session = requests.Session()
session.headers.update(headers)
session.cookies.update(cookies)

for i in range(TOTAL_PAGES):
    page_string = f"{FILENAME_PDF}/{i}"
    
    # Кодировка в Base64
    page_b64_bytes = base64.b64encode(page_string.encode('utf-8'))
    page_b64_string = page_b64_bytes.decode('utf-8')
    
    final_url = BASE_URL + page_b64_string
    
    output_filename = os.path.join(OUTPUT_DIR, f"page_{i:03d}.jpg")  # Имя с ведущими нулями

    print(f"Скачиваю страницу {i} -> {output_filename} из {final_url}")
    
    try:
        response = session.get(final_url, timeout=30)
        response.raise_for_status() # Проверка на ошибки HTTP (4xx, 5xx)

        # Определяем расширение, если возможно
        content_type = response.headers.get('Content-Type', '').lower()
        extension = ".jpg"
        if 'jpeg' in content_type or 'jpg' in content_type:
            extension = ".jpg"
        elif 'png' in content_type:
            extension = ".png"
        elif 'gif' in content_type:
            extension = ".gif"
        output_filename = os.path.join(OUTPUT_DIR, f"page_{i:03d}{extension}")

        with open(output_filename, 'wb') as f:
            f.write(response.content)

        if os.path.getsize(output_filename) == 0:
             print(f"Предупреждение: Файл {output_filename} пустой.")

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при скачивании страницы {i}: {e}")


    time.sleep(DELAY_SECONDS)

print("Скачивание завершено!")
