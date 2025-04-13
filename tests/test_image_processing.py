# tests/test_image_processing.py
import logging
import shutil
import types
import time
from pathlib import Path
from unittest.mock import MagicMock, call, ANY # ANY поможет проверять вызовы с динамическими аргументами

import pytest
from PIL import Image, ImageChops # Нужен для моков и проверки типов

# Импортируем тестируемую функцию
from src.image_processing import process_images_in_folders

# --- Фикстуры для моков ---

@pytest.fixture
def mock_config():
    """Фикстура для мока модуля config."""
    config = types.ModuleType("config")
    config.IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
    config.DEFAULT_ASPECT_RATIO_THRESHOLD = 1.2 # Пример значения
    config.JPEG_QUALITY = 85 # Пример значения
    return config

@pytest.fixture
def mock_utils():
    """Фикстура для мока модуля utils."""
    utils = types.ModuleType("utils")
    # Используем MagicMock для методов, чтобы можно было проверять вызовы
    utils.get_page_number = MagicMock()
    utils.is_likely_spread = MagicMock()
    return utils

@pytest.fixture
def mock_logger():
    """Фикстура для мока логгера."""
    logger = MagicMock(spec=logging.Logger)
    # Можно добавить методы, если нужно проверять конкретные уровни логгирования
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    return logger

@pytest.fixture
def mock_status_callback():
    """Фикстура для мока status_callback."""
    return MagicMock()

@pytest.fixture
def mock_progress_callback():
    """Фикстура для мока progress_callback."""
    return MagicMock()

@pytest.fixture
def mock_stop_event():
    """Фикстура для мока stop_event."""
    event = MagicMock()
    event.is_set = MagicMock(return_value=False) # По умолчанию не остановлено
    event.clear = MagicMock()
    return event

@pytest.fixture
def mock_pil_image():
    """Фикстура для создания мока объекта PIL Image."""
    img = MagicMock(spec=Image.Image)
    img.size = (800, 1200) # Пример размера одиночной страницы
    img.resize = MagicMock(return_value=img) # resize возвращает новый (мок) объект
    img.convert = MagicMock(return_value=img) # convert возвращает новый (мок) объект
    img.paste = MagicMock()
    img.save = MagicMock()
    # Для поддержки 'with Image.open(...) as img:'
    img.__enter__ = MagicMock(return_value=img)
    img.__exit__ = MagicMock(return_value=None)
    return img

# --- Вспомогательная функция для создания моков файлов ---
def create_mock_files(mocker, file_paths):
    """Создает мок Path объекта для input_dir с замоканным iterdir."""
    mock_input_path = MagicMock(spec=Path)
    mock_iterdir_results = []
    for p in file_paths:
        mock_file = MagicMock(spec=Path)
        mock_file.name = p.name
        mock_file.suffix = p.suffix.lower()
        mock_file.is_file.return_value = True
        # Переопределяем __str__ для логирования и сообщений
        mock_file.__str__.return_value = str(p)
        # __fspath__ нужен для os.path-совместимых функций, как shutil.copy2
        mock_file.__fspath__.return_value = str(p)
        # Добавим сам путь для сравнения в side_effect для Path
        mock_file.absolute.return_value = p.absolute()
        # Добавим сам объект Path для сравнения в is_likely_spread
        mock_file.path_obj = p # Сохраним реальный Path для возможных сравнений
        mock_iterdir_results.append(mock_file)

    mock_input_path.iterdir.return_value = mock_iterdir_results
    # Добавим __str__ самому моку папки
    mock_input_path.__str__.return_value = str(file_paths[0].parent) if file_paths else "mock_input_path"
    return mock_input_path, mock_iterdir_results


# --- Тесты ---

def test_process_images_success_copy_and_merge(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event, mock_pil_image
):
    """
    Тест успешного выполнения: копирование обложки, склейка пары, копирование одиночной.
    """
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    # --- Настройка моков ---
    # 1. Файлы в input_dir
    mock_file_paths_real = [
        input_dir / "000_cover.jpg",
        input_dir / "001_page.png",
        input_dir / "002_page.jpg",
        input_dir / "003_single.jpeg",
        input_dir / "ignored.txt", # Файл с неверным расширением
        input_dir / "no_number.jpg", # Файл без номера
    ]
    # Создаем моки файлов
    mock_input_path, mock_iterdir_results = create_mock_files(mocker, mock_file_paths_real)

    # Мокаем Path()
    # Важно: Path(output_folder) должен вернуть реальный объект для mkdir
    mock_output_path_obj = Path(output_dir)
    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            # Для случаев, когда Path используется для создания output_file_path
            # Нужно вернуть объект, который ведет себя как Path
            return Path(x)
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)


    # 2. Мокаем os/shutil/PIL
    mock_shutil_copy = mocker.patch('src.image_processing.shutil.copy2')
    mock_image_open = mocker.patch('src.image_processing.Image.open', return_value=mock_pil_image)
    mock_image_new = mocker.patch('src.image_processing.Image.new', return_value=mock_pil_image) # Image.new тоже возвращает Image
    mocker.patch('src.image_processing.time.sleep') # Убираем задержку

    # 3. Настройка mock_utils
    def get_page_number_side_effect(filename):
        if "000" in filename: return 0
        if "001" in filename: return 1
        if "002" in filename: return 2
        if "003" in filename: return 3
        return -1 # Для ignored.txt и no_number.jpg
    mock_utils.get_page_number.side_effect = get_page_number_side_effect

    def is_likely_spread_side_effect(filepath_mock, threshold):
        # Сравниваем имя файла из мока
        # В этом тесте все страницы одиночные
        return False
    mock_utils.is_likely_spread.side_effect = is_likely_spread_side_effect

    # 4. Настройка mock_pil_image (для сценария склейки)
    # Пусть у 001 и 002 будут разные высоты для теста ресайза
    mock_img1 = MagicMock(spec=Image.Image)
    mock_img1.size = (800, 1200)
    mock_img1.resize.return_value = mock_img1
    mock_img1.convert.return_value = mock_img1
    mock_img1.__enter__ = MagicMock(return_value=mock_img1)
    mock_img1.__exit__ = MagicMock(return_value=None)

    mock_img2 = MagicMock(spec=Image.Image)
    mock_img2.size = (810, 1210) # Другая высота
    mock_img2.resize.return_value = mock_img2
    mock_img2.convert.return_value = mock_img2
    mock_img2.__enter__ = MagicMock(return_value=mock_img2)
    mock_img2.__exit__ = MagicMock(return_value=None)

    # Image.open будет возвращать разные моки для разных файлов
    def image_open_side_effect(filepath_arg):
        # filepath_arg может быть строкой или моком Path
        filepath_str = str(filepath_arg)
        if "001" in filepath_str: return mock_img1
        if "002" in filepath_str: return mock_img2
        return mock_pil_image # Для остальных
    mock_image_open.side_effect = image_open_side_effect

    # --- Вызов функции ---
    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    # --- Проверки ---
    # 1. Результат
    assert result == (4, 1) # 1 копия (обложка) + 2 склеены + 1 копия (последняя) = 4 обработано, 1 разворот создан

    # 2. Создание папки
    assert output_dir.exists()

    # 3. Вызовы get_page_number
    # Вызывается 5 раз в initial loop + 4 раза в main loop = 9
    assert mock_utils.get_page_number.call_count == 9 # ИСПРАВЛЕНО
    # Проверим несколько ключевых вызовов
    mock_utils.get_page_number.assert_any_call("000_cover.jpg")
    mock_utils.get_page_number.assert_any_call("001_page.png")
    mock_utils.get_page_number.assert_any_call("002_page.jpg")
    mock_utils.get_page_number.assert_any_call("003_single.jpeg")
    mock_utils.get_page_number.assert_any_call("no_number.jpg") # Вызывается в initial loop
    # ignored.txt не должен вызвать get_page_number, т.к. фильтруется по расширению раньше

    # 4. Вызовы is_likely_spread (только для страниц > 0)
    # Вызывается для 001 (как current), 002 (как next), 003 (как current)
    assert mock_utils.is_likely_spread.call_count == 3
    mock_utils.is_likely_spread.assert_any_call(mock_iterdir_results[1], mock_config.DEFAULT_ASPECT_RATIO_THRESHOLD) # 001_page.png
    mock_utils.is_likely_spread.assert_any_call(mock_iterdir_results[2], mock_config.DEFAULT_ASPECT_RATIO_THRESHOLD) # 002_page.jpg (проверяется как next)
    mock_utils.is_likely_spread.assert_any_call(mock_iterdir_results[3], mock_config.DEFAULT_ASPECT_RATIO_THRESHOLD) # 003_single.jpeg

    # 5. Вызовы shutil.copy2
    assert mock_shutil_copy.call_count == 2
    # Копирование обложки
    mock_shutil_copy.assert_any_call(
        mock_iterdir_results[0], # Мок для 000_cover.jpg
        output_dir / "spread_000.jpg"
    )
    # Копирование последней одиночной страницы
    mock_shutil_copy.assert_any_call(
        mock_iterdir_results[3], # Мок для 003_single.jpeg
        output_dir / "spread_003.jpeg"
    )

    # 6. Вызовы PIL для склейки 001 и 002
    assert mock_image_open.call_count == 2
    # Передаются моки Path
    mock_image_open.assert_any_call(mock_iterdir_results[1]) # 001_page.png
    mock_image_open.assert_any_call(mock_iterdir_results[2]) # 002_page.jpg

    # Проверка ресайза из-за разной высоты
    assert mock_img1.resize.call_count == 1
    assert mock_img2.resize.call_count == 1
    target_height = 1210 # max(1200, 1210)
    w1_final = int(800 * (target_height / 1200))
    w2_final = int(810 * (target_height / 1210)) # = 810
    mock_img1.resize.assert_called_with((w1_final, target_height), Image.Resampling.LANCZOS)
    mock_img2.resize.assert_called_with((w2_final, target_height), Image.Resampling.LANCZOS)

    # Проверка создания нового изображения
    mock_image_new.assert_called_once_with('RGB', (w1_final + w2_final, target_height), (255, 255, 255))

    # Проверка вставки
    assert mock_pil_image.paste.call_count == 2 # mock_pil_image - это то, что вернул mock_image_new
    mock_pil_image.paste.assert_any_call(mock_img1.convert('RGB'), (0, 0))
    mock_pil_image.paste.assert_any_call(mock_img2.convert('RGB'), (w1_final, 0))

    # Проверка сохранения
    mock_pil_image.save.assert_called_once_with(
        output_dir / "spread_001-002.jpg",
        "JPEG",
        quality=mock_config.JPEG_QUALITY,
        optimize=True
    )

    # 7. Вызовы колбэков
    mock_status_callback.assert_any_call(f"Начинаем обработку изображений из '{input_dir}' в '{output_dir}'...")
    mock_status_callback.assert_any_call("Найдено 4 файлов. Создание разворотов...") # 4 нумерованных файла
    mock_status_callback.assert_any_call("Копирую обложку: 000_cover.jpg -> spread_000.jpg")
    mock_status_callback.assert_any_call("Создаю разворот: 001_page.png + 002_page.jpg -> spread_001-002.jpg")
    mock_status_callback.assert_any_call("Копирую последнюю одиночную страницу: 003_single.jpeg -> spread_003.jpeg")
    mock_status_callback.assert_any_call("Обработка завершена. Обработано/скопировано: 4. Создано разворотов: 1.")

    assert mock_progress_callback.call_count == 4 # 0 + после обложки + после склейки + после последней
    mock_progress_callback.assert_has_calls([
        call(0, 4),   # Начальный вызов
        call(1, 4),   # После обложки (page_index = 1)
        call(3, 4),   # После склейки (page_index = 1 + 2 = 3)
        call(4, 4)    # После последней страницы (page_index = 3 + 1 = 4)
    ])

    # 8. Вызовы логгера (примеры)
    mock_logger.info.assert_any_call(f"Starting image processing. Input: '{mock_input_path}', Output: '{mock_output_path_obj}'") # Используем моки в строке
    mock_logger.warning.assert_any_call("Skipping file without page number: no_number.jpg")
    mock_logger.info.assert_any_call("Found 4 numbered image files to process.")
    mock_logger.info.assert_any_call("Copying cover: 000_cover.jpg -> spread_000.jpg")
    mock_logger.info.assert_any_call("Creating spread: 001_page.png + 002_page.jpg -> spread_001-002.jpg")
    mock_logger.debug.assert_any_call("    Resizing images to target height: 1210px (using LANCZOS)") # Проверка ресайза
    mock_logger.info.assert_any_call("    Spread created successfully: spread_001-002.jpg")
    mock_logger.info.assert_any_call("Copying last single page: 003_single.jpeg -> spread_003.jpeg")
    mock_logger.info.assert_any_call("Processing finished. Processed/copied: 4, Spreads created: 1")

    # 9. Stop event
    mock_stop_event.clear.assert_called_once()
    # Проверяем, что is_set вызывался в цикле (хотя и возвращал False)
    # Количество итераций = 3 (обложка, склейка, последняя)
    assert mock_stop_event.is_set.call_count == 3


def test_process_images_input_not_found(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event
):
    """Тест обработки ошибки: входная папка не найдена."""
    input_dir = tmp_path / "non_existent_input"
    output_dir = tmp_path / "output"

    # Мокаем Path так, чтобы iterdir вызывал FileNotFoundError для input_dir
    mock_input_path = MagicMock(spec=Path)
    mock_input_path.iterdir.side_effect = FileNotFoundError
    mock_input_path.__str__.return_value = str(input_dir) # Для сообщений об ошибках

    # Мокаем Path(output_dir), чтобы вернуть МОК с моком mkdir - ИСПРАВЛЕНО
    mock_output_path_obj = MagicMock(spec=Path)
    mock_output_path_obj.mkdir = MagicMock() # Мок метода mkdir
    mock_output_path_obj.__str__.return_value = str(output_dir) # Для сообщений

    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj # Возвращаем мок
        else:
            # Возвращаем мок и для output файлов, чтобы избежать реальных Path
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    mocker.patch('src.image_processing.time.sleep')

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    assert result == (0, 0)
    mock_status_callback.assert_any_call(f"Ошибка: Папка со страницами '{input_dir}' не найдена.")
    mock_logger.error.assert_called_with(f"Ошибка: Папка со страницами '{input_dir}' не найдена.")
    assert not mock_progress_callback.called # Не дошли до прогресса
    # Проверяем, что мок mkdir был вызван - ИСПРАВЛЕНО
    mock_output_path_obj.mkdir.assert_called_once_with(parents=True, exist_ok=True)


def test_process_images_output_creation_error(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event
):
    """Тест обработки ошибки: не удалось создать выходную папку."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir() # Входная папка существует

    # Мокаем mkdir для выходной папки, чтобы вызвать ошибку
    mock_output_path = MagicMock(spec=Path)
    mock_output_path.mkdir.side_effect = OSError("Permission denied")
    mock_output_path.__str__.return_value = str(output_dir) # Для сообщений

    # Мокаем Path так, чтобы он возвращал наш мок для output_dir
    mock_input_path_obj = Path(input_dir) # Используем реальный для input
    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path_obj # Реальный Path для input
        elif x_str == str(output_dir):
            return mock_output_path # Наш мок с ошибкой mkdir
        else:
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    mocker.patch('src.image_processing.time.sleep')

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    assert result == (0, 0)
    mock_status_callback.assert_any_call(f"Ошибка создания папки для разворотов '{output_dir}': Permission denied")
    mock_logger.error.assert_called_with(f"Ошибка создания папки для разворотов '{output_dir}': Permission denied", exc_info=True)
    assert not mock_progress_callback.called


def test_process_images_no_numbered_files(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event
):
    """Тест случая, когда в папке есть файлы, но нет нумерованных."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    mock_file_paths_real = [
        input_dir / "image.jpg",
        input_dir / "another.png",
        input_dir / "document.txt",
    ]
    mock_input_path, _ = create_mock_files(mocker, mock_file_paths_real)
    mock_output_path_obj = Path(output_dir) # Реальный для mkdir
    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    mock_utils.get_page_number.return_value = -1 # Все файлы без номеров
    mocker.patch('src.image_processing.time.sleep')

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    assert result == (0, 0)
    # Проверяем, что get_page_number вызывался для всех файлов изображений (2 шт)
    assert mock_utils.get_page_number.call_count == 2 # image.jpg, another.png
    mock_utils.get_page_number.assert_any_call("image.jpg")
    mock_utils.get_page_number.assert_any_call("another.png")
    # Проверяем финальное сообщение
    mock_status_callback.assert_any_call("В папке не найдено подходящих файлов изображений с номерами.")
    mock_logger.warning.assert_called_with(f"No processable image files found in {mock_input_path}")
    assert not mock_progress_callback.called # Не дошли до прогресса основного цикла


def test_process_images_stop_event_triggered(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event
):
    """Тест прерывания обработки по событию stop_event."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    mock_file_paths_real = [
        input_dir / "000_cover.jpg",
        input_dir / "001_page.png",
        input_dir / "002_page.jpg",
    ]
    mock_input_path, mock_iterdir_results = create_mock_files(mocker, mock_file_paths_real)
    mock_output_path_obj = Path(output_dir) # Реальный для mkdir
    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            # Мокаем и выходные пути
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            # Для shutil.copy2 нужен '/'
            mock_other.__truediv__ = lambda self, other: Path(str(self)) / other
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    mock_shutil_copy = mocker.patch('src.image_processing.shutil.copy2')
    mocker.patch('src.image_processing.time.sleep')

    # Настройка utils
    def get_page_number_side_effect(filename):
        if "000" in filename: return 0
        if "001" in filename: return 1
        if "002" in filename: return 2
        return -1
    mock_utils.get_page_number.side_effect = get_page_number_side_effect
    mock_utils.is_likely_spread.return_value = False # Все одиночные

    # --- Ключевой момент: stop_event сработает перед обработкой второго файла ---
    mock_stop_event.is_set.side_effect = [False, True] # Первый раз False (перед 000), второй раз True (перед 001)

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    # Ожидаем, что обработается только обложка (1 файл)
    assert result == (1, 0)

    # Проверяем, что был скопирован только первый файл
    assert mock_shutil_copy.call_count == 1
    # Путь назначения теперь тоже мок, проверяем его строковое представление
    expected_dest_path_str = str(output_dir / "spread_000.jpg")
    mock_shutil_copy.assert_called_once_with(
        mock_iterdir_results[0], # 000_cover.jpg
        ANY # Проверяем только первый аргумент точно, второй может быть моком
    )
    # Дополнительная проверка второго аргумента (если нужно)
    assert str(mock_shutil_copy.call_args[0][1]) == expected_dest_path_str


    # Проверяем вызовы stop_event
    mock_stop_event.clear.assert_called_once()
    assert mock_stop_event.is_set.call_count == 2 # Проверился перед 000 и перед 001

    # Проверяем сообщения
    mock_status_callback.assert_any_call("Копирую обложку: 000_cover.jpg -> spread_000.jpg")
    mock_status_callback.assert_any_call("--- Обработка прервана пользователем ---")
    # Проверяем, что финальное сообщение все равно было вызвано
    mock_status_callback.assert_any_call("Обработка завершена. Обработано/скопировано: 1. Создано разворотов: 0.")

    # Проверяем лог
    mock_logger.info.assert_any_call("Processing interrupted by user.")

    # Проверяем прогресс
    mock_progress_callback.assert_has_calls([
        call(0, 3), # Начальный
        call(1, 3)  # После обложки
    ])
    assert mock_progress_callback.call_count == 2


def test_process_images_copy_error(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event
):
    """Тест ошибки при копировании файла."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    mock_file_paths_real = [input_dir / "000_cover.jpg"]
    mock_input_path, mock_iterdir_results = create_mock_files(mocker, mock_file_paths_real)
    mock_output_path_obj = Path(output_dir) # Реальный для mkdir
    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            # Мокаем и выходные пути
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            mock_other.__truediv__ = lambda self, other: Path(str(self)) / other
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    # Мокаем copy2, чтобы вызвать ошибку
    mock_shutil_copy = mocker.patch('src.image_processing.shutil.copy2', side_effect=shutil.Error("Disk full"))
    mocker.patch('src.image_processing.time.sleep')

    mock_utils.get_page_number.return_value = 0

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    # Файл не скопирован, processed_increment остался 0
    assert result == (0, 0)

    mock_shutil_copy.assert_called_once() # Попытка была
    mock_status_callback.assert_any_call("Ошибка при копировании 000_cover.jpg: Disk full")
    mock_logger.error.assert_called_with("Ошибка при копировании 000_cover.jpg: Disk full", exc_info=True)
    # Прогресс обновился после попытки обработки
    mock_progress_callback.assert_called_with(1, 1) # page_index увеличился


def test_process_images_merge_error(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event, mock_pil_image
):
    """Тест ошибки при склейке изображений (например, при сохранении)."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    # ИСПРАВЛЕНО: Добавляем обложку, чтобы не попасть в if page_index == 0
    mock_file_paths_real = [
        input_dir / "000_cover.jpg",
        input_dir / "001_page.png",
        input_dir / "002_page.jpg",
    ]
    mock_input_path, mock_iterdir_results = create_mock_files(mocker, mock_file_paths_real)
    mock_output_path_obj = Path(output_dir) # Реальный для mkdir
    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            # Мокаем и выходные пути
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            mock_other.__truediv__ = lambda self, other: Path(str(self)) / other
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    mock_shutil_copy = mocker.patch('src.image_processing.shutil.copy2') # Мокаем копирование обложки
    mock_image_open = mocker.patch('src.image_processing.Image.open', return_value=mock_pil_image)
    mock_image_new = mocker.patch('src.image_processing.Image.new', return_value=mock_pil_image)
    # Мокаем save, чтобы вызвать ошибку
    mock_pil_image.save.side_effect = OSError("Cannot save file")
    mocker.patch('src.image_processing.time.sleep')

    # ИСПРАВЛЕНО: get_page_number теперь обрабатывает и 000
    mock_utils.get_page_number.side_effect = lambda f: 0 if "000" in f else (1 if "001" in f else (2 if "002" in f else -1))
    # ИСПРАВЛЕНО: is_likely_spread вызывается для 001 и 002
    mock_utils.is_likely_spread.return_value = False # Оба одиночные

    # Настройка mock_pil_image (одинаковые размеры для простоты)
    mock_pil_image.size = (800, 1200)
    mock_pil_image.resize.return_value = mock_pil_image
    mock_pil_image.convert.return_value = mock_pil_image

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    # Ожидаемый результат:
    # 1. Обложка скопирована (processed_increment = 1) -> processed_count = 1, page_index = 1
    # 2. Склейка 001+002 падает (processed_increment = 2 в except) -> processed_count = 1 + 2 = 3, page_index = 1 + 2 = 3
    # 3. Разворотов создано = 0
    assert result == (3, 0) # ИСПРАВЛЕНО

    # Проверяем, что обложка была скопирована
    mock_shutil_copy.assert_called_once_with(mock_iterdir_results[0], ANY)

    # Проверяем попытку сохранения
    mock_pil_image.save.assert_called_once()
    expected_save_path_str = str(output_dir / "spread_001-002.jpg")
    assert str(mock_pil_image.save.call_args[0][0]) == expected_save_path_str

    # Проверяем сообщения об ошибке
    mock_status_callback.assert_any_call("Ошибка при создании разворота для 001_page.png и 002_page.jpg: Cannot save file")
    mock_logger.error.assert_called_with("Ошибка при создании разворота для 001_page.png и 002_page.jpg: Cannot save file", exc_info=True)

    # Проверяем прогресс
    # total_files = 3
    mock_progress_callback.assert_has_calls([
        call(0, 3), # Начальный
        call(1, 3), # После обложки
        call(3, 3)  # После попытки склейки (page_index стал 3)
    ])
    assert mock_progress_callback.call_count == 3


def test_process_images_cover_followed_by_spread(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event
):
    """Тест сценария: обложка, за которой следует готовый разворот."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    mock_file_paths_real = [
        input_dir / "000_cover.jpg", # Обложка
        input_dir / "001_spread.jpg", # Готовый разворот
    ]
    mock_input_path, mock_iterdir_results = create_mock_files(mocker, mock_file_paths_real)
    mock_output_path_obj = Path(output_dir) # Реальный для mkdir
    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            # Мокаем и выходные пути
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            mock_other.__truediv__ = lambda self, other: Path(str(self)) / other
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    mock_shutil_copy = mocker.patch('src.image_processing.shutil.copy2')
    mocker.patch('src.image_processing.time.sleep')

    # Настройка utils
    mock_utils.get_page_number.side_effect = lambda f: 0 if "000" in f else (1 if "001" in f else -1)
    # 000 - не проверяется is_likely_spread, 001 - разворот
    mock_utils.is_likely_spread.side_effect = lambda f, t: "001" in f.name

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    # Оба файла скопированы
    assert result == (2, 0)

    # Проверяем вызовы is_likely_spread (только для файла 001)
    assert mock_utils.is_likely_spread.call_count == 1
    mock_utils.is_likely_spread.assert_called_once_with(mock_iterdir_results[1], mock_config.DEFAULT_ASPECT_RATIO_THRESHOLD)

    # Проверяем вызовы copy2
    assert mock_shutil_copy.call_count == 2
    expected_dest0_str = str(output_dir / "spread_000.jpg")
    expected_dest1_str = str(output_dir / "spread_001.jpg")
    mock_shutil_copy.assert_any_call(mock_iterdir_results[0], ANY)
    mock_shutil_copy.assert_any_call(mock_iterdir_results[1], ANY)
    # Проверяем пути назначения
    call_args_list = mock_shutil_copy.call_args_list
    assert str(call_args_list[0][0][1]) == expected_dest0_str
    assert str(call_args_list[1][0][1]) == expected_dest1_str


    # Проверяем сообщения
    mock_status_callback.assert_any_call("Копирую обложку: 000_cover.jpg -> spread_000.jpg")
    mock_status_callback.assert_any_call("Копирую готовый разворот: 001_spread.jpg -> spread_001.jpg")
    mock_status_callback.assert_any_call("Обработка завершена. Обработано/скопировано: 2. Создано разворотов: 0.")

    # Проверяем прогресс
    mock_progress_callback.assert_has_calls([
        call(0, 2), # Начальный
        call(1, 2), # После 000
        call(2, 2)  # После 001
    ])


# НОВЫЙ ТЕСТ для сценария 2.2
def test_process_images_single_page_before_spread(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event
):
    """Тест сценария: обложка, одиночная страница, затем разворот."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    mock_file_paths_real = [
        input_dir / "000_cover.jpg",   # Обложка
        input_dir / "001_single.png",  # Одиночная
        input_dir / "002_spread.jpg",  # Разворот
    ]
    mock_input_path, mock_iterdir_results = create_mock_files(mocker, mock_file_paths_real)
    mock_output_path_obj = Path(output_dir) # Реальный для mkdir
    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            # Мокаем и выходные пути
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            mock_other.__truediv__ = lambda self, other: Path(str(self)) / other
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    mock_shutil_copy = mocker.patch('src.image_processing.shutil.copy2')
    mocker.patch('src.image_processing.time.sleep')

    # Настройка utils
    mock_utils.get_page_number.side_effect = lambda f: 0 if "000" in f else (1 if "001" in f else (2 if "002" in f else -1))
    # 001 - одиночная, 002 - разворот
    def is_likely_spread_side_effect(file_mock, threshold):
        if "001" in file_mock.name:
            return False # Текущий файл (001) - одиночный
        if "002" in file_mock.name:
            return True # Следующий файл (002) - разворот ИЛИ Текущий файл (002) - разворот
        return False # По умолчанию
    mock_utils.is_likely_spread.side_effect = is_likely_spread_side_effect

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    # Все три файла скопированы
    assert result == (3, 0)

    # Проверяем вызовы is_likely_spread
    # Вызывается для 001 (как current) и 002 (как next и как current)
    assert mock_utils.is_likely_spread.call_count == 3
    mock_utils.is_likely_spread.assert_any_call(mock_iterdir_results[1], mock_config.DEFAULT_ASPECT_RATIO_THRESHOLD) # current 001
    mock_utils.is_likely_spread.assert_any_call(mock_iterdir_results[2], mock_config.DEFAULT_ASPECT_RATIO_THRESHOLD) # next 002
    mock_utils.is_likely_spread.assert_any_call(mock_iterdir_results[2], mock_config.DEFAULT_ASPECT_RATIO_THRESHOLD) # current 002

    # Проверяем вызовы copy2
    assert mock_shutil_copy.call_count == 3
    expected_dest0_str = str(output_dir / "spread_000.jpg")
    expected_dest1_str = str(output_dir / "spread_001.png")
    expected_dest2_str = str(output_dir / "spread_002.jpg")
    mock_shutil_copy.assert_any_call(mock_iterdir_results[0], ANY) # Обложка
    mock_shutil_copy.assert_any_call(mock_iterdir_results[1], ANY) # Одиночная перед разворотом
    mock_shutil_copy.assert_any_call(mock_iterdir_results[2], ANY) # Сам разворот
    # Проверяем пути назначения
    call_args_list = mock_shutil_copy.call_args_list
    # Порядок вызовов может быть не гарантирован, если использовать assert_any_call,
    # но в данном случае он должен быть последовательным. Проверим все три.
    dest_paths = {str(call[0][1]) for call in call_args_list}
    assert dest_paths == {expected_dest0_str, expected_dest1_str, expected_dest2_str}


    # Проверяем сообщения
    mock_status_callback.assert_any_call("Копирую обложку: 000_cover.jpg -> spread_000.jpg")
    mock_status_callback.assert_any_call("Копирую одиночную страницу (следующий - разворот): 001_single.png -> spread_001.png")
    mock_status_callback.assert_any_call("Копирую готовый разворот: 002_spread.jpg -> spread_002.jpg")
    mock_status_callback.assert_any_call("Обработка завершена. Обработано/скопировано: 3. Создано разворотов: 0.")

    # Проверяем прогресс
    mock_progress_callback.assert_has_calls([
        call(0, 3), # Начальный
        call(1, 3), # После 000
        call(2, 3), # После 001
        call(3, 3)  # После 002
    ])


# --- Тесты для покрытия оставшихся except блоков ---

def test_process_images_iterdir_os_error(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event
):
    """Тест обработки OSError при чтении входной папки."""
    input_dir = tmp_path / "input_permission_denied"
    output_dir = tmp_path / "output"
    # input_dir создавать не нужно, ошибка должна возникнуть при iterdir

    # Мокаем Path
    mock_input_path = MagicMock(spec=Path)
    mock_input_path.iterdir.side_effect = OSError("Permission denied reading directory")
    mock_input_path.__str__.return_value = str(input_dir)

    mock_output_path_obj = Path(output_dir) # Реальный для mkdir

    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            return Path(x)
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)
    mocker.patch('src.image_processing.time.sleep')

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    assert result == (0, 0)
    mock_status_callback.assert_any_call(f"Ошибка чтения папки '{input_dir}': Permission denied reading directory")
    mock_logger.error.assert_called_with(f"Ошибка чтения папки '{input_dir}': Permission denied reading directory", exc_info=True)
    assert not mock_progress_callback.called # Не дошли до прогресса


def test_process_images_copy_error_single_before_spread(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event
):
    """Тест ошибки копирования одиночной страницы перед разворотом (Вариант 2.2)."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    mock_file_paths_real = [
        input_dir / "000_cover.jpg",   # Обложка
        input_dir / "001_single.png",  # Одиночная (здесь будет ошибка копирования)
        input_dir / "002_spread.jpg",  # Разворот
    ]
    mock_input_path, mock_iterdir_results = create_mock_files(mocker, mock_file_paths_real)
    mock_output_path_obj = Path(output_dir) # Реальный для mkdir

    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            # Мокаем и выходные пути
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            mock_other.__truediv__ = lambda self, other: Path(str(self)) / other
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    # Мокаем shutil.copy2 с ошибкой на ВТОРОМ вызове
    copy_call_count = 0
    def copy2_side_effect(src, dst):
        nonlocal copy_call_count
        copy_call_count += 1
        if copy_call_count == 2: # Ошибка при копировании '001_single.png'
            raise shutil.Error("Copy failed for single before spread")
        # Первый вызов (обложка) и последующие (разворот) проходят успешно
        pass # В моке просто ничего не делаем для успешных вызовов

    mock_shutil_copy = mocker.patch('src.image_processing.shutil.copy2', side_effect=copy2_side_effect)
    mocker.patch('src.image_processing.time.sleep')

    # Настройка utils
    mock_utils.get_page_number.side_effect = lambda f: 0 if "000" in f else (1 if "001" in f else (2 if "002" in f else -1))
    mock_utils.is_likely_spread.side_effect = lambda f, t: "002" in f.name # 001 - single, 002 - spread

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    # Ожидаемый результат:
    # 1. Обложка скопирована (processed=1, index=1)
    # 2. Копирование 001 падает (processed=1, index=1+1=2)
    # 3. 002 копируется (processed=1+1=2, index=2+1=3)
    # Итого: (2, 0)
    assert result == (2, 0)

    # Проверяем вызовы copy2
    assert mock_shutil_copy.call_count == 3 # Попытка для 000, 001, 002

    # Проверяем сообщения об ошибке
    mock_status_callback.assert_any_call("Ошибка при копировании одиночной 001_single.png: Copy failed for single before spread")
    mock_logger.error.assert_called_with("Ошибка при копировании одиночной 001_single.png: Copy failed for single before spread", exc_info=True)

    # Проверяем прогресс
    mock_progress_callback.assert_has_calls([
        call(0, 3), # Начальный
        call(1, 3), # После 000
        call(2, 3), # После ошибки на 001 (page_index увеличился)
        call(3, 3)  # После 002
    ])


def test_process_images_copy_error_last_single(
    mocker, tmp_path, mock_config, mock_utils, mock_logger,
    mock_status_callback, mock_progress_callback, mock_stop_event, mock_pil_image
):
    """Тест ошибки копирования последней одиночной страницы (Вариант 2.3)."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    mock_file_paths_real = [
        input_dir / "000_cover.jpg",
        input_dir / "001_page.png",
        input_dir / "002_page.jpg",
        input_dir / "003_last_single.jpeg", # Здесь будет ошибка копирования
    ]
    mock_input_path, mock_iterdir_results = create_mock_files(mocker, mock_file_paths_real)
    mock_output_path_obj = Path(output_dir) # Реальный для mkdir

    def path_side_effect(x):
        x_str = str(x)
        if x_str == str(input_dir):
            return mock_input_path
        elif x_str == str(output_dir):
            return mock_output_path_obj
        else:
            # Мокаем и выходные пути
            mock_other = MagicMock(spec=Path)
            mock_other.__str__.return_value = x_str
            mock_other.__truediv__ = lambda self, other: Path(str(self)) / other
            return mock_other
    mocker.patch('src.image_processing.Path', side_effect=path_side_effect)

    # Мокаем shutil.copy2 с ошибкой на ВТОРОМ вызове
    copy_call_count = 0
    def copy2_side_effect(src, dst):
        nonlocal copy_call_count
        copy_call_count += 1
        if copy_call_count == 2: # Ошибка при копировании '003_last_single.jpeg'
            raise shutil.Error("Copy failed for last single")
        # Первый вызов (обложка) проходит успешно
        pass

    mock_shutil_copy = mocker.patch('src.image_processing.shutil.copy2', side_effect=copy2_side_effect)
    # Мокаем PIL для успешной склейки 001+002
    mocker.patch('src.image_processing.Image.open', return_value=mock_pil_image)
    mocker.patch('src.image_processing.Image.new', return_value=mock_pil_image)
    mocker.patch('src.image_processing.time.sleep')

    # Настройка utils
    mock_utils.get_page_number.side_effect = lambda f: 0 if "000" in f else (1 if "001" in f else (2 if "002" in f else (3 if "003" in f else -1)))
    mock_utils.is_likely_spread.return_value = False # Все одиночные

    # Настройка mock_pil_image для склейки
    mock_pil_image.size = (800, 1200)
    mock_pil_image.resize.return_value = mock_pil_image
    mock_pil_image.convert.return_value = mock_pil_image

    result = process_images_in_folders(
        str(input_dir), str(output_dir), mock_status_callback, mock_progress_callback,
        mock_stop_event, mock_config, mock_utils, mock_logger
    )

    # Ожидаемый результат:
    # 1. Обложка скопирована (processed=1, index=1)
    # 2. 001+002 склеены (processed=1+2=3, index=1+2=3, spreads=1)
    # 3. Копирование 003 падает (processed=3, index=3+1=4, spreads=1)
    # Итого: (3, 1)
    assert result == (3, 1)

    # Проверяем вызовы copy2
    assert mock_shutil_copy.call_count == 2 # Попытка для 000 и 003

    # Проверяем сообщения об ошибке
    mock_status_callback.assert_any_call("Ошибка при копировании последней одиночной 003_last_single.jpeg: Copy failed for last single")
    mock_logger.error.assert_called_with("Ошибка при копировании последней одиночной 003_last_single.jpeg: Copy failed for last single", exc_info=True)

    # Проверяем прогресс
    mock_progress_callback.assert_has_calls([
        call(0, 4), # Начальный
        call(1, 4), # После 000
        call(3, 4), # После склейки 001+002
        call(4, 4)  # После ошибки на 003 (page_index увеличился)
    ])
 