# tests/test_task_manager.py
import pytest
import threading
import time
from unittest.mock import MagicMock, call, ANY

# Импортируем класс для тестирования
from src.task_manager import TaskManager
# Импортируем зависимости, которые будем мокать (если они нужны для type hinting или isinstance)
# Обычно достаточно мокать их через mocker, но для ясности можно импортировать
# from src.app_state import AppState
# from src.logic import LibraryHandler

# Фикстура для мока зависимостей TaskManager
@pytest.fixture
def mock_deps(mocker):
    """Создает моки для всех зависимостей TaskManager."""
    mock_app_state = MagicMock(name="AppState")
    # Настраиваем моки для методов get() и get_total_pages_int()
    mock_app_state.url_base.get.return_value = "http://example.com/base/"
    mock_app_state.url_ids.get.return_value = "1,2,3"
    mock_app_state.pdf_filename.get.return_value = "doc.pdf"
    mock_app_state.pages_dir.get.return_value = "/path/to/pages"
    mock_app_state.spreads_dir.get.return_value = "/path/to/spreads"
    mock_app_state.get_total_pages_int.return_value = 10 # По умолчанию корректное значение

    mock_handler = MagicMock(name="LibraryHandler")
    # Настраиваем возвращаемые значения для методов handler
    # (success_count, total_pages)
    mock_handler.download_pages.return_value = (10, 10)
    # (processed_count, created_spread_count)
    mock_handler.process_images.return_value = (10, 5)

    mock_stop_event = MagicMock(spec=threading.Event, name="StopEvent")
    mock_stop_event.is_set.return_value = False # По умолчанию событие не установлено

    # Моки для колбэков
    mock_status_cb = MagicMock(name="StatusCallback")
    mock_progress_cb = MagicMock(name="ProgressCallback")
    mock_set_buttons_state_cb = MagicMock(name="SetButtonsStateCallback")
    mock_show_message_cb = MagicMock(name="ShowMessageCallback")
    mock_open_folder_cb = MagicMock(name="OpenFolderCallback")

    # Мок для root (Tkinter)
    mock_root = MagicMock(name="TkRoot")
    # Мокаем root.after, чтобы он сразу вызывал переданную функцию
    # Это упрощает тестирование асинхронных вызовов GUI из потока
    mock_root.after.side_effect = lambda ms, func: func()

    # Мокаем threading.Thread, чтобы не запускать реальные потоки
    mock_thread_class = mocker.patch('threading.Thread', autospec=True)
    # Сохраняем переданные target и args при создании потока
    thread_targets = {}
    def capture_target(*args, **kwargs):
        nonlocal thread_targets
        target = kwargs.get('target')
        target_args = kwargs.get('args', ())
        target_kwargs = kwargs.get('kwargs', {}) # Получаем kwargs для _thread_wrapper
        mock_thread_instance = MagicMock(name="ThreadInstance")
        mock_thread_instance.is_alive.return_value = True # Изначально поток "жив"
        thread_targets['instance'] = mock_thread_instance
        thread_targets['target'] = target
        thread_targets['args'] = target_args
        thread_targets['kwargs'] = target_kwargs # Сохраняем kwargs
        # Мок start(), чтобы ничего не делать, но позволить тесту вызвать target
        mock_thread_instance.start.side_effect = lambda: print(f"Mock Thread started for {target.__name__}")
        return mock_thread_instance

    mock_thread_class.side_effect = capture_target

    # Мокаем time.sleep, чтобы тесты не ждали
    mocker.patch('time.sleep', return_value=None)

    # Мокаем config для доступа к LOG_FILE в сообщениях
    mock_config = mocker.patch('src.task_manager.config')
    mock_config.LOG_FILE = "test_log.log"

    return {
        "app_state": mock_app_state,
        "handler": mock_handler,
        "stop_event": mock_stop_event,
        "status_cb": mock_status_cb,
        "progress_cb": mock_progress_cb,
        "set_buttons_state_cb": mock_set_buttons_state_cb,
        "show_message_cb": mock_show_message_cb,
        "open_folder_cb": mock_open_folder_cb,
        "root": mock_root,
        "thread_class": mock_thread_class,
        "thread_targets": thread_targets, # Для доступа к захваченным target/args
    }

# Фикстура для создания экземпляра TaskManager с моками
@pytest.fixture
def task_manager(mock_deps):
    """Создает экземпляр TaskManager с замоканными зависимостями."""
    tm = TaskManager(
        app_state=mock_deps["app_state"],
        handler=mock_deps["handler"],
        stop_event=mock_deps["stop_event"],
        status_callback=mock_deps["status_cb"],
        progress_callback=mock_deps["progress_cb"],
        set_buttons_state_callback=mock_deps["set_buttons_state_cb"],
        show_message_callback=mock_deps["show_message_cb"],
        open_folder_callback=mock_deps["open_folder_cb"],
        root=mock_deps["root"]
    )
    # Добавляем моки в экземпляр для удобства доступа в тестах
    tm._mocks = mock_deps
    return tm

# --- Тесты ---

def test_task_manager_initialization(task_manager, mock_deps):
    """Тест инициализации TaskManager."""
    assert task_manager.app_state == mock_deps["app_state"]
    assert task_manager.handler == mock_deps["handler"]
    assert task_manager.stop_event == mock_deps["stop_event"]
    assert task_manager.status_cb == mock_deps["status_cb"]
    # ... и т.д. для остальных колбэков и root
    assert not task_manager.is_running()
    assert task_manager.current_thread is None

def test_is_running(task_manager, mock_deps):
    """Тест метода is_running."""
    assert not task_manager.is_running()

    # Имитируем запуск потока
    task_manager.start_download() # Это создаст мок потока
    mock_thread_instance = mock_deps["thread_targets"]["instance"]
    task_manager.current_thread = mock_thread_instance # Устанавливаем мок как текущий

    assert task_manager.is_running()

    # Имитируем завершение потока
    mock_thread_instance.is_alive.return_value = False
    assert not task_manager.is_running()

    # Имитируем сброс потока после завершения в _thread_wrapper
    task_manager.current_thread = None
    assert not task_manager.is_running()

def test_start_task_when_already_running(task_manager, mock_deps):
    """Тест попытки запуска задачи, когда другая уже выполняется."""
    # Имитируем запущенный поток
    task_manager.current_thread = MagicMock(spec=threading.Thread)
    task_manager.current_thread.is_alive.return_value = True

    task_manager.start_download()

    # Проверяем, что новый поток не был создан
    mock_deps["thread_class"].assert_not_called()
    # Проверяем, что было показано сообщение об ошибке
    mock_deps["show_message_cb"].assert_called_once_with(
        'warning', "Занято", "Другая операция уже выполняется."
    )
    # Проверяем, что состояние кнопок не менялось
    mock_deps["set_buttons_state_cb"].assert_not_called()
    # Проверяем, что событие остановки не сбрасывалось
    mock_deps["stop_event"].clear.assert_not_called()

def test_start_download_success(task_manager, mock_deps):
    """Тест успешного запуска и выполнения скачивания."""
    # Ожидаемые аргументы для handler.download_pages
    expected_args = (
        "http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages"
    )
    # Настраиваем успешный результат для download_pages
    mock_deps["handler"].download_pages.return_value = (10, 10)

    task_manager.start_download()

    # 1. Проверка подготовки к запуску (_start_thread)
    mock_deps["stop_event"].clear.assert_called_once()
    mock_deps["set_buttons_state_cb"].assert_called_once_with(True) # Блокировка кнопок
    mock_deps["thread_class"].assert_called_once() # Проверяем, что Thread был создан

    # 2. Проверка аргументов, переданных в Thread
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"] # Получаем kwargs

    assert captured_target == task_manager._thread_wrapper
    assert captured_args[0] == mock_deps["handler"].download_pages # Целевая функция для wrapper
    assert captured_args[1:] == expected_args # Аргументы для download_pages
    assert captured_kwargs == {'task_name': 'Download'} # Проверяем task_name

    # 3. Имитация выполнения потока (вызов _thread_wrapper)
    # Запускаем захваченный target (_thread_wrapper) с его аргументами
    captured_target(*captured_args, **captured_kwargs)

    # 4. Проверка вызовов внутри _thread_wrapper (успешный сценарий download)
    mock_deps["handler"].download_pages.assert_called_once_with(*expected_args)
    mock_deps["status_cb"].assert_has_calls([
        call("--- Download: Задача завершена. ---"), # Сообщение из finally _thread_wrapper
        # Примечание: Сообщение об успехе скачивания передается в show_message_cb, а не status_cb
    ])
    mock_deps["show_message_cb"].assert_called_once_with(
        'info', "Успех", "Все страницы успешно скачаны!"
    )
    # Проверка вызова open_folder_cb через root.after
    # mock_deps["root"].after был настроен на немедленный вызов, поэтому проверяем сам колбэк
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/pages")

    # 5. Проверка действий в finally _thread_wrapper
    # set_buttons_state_cb(False) вызывается через root.after
    mock_deps["set_buttons_state_cb"].assert_has_calls([
        call(True), # При старте
        call(False) # В finally (через root.after)
    ])
    assert task_manager.current_thread is None # Поток сброшен

def test_start_download_partial_success(task_manager, mock_deps):
    """Тест запуска скачивания с частичным успехом."""
    expected_args = (
        "http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages"
    )
    # Настраиваем частичный результат
    mock_deps["handler"].download_pages.return_value = (7, 10)

    task_manager.start_download()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    captured_target(*captured_args, **captured_kwargs) # Имитируем выполнение

    mock_deps["handler"].download_pages.assert_called_once_with(*expected_args)
    mock_deps["show_message_cb"].assert_called_once_with(
        'warning', "Завершено с ошибками", "Скачано 7 из 10 страниц.\nПроверьте лог."
    )
    # Папка все равно должна открыться, если хоть что-то скачано
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/pages")
    mock_deps["status_cb"].assert_called_with("--- Download: Скачивание завершено. Успешно: 7 из 10. ---")
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_download_total_failure(task_manager, mock_deps):
    """Тест запуска скачивания с полным провалом (0 страниц)."""
    expected_args = (
        "http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages"
    )
    # Настраиваем результат 0 страниц
    mock_deps["handler"].download_pages.return_value = (0, 10)

    task_manager.start_download()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    captured_target(*captured_args, **captured_kwargs) # Имитируем выполнение

    mock_deps["handler"].download_pages.assert_called_once_with(*expected_args)
    mock_deps["show_message_cb"].assert_called_once_with(
        'error', "Ошибка", f"Не удалось скачать ни одной страницы.\nПроверьте параметры и лог ({mock_deps['config'].LOG_FILE})."
    )
    # Папка не должна открываться
    mock_deps["open_folder_cb"].assert_not_called()
    mock_deps["status_cb"].assert_called_with("--- Download: Скачивание завершено. Успешно: 0 из 10. ---")
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_download_invalid_pages(task_manager, mock_deps):
    """Тест запуска скачивания с некорректным количеством страниц."""
    mock_deps["app_state"].get_total_pages_int.return_value = None # Имитация ошибки валидации GUI

    task_manager.start_download()

    # Проверяем, что поток не стартовал
    mock_deps["thread_class"].assert_not_called()
    # Проверяем сообщение об ошибке
    mock_deps["show_message_cb"].assert_called_once_with(
        'error', "Ошибка", "Некорректное количество страниц."
    )
    # Кнопки не должны блокироваться
    mock_deps["set_buttons_state_cb"].assert_not_called()

def test_start_processing_success(task_manager, mock_deps):
    """Тест успешного запуска и выполнения обработки."""
    expected_args = ("/path/to/pages", "/path/to/spreads")
    mock_deps["handler"].process_images.return_value = (10, 5) # processed, created

    task_manager.start_processing()

    # 1. Проверка подготовки
    mock_deps["stop_event"].clear.assert_called_once()
    mock_deps["set_buttons_state_cb"].assert_called_once_with(True)
    mock_deps["thread_class"].assert_called_once()

    # 2. Проверка аргументов Thread
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    assert captured_target == task_manager._thread_wrapper
    assert captured_args[0] == mock_deps["handler"].process_images
    assert captured_args[1:] == expected_args
    assert captured_kwargs == {'task_name': 'Processing'}

    # 3. Имитация выполнения
    captured_target(*captured_args, **captured_kwargs)

    # 4. Проверка вызовов
    mock_deps["handler"].process_images.assert_called_once_with(*expected_args)
    final_msg = "Обработка завершена. Обработано/скопировано: 10. Создано разворотов: 5."
    mock_deps["show_message_cb"].assert_called_once_with(
        'info', "Успех", f"Создание разворотов завершено!\n{final_msg}"
    )
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/spreads")
    mock_deps["status_cb"].assert_called_with(f"--- Processing: {final_msg} ---")

    # 5. Проверка finally
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_processing_no_spreads_created(task_manager, mock_deps):
    """Тест обработки, когда развороты не созданы, но файлы обработаны."""
    expected_args = ("/path/to/pages", "/path/to/spreads")
    mock_deps["handler"].process_images.return_value = (10, 0) # processed, created

    task_manager.start_processing()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    captured_target(*captured_args, **captured_kwargs) # Имитируем выполнение

    mock_deps["handler"].process_images.assert_called_once_with(*expected_args)
    final_msg = "Обработка завершена. Обработано/скопировано: 10." # Без "Создано разворотов"
    mock_deps["show_message_cb"].assert_called_once_with(
        'info', "Успех", f"Создание разворотов завершено!\n{final_msg}"
    )
    # Папка все равно открывается, если что-то обработано
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/spreads")
    mock_deps["status_cb"].assert_called_with(f"--- Processing: {final_msg} ---")
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_thread_wrapper_exception(task_manager, mock_deps):
    """Тест обработки исключения внутри _thread_wrapper."""
    error_message = "Something went wrong!"
    mock_deps["handler"].download_pages.side_effect = Exception(error_message)

    task_manager.start_download() # Запускаем задачу, которая вызовет исключение

    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]

    # Вызов _thread_wrapper должен перехватить исключение
    captured_target(*captured_args, **captured_kwargs)

    # Проверяем, что было вызвано сообщение об ошибке
    mock_deps["show_message_cb"].assert_called_once_with(
        'error',
        "Критическая ошибка",
        f"Download: Критическая ошибка при выполнении: {error_message}\n\nПодробности в лог-файле:\n{mock_deps['config'].LOG_FILE}"
    )
    # Проверяем статусное сообщение об ошибке (вызывается *до* finally)
    mock_deps["status_cb"].assert_called_once_with(f"--- Download: Критическая ошибка при выполнении: {error_message} ---")

    # Проверяем, что папка не открывалась
    mock_deps["open_folder_cb"].assert_not_called()

    # Проверяем действия в finally
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_stop_task_when_running(task_manager, mock_deps):
    """Тест вызова stop_task во время выполнения задачи."""
    # Имитируем запущенный поток
    task_manager.start_download() # Создает мок потока
    mock_thread_instance = mock_deps["thread_targets"]["instance"]
    task_manager.current_thread = mock_thread_instance

    assert task_manager.is_running()

    task_manager.stop_task()

    # Проверяем, что событие было установлено
    mock_deps["stop_event"].set.assert_called_once()
    # Проверяем, что статус обновлен
    mock_deps["status_cb"].assert_called_once_with("--- Получен сигнал СТОП от пользователя ---")

def test_stop_task_when_not_running(task_manager, mock_deps):
    """Тест вызова stop_task, когда нет активной задачи."""
    assert not task_manager.is_running()

    task_manager.stop_task()

    # Проверяем, что событие НЕ было установлено
    mock_deps["stop_event"].set.assert_not_called()
    # Проверяем, что статус НЕ обновлялся
    mock_deps["status_cb"].assert_not_called()

def test_thread_wrapper_stopped_before_finish(task_manager, mock_deps):
    """Тест сценария, когда задача остановлена до ее завершения."""
    expected_args = (
        "http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages"
    )
    # Настраиваем успешный результат, но он не должен использоваться для сообщений
    mock_deps["handler"].download_pages.return_value = (10, 10)

    task_manager.start_download()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]

    # Имитируем установку события СТОП *перед* вызовом finally в _thread_wrapper
    mock_deps["stop_event"].is_set.return_value = True

    # Имитируем выполнение
    captured_target(*captured_args, **captured_kwargs)

    # Проверяем, что handler был вызван (остановка происходит после)
    mock_deps["handler"].download_pages.assert_called_once_with(*expected_args)

    # Проверяем, что финальное сообщение в status_cb НЕ было вызвано
    # mock_deps["status_cb"] мог быть вызван ранее (например, при вызове stop_task),
    # поэтому проверяем отсутствие *финального* сообщения
    for call_args in mock_deps["status_cb"].call_args_list:
        assert "Задача завершена" not in call_args[0][0]
        assert "Скачивание завершено" not in call_args[0][0]

    # Проверяем, что show_message_cb НЕ вызывался
    mock_deps["show_message_cb"].assert_not_called()
    # Проверяем, что open_folder_cb НЕ вызывался
    mock_deps["open_folder_cb"].assert_not_called()

    # Проверяем действия в finally (они должны выполниться)
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

# --- Тесты для start_all и _run_all_sequence ---

@pytest.fixture
def setup_start_all(task_manager, mock_deps):
    """Настройка для тестов start_all."""
    # Ожидаемые аргументы для _run_all_sequence
    expected_args = (
        "http://example.com/base/", "1,2,3", "doc.pdf", 10,
        "/path/to/pages", "/path/to/spreads"
    )
    task_manager.start_all()

    # Проверка подготовки (_start_thread)
    mock_deps["stop_event"].clear.assert_called_once()
    mock_deps["set_buttons_state_cb"].assert_called_once_with(True)
    mock_deps["thread_class"].assert_called_once()

    # Проверка аргументов Thread
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    assert captured_target == task_manager._thread_wrapper
    assert captured_args[0] == task_manager._run_all_sequence # Целевая функция
    assert captured_args[1:] == expected_args # Аргументы для _run_all_sequence
    assert captured_kwargs == {'task_name': 'Download & Process'}

    # Возвращаем захваченные элементы для имитации выполнения
    return captured_target, captured_args, captured_kwargs

def test_start_all_full_success(task_manager, mock_deps, setup_start_all):
    """Тест успешного выполнения start_all (скачивание + обработка)."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all

    # Настраиваем успешные результаты для обоих этапов
    mock_deps["handler"].download_pages.return_value = (10, 10)
    mock_deps["handler"].process_images.return_value = (10, 5)

    # Имитируем выполнение _thread_wrapper -> _run_all_sequence
    wrapper_target(*wrapper_args, **wrapper_kwargs)

    # Проверка вызовов handler
    mock_deps["handler"].download_pages.assert_called_once_with(
        "http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages"
    )
    mock_deps["handler"].process_images.assert_called_once_with(
        "/path/to/pages", "/path/to/spreads"
    )

    # Проверка статусных сообщений из _run_all_sequence
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание успешно завершено (10/10) ---"),
        call("--- НАЧАЛО: Создание разворотов ---"),
        call("--- Download & Process: Скачивание (10/10) и обработка (10 файлов, 5 разворотов) завершены. ---")
    ], any_order=False) # Проверяем порядок

    # Проверка финального сообщения show_message_cb из _run_all_sequence
    mock_deps["show_message_cb"].assert_called_once_with(
        'info', "Завершено", "Скачивание (10/10) и обработка (10 файлов, 5 разворотов) завершены."
    )

    # Проверка открытия папки (должна быть папка разворотов)
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/spreads")

    # Проверка finally из _thread_wrapper
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_download_fails_zero_pages(task_manager, mock_deps, setup_start_all):
    """Тест start_all, когда скачивание завершается с 0 страниц."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all

    # Настраиваем провал скачивания
    mock_deps["handler"].download_pages.return_value = (0, 10)

    # Имитируем выполнение
    wrapper_target(*wrapper_args, **wrapper_kwargs)

    # Проверка вызовов handler
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_not_called() # Обработка не должна запускаться

    # Проверка статусных сообщений
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание не удалось (0 страниц), обработка пропущена ---")
    ], any_order=False)

    # Проверка сообщения об ошибке
    mock_deps["show_message_cb"].assert_called_once_with(
        'error', "Ошибка скачивания", f"Не удалось скачать ни одной страницы.\nОбработка не будет запущена.\nПроверьте лог ({mock_deps['config'].LOG_FILE})."
    )

    # Папка не открывается
    mock_deps["open_folder_cb"].assert_not_called()

    # Проверка finally из _thread_wrapper
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_download_partial_then_process(task_manager, mock_deps, setup_start_all):
    """Тест start_all: частичное скачивание, затем успешная обработка."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all

    # Настраиваем частичный успех скачивания и успех обработки
    mock_deps["handler"].download_pages.return_value = (7, 10)
    mock_deps["handler"].process_images.return_value = (7, 4) # Обработано 7, создано 4

    # Имитируем выполнение
    wrapper_target(*wrapper_args, **wrapper_kwargs)

    # Проверка вызовов handler
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_called_once()

    # Проверка статусных сообщений
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание завершено с ошибками (7/10). Продолжаем обработку скачанных... ---"),
        call("--- НАЧАЛО: Создание разворотов ---"),
        call("--- Download & Process: Скачивание (7/10) и обработка (7 файлов, 4 разворотов) завершены. ---")
    ], any_order=False)

    # Проверка сообщений пользователю (предупреждение о скачивании + финальное инфо)
    mock_deps["show_message_cb"].assert_has_calls([
        call('warning', "Скачивание с ошибками", "Скачано 7 из 10 страниц.\nОбработка будет запущена для скачанных файлов."),
        call('info', "Завершено", "Скачивание (7/10) и обработка (7 файлов, 4 разворотов) завершены.")
    ], any_order=False)

    # Папка разворотов открывается
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/spreads")

    # Проверка finally
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_stopped_during_download(task_manager, mock_deps, setup_start_all):
    """Тест start_all, когда приходит сигнал СТОП во время скачивания."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all

    # Настраиваем, чтобы download_pages вернул что-то, но потом проверился stop_event
    mock_deps["handler"].download_pages.return_value = (5, 10)

    # Имитируем установку stop_event *после* вызова download_pages, но *до* проверки
    def download_and_stop(*args, **kwargs):
        mock_deps["stop_event"].is_set.return_value = True # Устанавливаем флаг
        return (5, 10) # Возвращаем результат
    mock_deps["handler"].download_pages.side_effect = download_and_stop

    # Имитируем выполнение
    wrapper_target(*wrapper_args, **wrapper_kwargs)

    # Проверка вызовов handler
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_not_called() # Обработка не должна запускаться

    # Проверка статусных сообщений
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание прервано, обработка отменена ---") # Сообщение об остановке
    ], any_order=False)

    # Сообщения пользователю и открытие папки не должны вызываться после остановки
    mock_deps["show_message_cb"].assert_not_called()
    mock_deps["open_folder_cb"].assert_not_called()

    # Проверка finally из _thread_wrapper
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_stopped_during_processing(task_manager, mock_deps, setup_start_all):
    """Тест start_all, когда приходит сигнал СТОП во время обработки."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all

    # Скачивание успешно
    mock_deps["handler"].download_pages.return_value = (10, 10)
    # Настраиваем, чтобы process_images вернул что-то, но потом проверился stop_event
    def process_and_stop(*args, **kwargs):
        mock_deps["stop_event"].is_set.return_value = True # Устанавливаем флаг
        return (5, 2) # Возвращаем результат
    mock_deps["handler"].process_images.side_effect = process_and_stop

    # Имитируем выполнение
    wrapper_target(*wrapper_args, **wrapper_kwargs)

    # Проверка вызовов handler
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_called_once()

    # Проверка статусных сообщений
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание успешно завершено (10/10) ---"),
        call("--- НАЧАЛО: Создание разворотов ---"),
        call("--- Обработка прервана ---") # Сообщение об остановке на этапе обработки
    ], any_order=False)

    # Сообщения пользователю и открытие папки не должны вызываться после остановки
    mock_deps["show_message_cb"].assert_not_called()
    mock_deps["open_folder_cb"].assert_not_called()

    # Проверка finally из _thread_wrapper
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_exception_during_download(task_manager, mock_deps, setup_start_all):
    """Тест start_all с исключением во время скачивания."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all
    error_message = "Download failed badly"
    mock_deps["handler"].download_pages.side_effect = Exception(error_message)

    # Имитируем выполнение _thread_wrapper -> _run_all_sequence
    wrapper_target(*wrapper_args, **wrapper_kwargs)

    # Проверка вызовов handler
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_not_called()

    # Проверка сообщения об ошибке (вызывается из _run_all_sequence catch block)
    # Ожидаем, что 's' будет заменено на 'скачивания'
    mock_deps["show_message_cb"].assert_called_once_with(
        'error',
        "Критическая ошибка",
        f"Ошибка на этапе скачивания:\nDownload & Process: Критическая ошибка: {error_message}\n\nПодробности в лог-файле:\n{mock_deps['config'].LOG_FILE}"
    )

    # Статусное сообщение из finally _thread_wrapper должно содержать ошибку
    mock_deps["status_cb"].assert_called_with(f"--- Download & Process: Критическая ошибка при выполнении: Ошибка на этапе скачивания:\nDownload & Process: Критическая ошибка: {error_message}\n\nПодробности в лог-файле:\n{mock_deps['config'].LOG_FILE} ---")


    # Папка не открывается
    mock_deps["open_folder_cb"].assert_not_called()

    # Проверка finally из _thread_wrapper
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None


def test_start_all_exception_during_processing(task_manager, mock_deps, setup_start_all):
    """Тест start_all с исключением во время обработки."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all
    error_message = "Processing failed badly"
    # Скачивание успешно
    mock_deps["handler"].download_pages.return_value = (10, 10)
    # Обработка падает
    mock_deps["handler"].process_images.side_effect = Exception(error_message)

    # Имитируем выполнение
    wrapper_target(*wrapper_args, **wrapper_kwargs)

    # Проверка вызовов handler
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_called_once()

    # Проверка сообщения об ошибке (вызывается из _run_all_sequence catch block)
    # Ожидаем, что 's' будет заменено на 'обработки'
    mock_deps["show_message_cb"].assert_called_once_with(
        'error',
        "Критическая ошибка",
        f"Ошибка на этапе обработки:\nDownload & Process: Критическая ошибка: {error_message}\n\nПодробности в лог-файле:\n{mock_deps['config'].LOG_FILE}"
    )

     # Статусное сообщение из finally _thread_wrapper должно содержать ошибку
    mock_deps["status_cb"].assert_called_with(f"--- Download & Process: Критическая ошибка при выполнении: Ошибка на этапе обработки:\nDownload & Process: Критическая ошибка: {error_message}\n\nПодробности в лог-файле:\n{mock_deps['config'].LOG_FILE} ---")


    # Папка не открывается
    mock_deps["open_folder_cb"].assert_not_called()

    # Проверка finally из _thread_wrapper
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_invalid_pages(task_manager, mock_deps):
    """Тест запуска start_all с некорректным количеством страниц."""
    mock_deps["app_state"].get_total_pages_int.return_value = None # Имитация ошибки валидации GUI

    task_manager.start_all()

    # Проверяем, что поток не стартовал
    mock_deps["thread_class"].assert_not_called()
    # Проверяем сообщение об ошибке
    mock_deps["show_message_cb"].assert_called_once_with(
        'error', "Ошибка", "Некорректное количество страниц."
    )
    # Кнопки не должны блокироваться
    mock_deps["set_buttons_state_cb"].assert_not_called()