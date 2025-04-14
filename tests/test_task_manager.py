# tests/test_task_manager.py
import pytest
import threading
import time
from unittest.mock import MagicMock, call, ANY, patch

# Импортируем класс для тестирования
from src.task_manager import TaskManager
import threading

# Константа для ожидаемого имени лог-файла в тестах
EXPECTED_MOCKED_LOG_FILE = "test_log.log"

# Фикстура для мока зависимостей TaskManager
@pytest.fixture
def mock_deps(mocker):
    """Создает моки для всех зависимостей TaskManager."""
    mock_app_state = MagicMock(name="AppState")
    mock_app_state.url_base.get.return_value = "http://example.com/base/"
    mock_app_state.url_ids.get.return_value = "1,2,3"
    mock_app_state.pdf_filename.get.return_value = "doc.pdf"
    mock_app_state.pages_dir.get.return_value = "/path/to/pages"
    mock_app_state.spreads_dir.get.return_value = "/path/to/spreads"
    mock_app_state.get_total_pages_int.return_value = 10

    mock_handler = MagicMock(name="LibraryHandler")
    mock_handler.download_pages.return_value = (10, 10)
    mock_handler.process_images.return_value = (10, 5)

    mock_stop_event = MagicMock(spec=threading.Event, name="StopEvent")
    mock_stop_event.is_set.return_value = False

    mock_status_cb = MagicMock(name="StatusCallback")
    mock_progress_cb = MagicMock(name="ProgressCallback")
    mock_set_buttons_state_cb = MagicMock(name="SetButtonsStateCallback")
    mock_show_message_cb = MagicMock(name="ShowMessageCallback")
    mock_open_folder_cb = MagicMock(name="OpenFolderCallback")

    mock_root = MagicMock(name="TkRoot")
    mock_root.after.side_effect = lambda ms, func: func()

    # Мокаем threading.Thread
    patcher_thread = patch('src.task_manager.threading.Thread', autospec=True)
    mock_thread_class = patcher_thread.start()
    thread_targets = {}
    def capture_target(*args, **kwargs):
        nonlocal thread_targets
        target = kwargs.get('target')
        target_args = kwargs.get('args', ())
        target_kwargs = kwargs.get('kwargs', {})
        mock_thread_instance = MagicMock(name="ThreadInstance")
        mock_thread_instance.is_alive.return_value = True
        thread_targets['instance'] = mock_thread_instance
        thread_targets['target'] = target
        thread_targets['args'] = target_args
        thread_targets['kwargs'] = target_kwargs
        mock_thread_instance.start.side_effect = lambda: print(f"Mock Thread started for {target.__name__ if hasattr(target, '__name__') else repr(target)}")
        return mock_thread_instance
    mock_thread_class.side_effect = capture_target

    # Мокаем time.sleep
    mocker.patch('src.task_manager.time.sleep', return_value=None)

    # FIX: Мокаем напрямую атрибут LOG_FILE в модуле config,
    # как он используется в src.task_manager
    patcher_config_log = mocker.patch('src.task_manager.config.LOG_FILE', EXPECTED_MOCKED_LOG_FILE)

    deps = {
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
        "thread_targets": thread_targets,
        # "config" больше не нужен в deps для тестов ниже, т.к. используем константу
    }
    yield deps

    patcher_thread.stop()
    # mocker сам остановит patcher_config_log для function scope

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
    tm._mocks = mock_deps
    return tm

# --- Тесты ---

# ... (Тесты, которые уже проходили, остаются без изменений) ...

def test_task_manager_initialization(task_manager, mock_deps):
    """Тест инициализации TaskManager."""
    assert task_manager.app_state == mock_deps["app_state"]
    assert task_manager.handler == mock_deps["handler"]
    assert task_manager.stop_event == mock_deps["stop_event"]
    assert task_manager.status_cb == mock_deps["status_cb"]
    assert not task_manager.is_running()
    assert task_manager.current_thread is None

def test_is_running(task_manager, mock_deps):
    """Тест метода is_running."""
    assert not task_manager.is_running()
    task_manager.start_download()
    assert "instance" in mock_deps["thread_targets"]
    mock_thread_instance = mock_deps["thread_targets"]["instance"]
    task_manager.current_thread = mock_thread_instance
    assert task_manager.is_running()
    mock_thread_instance.is_alive.return_value = False
    assert not task_manager.is_running()
    task_manager.current_thread = None
    assert not task_manager.is_running()

def test_start_task_when_already_running(task_manager, mock_deps):
    """Тест попытки запуска задачи, когда другая уже выполняется."""
    task_manager.current_thread = MagicMock(name="RunningThreadInstance")
    task_manager.current_thread.is_alive.return_value = True
    task_manager.start_download()
    mock_deps["thread_class"].assert_not_called()
    mock_deps["show_message_cb"].assert_called_once_with(
        'warning', "Занято", "Другая операция уже выполняется."
    )
    mock_deps["set_buttons_state_cb"].assert_not_called()
    mock_deps["stop_event"].clear.assert_not_called()

def test_start_download_success(task_manager, mock_deps):
    """Тест успешного запуска и выполнения скачивания."""
    expected_args = ("http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages")
    mock_deps["handler"].download_pages.return_value = (10, 10)
    task_manager.start_download()
    mock_deps["stop_event"].clear.assert_called_once()
    mock_deps["set_buttons_state_cb"].assert_called_once_with(True)
    mock_deps["thread_class"].assert_called_once()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    assert captured_target == task_manager._thread_wrapper
    assert captured_args[0] == mock_deps["handler"].download_pages
    assert captured_args[1:] == expected_args
    assert captured_kwargs == {'task_name': 'Download'}
    captured_target(*captured_args, **captured_kwargs)
    mock_deps["handler"].download_pages.assert_called_once_with(*expected_args)
    expected_final_message = "Скачивание завершено. Успешно: 10 из 10."
    mock_deps["status_cb"].assert_called_once_with(f"--- {expected_final_message} ---")
    mock_deps["show_message_cb"].assert_called_once_with('info', "Успех", "Все страницы успешно скачаны!")
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/pages")
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_download_partial_success(task_manager, mock_deps):
    """Тест запуска скачивания с частичным успехом."""
    expected_args = ("http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages")
    mock_deps["handler"].download_pages.return_value = (7, 10)
    task_manager.start_download()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    captured_target(*captured_args, **captured_kwargs)
    mock_deps["handler"].download_pages.assert_called_once_with(*expected_args)
    mock_deps["show_message_cb"].assert_called_once_with('warning', "Завершено с ошибками", "Скачано 7 из 10 страниц.\nПроверьте лог.")
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/pages")
    expected_final_message = "Скачивание завершено. Успешно: 7 из 10."
    mock_deps["status_cb"].assert_called_once_with(f"--- {expected_final_message} ---")
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_download_total_failure(task_manager, mock_deps):
    """Тест запуска скачивания с полным провалом (0 страниц)."""
    expected_args = (
        "http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages"
    )
    mock_deps["handler"].download_pages.return_value = (0, 10)

    task_manager.start_download()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    captured_target(*captured_args, **captured_kwargs)

    mock_deps["handler"].download_pages.assert_called_once_with(*expected_args)

    # FIX: Используем константу EXPECTED_MOCKED_LOG_FILE
    mock_deps["show_message_cb"].assert_called_once_with(
        'error', "Ошибка", f"Не удалось скачать ни одной страницы.\nПроверьте параметры и лог ({EXPECTED_MOCKED_LOG_FILE})."
    )
    mock_deps["open_folder_cb"].assert_not_called()

    expected_final_message = "Скачивание завершено. Успешно: 0 из 10."
    mock_deps["status_cb"].assert_called_once_with(f"--- {expected_final_message} ---")

    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_download_invalid_pages(task_manager, mock_deps):
    """Тест запуска скачивания с некорректным количеством страниц."""
    mock_deps["app_state"].get_total_pages_int.return_value = None
    task_manager.start_download()
    mock_deps["thread_class"].assert_not_called()
    mock_deps["show_message_cb"].assert_called_once_with('error', "Ошибка", "Некорректное количество страниц.")
    mock_deps["set_buttons_state_cb"].assert_not_called()

def test_start_processing_success(task_manager, mock_deps):
    """Тест успешного запуска и выполнения обработки."""
    expected_args = ("/path/to/pages", "/path/to/spreads")
    mock_deps["handler"].process_images.return_value = (10, 5)
    task_manager.start_processing()
    mock_deps["stop_event"].clear.assert_called_once()
    mock_deps["set_buttons_state_cb"].assert_called_once_with(True)
    mock_deps["thread_class"].assert_called_once()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    assert captured_target == task_manager._thread_wrapper
    assert captured_args[0] == mock_deps["handler"].process_images
    assert captured_args[1:] == expected_args
    assert captured_kwargs == {'task_name': 'Processing'}
    captured_target(*captured_args, **captured_kwargs)
    mock_deps["handler"].process_images.assert_called_once_with(*expected_args)
    final_msg_from_code = "Обработка завершена. Обработано/скопировано: 10. Создано разворотов: 5."
    mock_deps["show_message_cb"].assert_called_once_with('info', "Успех", f"Создание разворотов завершено!\n{final_msg_from_code}")
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/spreads")
    mock_deps["status_cb"].assert_called_once_with(f"--- {final_msg_from_code} ---")
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_processing_no_spreads_created(task_manager, mock_deps):
    """Тест обработки, когда развороты не созданы, но файлы обработаны."""
    expected_args = ("/path/to/pages", "/path/to/spreads")
    mock_deps["handler"].process_images.return_value = (10, 0)
    task_manager.start_processing()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    captured_target(*captured_args, **captured_kwargs)
    mock_deps["handler"].process_images.assert_called_once_with(*expected_args)
    final_msg_from_code = "Обработка завершена. Обработано/скопировано: 10."
    mock_deps["show_message_cb"].assert_called_once_with('info', "Успех", f"Создание разворотов завершено!\n{final_msg_from_code}")
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/spreads")
    mock_deps["status_cb"].assert_called_once_with(f"--- {final_msg_from_code} ---")
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_thread_wrapper_exception(task_manager, mock_deps):
    """Тест обработки исключения внутри _thread_wrapper."""
    error_message = "Something went wrong!"
    task_name = "Download"
    mock_deps["handler"].download_pages.side_effect = Exception(error_message)

    task_manager.start_download()

    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]

    captured_target(*captured_args, **captured_kwargs)

    expected_error_msg_detail = f"{task_name}: Критическая ошибка при выполнении: {error_message}"
    # FIX: Используем константу EXPECTED_MOCKED_LOG_FILE
    mock_deps["show_message_cb"].assert_called_once_with(
        'error',
        "Критическая ошибка",
        f"{expected_error_msg_detail}\n\nПодробности в лог-файле:\n{EXPECTED_MOCKED_LOG_FILE}"
    )
    mock_deps["status_cb"].assert_called_once_with(f"--- {expected_error_msg_detail} ---")
    mock_deps["open_folder_cb"].assert_not_called()
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_stop_task_when_running(task_manager, mock_deps):
    """Тест вызова stop_task во время выполнения задачи."""
    task_manager.start_download()
    assert "instance" in mock_deps["thread_targets"]
    mock_thread_instance = mock_deps["thread_targets"]["instance"]
    task_manager.current_thread = mock_thread_instance
    assert task_manager.is_running()
    task_manager.stop_task()
    mock_deps["stop_event"].set.assert_called_once()
    mock_deps["status_cb"].assert_called_once_with("--- Получен сигнал СТОП от пользователя ---")

def test_stop_task_when_not_running(task_manager, mock_deps):
    """Тест вызова stop_task, когда нет активной задачи."""
    assert not task_manager.is_running()
    task_manager.stop_task()
    mock_deps["stop_event"].set.assert_not_called()
    mock_deps["status_cb"].assert_not_called()

def test_thread_wrapper_stopped_before_finish(task_manager, mock_deps):
    """Тест сценария, когда задача остановлена до ее завершения."""
    expected_args = ("http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages")
    mock_deps["handler"].download_pages.return_value = (10, 10)
    task_manager.start_download()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    mock_deps["stop_event"].is_set.return_value = True
    captured_target(*captured_args, **captured_kwargs)
    mock_deps["handler"].download_pages.assert_called_once_with(*expected_args)
    for call_arg in mock_deps["status_cb"].call_args_list:
        assert "Скачивание завершено" not in call_arg.args[0]
        assert "Задача завершена" not in call_arg.args[0]
    mock_deps["show_message_cb"].assert_not_called()
    mock_deps["open_folder_cb"].assert_not_called()
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

# --- Тесты для start_all и _run_all_sequence ---

@pytest.fixture
def setup_start_all(task_manager, mock_deps):
    """Настройка для тестов start_all."""
    expected_args = ("http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages", "/path/to/spreads")
    task_manager.start_all()
    mock_deps["stop_event"].clear.assert_called_once()
    mock_deps["set_buttons_state_cb"].assert_called_once_with(True)
    mock_deps["thread_class"].assert_called_once()
    captured_target = mock_deps["thread_targets"]["target"]
    captured_args = mock_deps["thread_targets"]["args"]
    captured_kwargs = mock_deps["thread_targets"]["kwargs"]
    assert captured_target == task_manager._thread_wrapper
    assert captured_args[0] == task_manager._run_all_sequence
    assert captured_args[1:] == expected_args
    assert captured_kwargs == {'task_name': 'Download & Process'}
    return captured_target, captured_args, captured_kwargs

def test_start_all_full_success(task_manager, mock_deps, setup_start_all):
    """Тест успешного выполнения start_all (скачивание + обработка)."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all
    task_name = wrapper_kwargs['task_name']
    mock_deps["handler"].download_pages.return_value = (10, 10)
    mock_deps["handler"].process_images.return_value = (10, 5)
    wrapper_target(*wrapper_args, **wrapper_kwargs)
    mock_deps["handler"].download_pages.assert_called_once_with("http://example.com/base/", "1,2,3", "doc.pdf", 10, "/path/to/pages")
    mock_deps["handler"].process_images.assert_called_once_with("/path/to/pages", "/path/to/spreads")
    final_msg_sequence = "Скачивание (10/10) и обработка (10 файлов, 5 разворотов) завершены."
    final_msg_wrapper = f"{task_name}: Задача завершена."
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание успешно завершено (10/10) ---"),
        call("--- НАЧАЛО: Создание разворотов ---"),
        call(f"--- {final_msg_sequence} ---"),
        call(f"--- {final_msg_wrapper} ---")
    ], any_order=False)
    mock_deps["show_message_cb"].assert_called_once_with('info', "Завершено", final_msg_sequence)
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/spreads")
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_download_fails_zero_pages(task_manager, mock_deps, setup_start_all):
    """Тест start_all, когда скачивание завершается с 0 страниц."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all
    task_name = wrapper_kwargs['task_name']
    mock_deps["handler"].download_pages.return_value = (0, 10)
    wrapper_target(*wrapper_args, **wrapper_kwargs)
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_not_called()
    final_msg_wrapper = f"{task_name}: Задача завершена."
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание не удалось (0 страниц), обработка пропущена ---"),
        call(f"--- {final_msg_wrapper} ---")
    ], any_order=False)

    # FIX: Используем константу EXPECTED_MOCKED_LOG_FILE
    mock_deps["show_message_cb"].assert_called_once_with(
        'error', "Ошибка скачивания", f"Не удалось скачать ни одной страницы.\nОбработка не будет запущена.\nПроверьте лог ({EXPECTED_MOCKED_LOG_FILE})."
    )
    mock_deps["open_folder_cb"].assert_not_called()
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_download_partial_then_process(task_manager, mock_deps, setup_start_all):
    """Тест start_all: частичное скачивание, затем успешная обработка."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all
    task_name = wrapper_kwargs['task_name']
    mock_deps["handler"].download_pages.return_value = (7, 10)
    mock_deps["handler"].process_images.return_value = (7, 4)
    wrapper_target(*wrapper_args, **wrapper_kwargs)
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_called_once()
    final_msg_sequence = "Скачивание (7/10) и обработка (7 файлов, 4 разворотов) завершены."
    final_msg_wrapper = f"{task_name}: Задача завершена."
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание завершено с ошибками (7/10). Продолжаем обработку скачанных... ---"),
        call("--- НАЧАЛО: Создание разворотов ---"),
        call(f"--- {final_msg_sequence} ---"),
        call(f"--- {final_msg_wrapper} ---")
    ], any_order=False)
    mock_deps["show_message_cb"].assert_has_calls([
        call('warning', "Скачивание с ошибками", "Скачано 7 из 10 страниц.\nОбработка будет запущена для скачанных файлов."),
        call('info', "Завершено", final_msg_sequence)
    ], any_order=False)
    mock_deps["open_folder_cb"].assert_called_once_with("/path/to/spreads")
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_stopped_during_download(task_manager, mock_deps, setup_start_all):
    """Тест start_all, когда приходит сигнал СТОП во время скачивания."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all
    task_name = wrapper_kwargs['task_name']
    def download_and_stop(*args, **kwargs):
        mock_deps["stop_event"].is_set.return_value = True
        return (5, 10)
    mock_deps["handler"].download_pages.side_effect = download_and_stop
    wrapper_target(*wrapper_args, **wrapper_kwargs)
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_not_called()
    final_msg_wrapper = f"{task_name}: Задача завершена."
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание прервано, обработка отменена ---")
    ], any_order=False)
    assert call(f"--- {final_msg_wrapper} ---") not in mock_deps["status_cb"].call_args_list
    mock_deps["show_message_cb"].assert_not_called()
    mock_deps["open_folder_cb"].assert_not_called()
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_stopped_during_processing(task_manager, mock_deps, setup_start_all):
    """Тест start_all, когда приходит сигнал СТОП во время обработки."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all
    task_name = wrapper_kwargs['task_name']
    mock_deps["handler"].download_pages.return_value = (10, 10)
    def process_and_stop(*args, **kwargs):
        mock_deps["stop_event"].is_set.return_value = True
        return (5, 2)
    mock_deps["handler"].process_images.side_effect = process_and_stop
    wrapper_target(*wrapper_args, **wrapper_kwargs)
    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_called_once()
    final_msg_wrapper = f"{task_name}: Задача завершена."
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание успешно завершено (10/10) ---"),
        call("--- НАЧАЛО: Создание разворотов ---"),
        call("--- Обработка прервана ---")
    ], any_order=False)
    assert call(f"--- {final_msg_wrapper} ---") not in mock_deps["status_cb"].call_args_list
    mock_deps["show_message_cb"].assert_not_called()
    mock_deps["open_folder_cb"].assert_not_called()
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_exception_during_download(task_manager, mock_deps, setup_start_all):
    """Тест start_all с исключением во время скачивания."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all
    task_name = wrapper_kwargs['task_name']
    error_message = "Download failed badly"
    mock_deps["handler"].download_pages.side_effect = Exception(error_message)

    wrapper_target(*wrapper_args, **wrapper_kwargs)

    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_not_called()

    # FIX: Ожидаем ОДИН вызов show_message_cb из _thread_wrapper.except
    expected_error_msg_wrapper = f"{task_name}: Критическая ошибка при выполнении: {error_message}"
    mock_deps["show_message_cb"].assert_called_once_with(
        'error',
        "Критическая ошибка",
        f"{expected_error_msg_wrapper}\n\nПодробности в лог-файле:\n{EXPECTED_MOCKED_LOG_FILE}"
    )

    # Проверка status_cb остается прежней (вызов из _run_all_sequence + финальный из wrapper)
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call(f"--- {expected_error_msg_wrapper} ---")
    ])
    assert mock_deps["status_cb"].call_count == 2

    mock_deps["open_folder_cb"].assert_not_called()
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None


def test_start_all_exception_during_processing(task_manager, mock_deps, setup_start_all):
    """Тест start_all с исключением во время обработки."""
    wrapper_target, wrapper_args, wrapper_kwargs = setup_start_all
    task_name = wrapper_kwargs['task_name']
    error_message = "Processing failed badly"
    mock_deps["handler"].download_pages.return_value = (10, 10)
    mock_deps["handler"].process_images.side_effect = Exception(error_message)

    wrapper_target(*wrapper_args, **wrapper_kwargs)

    mock_deps["handler"].download_pages.assert_called_once()
    mock_deps["handler"].process_images.assert_called_once()

    # FIX: Ожидаем ОДИН вызов show_message_cb из _thread_wrapper.except
    expected_error_msg_wrapper = f"{task_name}: Критическая ошибка при выполнении: {error_message}"
    mock_deps["show_message_cb"].assert_called_once_with(
        'error',
        "Критическая ошибка",
        f"{expected_error_msg_wrapper}\n\nПодробности в лог-файле:\n{EXPECTED_MOCKED_LOG_FILE}"
    )

    # Проверка status_cb остается прежней (вызовы из _run_all_sequence + финальный из wrapper)
    mock_deps["status_cb"].assert_has_calls([
        call("--- НАЧАЛО: Скачивание страниц ---"),
        call("--- Скачивание успешно завершено (10/10) ---"),
        call("--- НАЧАЛО: Создание разворотов ---"),
        call(f"--- {expected_error_msg_wrapper} ---") # Финальное из wrapper с ошибкой
    ])
    assert mock_deps["status_cb"].call_count == 4

    mock_deps["open_folder_cb"].assert_not_called()
    mock_deps["set_buttons_state_cb"].assert_has_calls([call(True), call(False)])
    assert task_manager.current_thread is None

def test_start_all_invalid_pages(task_manager, mock_deps):
    """Тест запуска start_all с некорректным количеством страниц."""
    mock_deps["app_state"].get_total_pages_int.return_value = None
    task_manager.start_all()
    mock_deps["thread_class"].assert_not_called()
    mock_deps["show_message_cb"].assert_called_once_with('error', "Ошибка", "Некорректное количество страниц.")
    mock_deps["set_buttons_state_cb"].assert_not_called()