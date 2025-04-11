import logging
import os
import shutil
import time
import types
from pathlib import Path
from typing import Tuple
from PIL import Image

# Общие типы и зависимости
from .types import ProgressCallback, StatusCallback, StopEvent
ConfigModule = types.ModuleType
UtilsModule = types.ModuleType


def process_images_in_folders(
    input_folder: str,
    output_folder: str,
    status_callback: StatusCallback,
    progress_callback: ProgressCallback,
    stop_event: StopEvent,
    config: ConfigModule,
    utils: UtilsModule,
    logger: logging.Logger
) -> Tuple[int, int]:
    """
    Обрабатывает скачанные изображения: копирует обложки/развороты,
    склеивает одиночные страницы.

    Args:
        input_folder: Папка со скачанными страницами.
        output_folder: Папка для сохранения разворотов.
        status_callback: Функция для отправки сообщений о статусе (в GUI).
        progress_callback: Функция для обновления прогресса (в GUI).
        stop_event: Событие для сигнализации об остановке операции.
        config: Модуль с конфигурацией.
        utils: Модуль с утилитами.
        logger: Экземпляр логгера.

    Returns:
        Кортеж (количество обработанных/скопированных файлов,
                 количество созданных разворотов).
    """
    stop_event.clear() # Используем переданный event
    input_path = Path(input_folder)
    output_path = Path(output_folder)

    status_callback(f"Начинаем обработку изображений из '{input_folder}' в '{output_folder}'...")
    logger.info(f"Starting image processing. Input: '{input_path}', Output: '{output_path}'")

    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        msg = f"Ошибка создания папки для разворотов '{output_folder}': {e}"
        status_callback(msg)
        logger.error(msg, exc_info=True)
        return 0, 0

    try:
        all_files = [
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in config.IMAGE_EXTENSIONS
        ]
        logger.info(f"Found {len(all_files)} potential image files in {input_path}.")
    except FileNotFoundError:
        msg = f"Ошибка: Папка со страницами '{input_folder}' не найдена."
        status_callback(msg)
        logger.error(msg)
        return 0, 0
    except OSError as e:
        msg = f"Ошибка чтения папки '{input_folder}': {e}"
        status_callback(msg)
        logger.error(msg, exc_info=True)
        return 0, 0

    numbered_files = []
    for f in all_files:
        page_num = utils.get_page_number(f.name)
        if page_num != -1:
            numbered_files.append((page_num, f))
        else:
            logger.warning(f"Skipping file without page number: {f.name}")

    sorted_files = [f for _, f in sorted(numbered_files)]
    total_files_to_process = len(sorted_files)
    logger.info(f"Found {total_files_to_process} numbered image files to process.")

    if not sorted_files:
        status_callback("В папке не найдено подходящих файлов изображений с номерами.")
        logger.warning(f"No processable image files found in {input_path}")
        return 0, 0

    status_callback(f"Найдено {total_files_to_process} файлов. Создание разворотов...")
    progress_callback(0, total_files_to_process)

    page_index = 0
    processed_count = 0 # Скопировано или склеено
    created_spread_count = 0

    while page_index < total_files_to_process:
        if stop_event.is_set():
            status_callback("--- Обработка прервана пользователем ---")
            logger.info("Processing interrupted by user.")
            break

        current_file_path = sorted_files[page_index]
        current_page_num = utils.get_page_number(current_file_path.name)
        current_is_spread = page_index > 0 and utils.is_likely_spread(
            current_file_path, config.DEFAULT_ASPECT_RATIO_THRESHOLD
        )

        logger.debug(f"Processing index {page_index}: {current_file_path.name} (Page: {current_page_num}, IsSpread: {current_is_spread})")

        processed_increment = 0 # Обработали на итерации

        # --- Вариант 1: Копирование (Обложка или уже готовый разворот) ---
        if page_index == 0 or current_is_spread:
            output_filename = f"spread_{current_page_num:03d}{current_file_path.suffix}"
            output_file_path = output_path / output_filename
            action_desc = 'обложку' if page_index == 0 else 'готовый разворот'
            status_msg = f"Копирую {action_desc}: {current_file_path.name} -> {output_filename}"
            status_callback(status_msg)
            logger.info(f"Copying {'cover' if page_index == 0 else 'existing spread'}: {current_file_path.name} -> {output_filename}")
            try:
                shutil.copy2(current_file_path, output_file_path)
                processed_increment = 1
            except Exception as e:
                msg = f"Ошибка при копировании {current_file_path.name}: {e}"
                status_callback(msg)
                logger.error(msg, exc_info=True)
            page_index += 1

        # --- Вариант 2: Текущий файл - одиночная страница ---
        else:
            # Проверяем, есть ли следующий файл
            if page_index + 1 < total_files_to_process:
                next_file_path = sorted_files[page_index + 1]
                next_page_num = utils.get_page_number(next_file_path.name)
                # Определяем, является ли СЛЕДУЮЩИЙ файл одиночным
                next_is_single = not utils.is_likely_spread(
                    next_file_path, config.DEFAULT_ASPECT_RATIO_THRESHOLD
                )
                logger.debug(f"  Next file: {next_file_path.name} (Page: {next_page_num}, IsSingle: {next_is_single})")

                # --- Вариант 2.1: Следующий тоже одиночный ---
                if next_is_single:
                    output_filename = f"spread_{current_page_num:03d}-{next_page_num:03d}.jpg"
                    output_file_path = output_path / output_filename
                    status_msg = f"Создаю разворот: {current_file_path.name} + {next_file_path.name} -> {output_filename}"
                    status_callback(status_msg)
                    logger.info(f"Creating spread: {current_file_path.name} + {next_file_path.name} -> {output_filename}")

                    try:
                        with Image.open(current_file_path) as img_left, \
                             Image.open(next_file_path) as img_right:

                            w_left, h_left = img_left.size
                            w_right, h_right = img_right.size

                            # Приводим к одной высоте по LANCZOS, если нужно
                            if h_left != h_right:
                                target_height = max(h_left, h_right) # Берем максимальную высоту
                                logger.debug(f"    Resizing images to target height: {target_height}px (using LANCZOS)")

                                # Масштабируем левое изображение
                                ratio_left = target_height / h_left
                                w_left_final = int(w_left * ratio_left)
                                img_left_final = img_left.resize((w_left_final, target_height), Image.Resampling.LANCZOS)
                                logger.debug(f"    Left resized to: {w_left_final}x{target_height}")

                                # Масштабируем правое изображение
                                ratio_right = target_height / h_right
                                w_right_final = int(w_right * ratio_right)
                                img_right_final = img_right.resize((w_right_final, target_height), Image.Resampling.LANCZOS)
                                logger.debug(f"    Right resized to: {w_right_final}x{target_height}")
                            else:
                                target_height = h_left
                                img_left_final = img_left
                                img_right_final = img_right
                                w_left_final = w_left
                                w_right_final = w_right
                                logger.debug("    Heights match, no resize needed.")

                            total_width = w_left_final + w_right_final
                            logger.debug(f"    Creating new spread image: {total_width}x{target_height}")
                            spread_img = Image.new('RGB', (total_width, target_height), (255, 255, 255))
                            spread_img.paste(img_left_final.convert('RGB'), (0, 0))
                            spread_img.paste(img_right_final.convert('RGB'), (w_left_final, 0))
                            spread_img.save(output_file_path, "JPEG", quality=config.JPEG_QUALITY, optimize=True)

                            created_spread_count += 1
                            processed_increment = 2
                            logger.info(f"    Spread created successfully: {output_filename}")

                    except Exception as e:
                        msg = f"Ошибка при создании разворота для {current_file_path.name} и {next_file_path.name}: {e}"
                        status_callback(msg)
                        logger.error(msg, exc_info=True)
                        # Пропускаем оба файла, но считаем обработанными
                        processed_increment = 2
                    page_index += 2 # Переходим через пару

                # --- Вариант 2.2: Текущий одиночный, следующий - разворот ---
                else:
                    output_filename = f"spread_{current_page_num:03d}{current_file_path.suffix}"
                    output_file_path = output_path / output_filename
                    status_msg = f"Копирую одиночную страницу (следующий - разворот): {current_file_path.name} -> {output_filename}"
                    status_callback(status_msg)
                    logger.info(f"Copying single page (next is spread): {current_file_path.name} -> {output_filename}")
                    try:
                        shutil.copy2(current_file_path, output_file_path)
                        processed_increment = 1
                    except Exception as e:
                        msg = f"Ошибка при копировании одиночной {current_file_path.name}: {e}"
                        status_callback(msg)
                        logger.error(msg, exc_info=True)
                    page_index += 1 # Переходим к следующему файлу (который разворот)

            # --- Вариант 2.3: Текущий одиночный - последний файл ---
            else:
                output_filename = f"spread_{current_page_num:03d}{current_file_path.suffix}"
                output_file_path = output_path / output_filename
                status_msg = f"Копирую последнюю одиночную страницу: {current_file_path.name} -> {output_filename}"
                status_callback(status_msg)
                logger.info(f"Copying last single page: {current_file_path.name} -> {output_filename}")
                try:
                    shutil.copy2(current_file_path, output_file_path)
                    processed_increment = 1
                except Exception as e:
                    msg = f"Ошибка при копировании последней одиночной {current_file_path.name}: {e}"
                    status_callback(msg)
                    logger.error(msg, exc_info=True)
                page_index += 1 # Завершаем цикл

        processed_count += processed_increment
        progress_callback(page_index, total_files_to_process)
        # Чтобы GUI успевал обновляться
        time.sleep(0.01)


    logger.info(f"Processing finished. Processed/copied: {processed_count}, Spreads created: {created_spread_count}")
    status_callback(f"Обработка завершена. Обработано/скопировано: {processed_count}. Создано разворотов: {created_spread_count}.")
    return processed_count, created_spread_count
