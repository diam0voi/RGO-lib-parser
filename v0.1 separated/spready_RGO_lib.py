import os
import re

from PIL import Image

""" --- НАСТРОЙКИ --- """
INPUT_DIR = "..."  # Папка со скачанными страницами
OUTPUT_DIR = "sprds_smart"  # Папка для итоговых разворотов
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff")
SPREAD_BG_COLOR = (255, 255, 255)  # Белый фон
SPREAD_ASPECT_RATIO_THRESHOLD = (
    1.1  # Порог соотношения сторон (ширина / высота) для определения разворота.
)
# Если оказалось W/H > порога, считаем разворотом.
# Обычная страница ~0.6-0.7, разворот ~1.2-1.5.


def get_page_number(filename):
    match = re.search(r"\d+", filename)
    return int(match.group()) if match else -1


def is_likely_spread(image_path, threshold):
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if height == 0:
                return False
            aspect_ratio = width / height
            # print(f"Debug: {os.path.basename(image_path)} - W: {width}, H: {height}, Ratio: {aspect_ratio:.2f}")  # Для экспериментов
            return aspect_ratio > threshold
    except Exception as e:
        print(
            f"Warning: Could not read image {os.path.basename(image_path)} to check aspect ratio: {e}"
        )
        return False


def create_smart_spreads(input_folder, output_folder):
    print(f"Обработка папки: {input_folder}")
    if not os.path.isdir(input_folder):
        print(f"Ошибка: Папка '{input_folder}' не найдена.")
        return

    os.makedirs(output_folder, exist_ok=True)

    try:
        all_files = [
            f for f in os.listdir(input_folder) if f.lower().endswith(IMAGE_EXTENSIONS)
        ]
    except FileNotFoundError:
        print(f"Ошибка: Не удалось получить доступ к папке '{input_folder}'.")
        return

    sorted_files = sorted(
        [f for f in all_files if get_page_number(f) != -1], key=get_page_number
    )

    if not sorted_files:
        print("В папке не найдено подходящих файлов изображений с номерами.")
        return

    print(
        f"Найдено {len(sorted_files)} страниц/файлов. Начинаем умное создание разворотов..."
    )

    page_index = 0
    while page_index < len(sorted_files):
        current_file = sorted_files[page_index]
        current_path = os.path.join(input_folder, current_file)
        current_page_num = get_page_number(current_file)
        current_is_spread = page_index > 0 and is_likely_spread(
            current_path, SPREAD_ASPECT_RATIO_THRESHOLD
        )

        # Вариант 1: Текущий файл - это уже разворот или обложка
        if current_is_spread or page_index == 0:
            output_filename = f"spread_{current_page_num:03d}.jpg"
            output_path = os.path.join(output_folder, output_filename)
            try:
                print(
                    f"Копирую {'обложку' if page_index == 0 else 'готовый разворот'}: {current_file} -> {output_filename}"
                )
                img = Image.open(current_path)
                img.convert("RGB").save(output_path, "JPEG", quality=95)
                img.close()
            except Exception as e:
                print(f"Ошибка при копировании {current_file}: {e}")
            page_index += 1
            continue

        # Вариант 2: Текущий файл - это одиночная страница
        if page_index + 1 < len(sorted_files):  # Проверяем, есть ли следующий файл
            next_file = sorted_files[page_index + 1]
            next_path = os.path.join(input_folder, next_file)
            next_page_num = get_page_number(next_file)

            next_is_single = not is_likely_spread(
                next_path, SPREAD_ASPECT_RATIO_THRESHOLD
            )

            # Вариант 2.1: Следующий файл тоже одиночный - СКЛЕИВАЕМ
            if next_is_single:
                output_filename = (
                    f"spread_{current_page_num:03d}-{next_page_num:03d}.jpg"
                )
                output_path = os.path.join(output_folder, output_filename)
                print(
                    f"Создаю разворот из одиночных: {current_file} + {next_file} -> {output_filename}"
                )

                try:
                    img_left = Image.open(current_path)
                    img_right = Image.open(next_path)
                    width_left, height_left = img_left.size
                    width_right, height_right = img_right.size
                    total_width = width_left + width_right
                    max_height = max(height_left, height_right)
                    spread_img = Image.new(
                        "RGB", (total_width, max_height), SPREAD_BG_COLOR
                    )
                    spread_img.paste(img_left, (0, 0))
                    spread_img.paste(img_right, (width_left, 0))
                    spread_img.save(output_path, "JPEG", quality=95)
                    img_left.close()
                    img_right.close()
                except Exception as e:
                    print(
                        f"Ошибка при создании разворота для {current_file} и {next_file}: {e}"
                    )

                page_index += 2  # Перескакиваем через обработанную пару
                continue

        # Вариант 2.2: Следующего файла нет ИЛИ следующий файл - разворот
        output_filename = f"spread_{current_page_num:03d}.jpg"
        output_path = os.path.join(output_folder, output_filename)
        try:
            print(
                f"Копирую одиночную страницу (нет пары или след. - разворот): {current_file} -> {output_filename}"
            )
            img = Image.open(current_path)
            img.convert("RGB").save(output_path, "JPEG", quality=95)
            img.close()
        except Exception as e:
            print(f"Ошибка при копировании одиночной {current_file}: {e}")

        page_index += 1

    print(f"Обработка папки {input_folder} завершена. Результаты в {output_folder}")


# Для обработки нескольких папок:
"""
input_folders = ["journal_pages_book1", "journal_pages_book2_problem", "journal_pages_book3"]
output_base = "spreads_output_smart"
for i, folder in enumerate(input_folders):
    output_folder_name = f"book_{i+1}_spreads"
    full_output_path = os.path.join(output_base, output_folder_name)
    create_smart_spreads(folder, full_output_path)
"""

create_smart_spreads(INPUT_DIR, OUTPUT_DIR)
print("\nГотово!")
