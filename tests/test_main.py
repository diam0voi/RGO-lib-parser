# tests/test_main.py
import pytest
from unittest.mock import MagicMock, call, patch # <-- Добавлен patch
import tkinter as tk
import sys
from io import StringIO
import logging
import importlib

# Импортируем зависимости ПЕРЕД тестами
from src import config
# НЕ импортируем utils и main здесь, они обрабатываются в фикстуре

# --- Фикстуры ---

@pytest.fixture(autouse=True)
def patch_main_dependencies(monkeypatch):
    """Патчит все внешние зависимости и module-level код main.py."""
    # --- Патчим ДО импорта main ---
    # Патчим setup_logging в utils ПЕРЕД тем, как main его импортирует
    mock_setup = MagicMock(name="mock_setup_logging")
    # Используем patch вместо monkeypatch для модуля, который еще не импортирован явно здесь
    # Важно: указываем полный путь к функции, которую main.py будет импортировать
    patcher_setup_logging = patch('src.utils.setup_logging', mock_setup)
    patcher_setup_logging.start() # Начинаем патчить

    # Патчим getLogger в logging (глобально) ПЕРЕД импортом main
    mock_logger_instance = MagicMock(name="mock_logger_instance")
    mock_getLogger = MagicMock(return_value=mock_logger_instance, name="mock_getLogger")
    patcher_getLogger = patch('logging.getLogger', mock_getLogger)
    patcher_getLogger.start()

    # Патчим logging.shutdown (глобально)
    mock_shutdown = MagicMock(name="mock_shutdown")
    patcher_shutdown = patch('logging.shutdown', mock_shutdown)
    patcher_shutdown.start()

    # --- Теперь импортируем main, он должен подхватить моки setup_logging и getLogger ---
    # Используем importlib для чистого импорта/перезагрузки
    if 'src.main' in sys.modules:
        importlib.reload(sys.modules['src.main'])
    else:
        import src.main

    # --- Патчим зависимости ВНУТРИ main ПОСЛЕ его импорта ---
    # Патчим Tk
    mock_tk_class = MagicMock(name="mock_Tk")
    mock_root_instance = MagicMock(name="mock_root_instance")
    mock_root_instance.mainloop.return_value = None
    mock_root_instance.winfo_exists.return_value = True
    mock_tk_class.return_value = mock_root_instance
    monkeypatch.setattr(src.main.tk, "Tk", mock_tk_class)

    # Патчим App
    mock_app_class = MagicMock(name="mock_App")
    mock_app_instance = MagicMock(name="mock_app_instance")
    mock_app_class.return_value = mock_app_instance
    monkeypatch.setattr(src.main, "JournalDownloaderApp", mock_app_class)

    # Патчим messagebox
    mock_mb = MagicMock(name="mock_messagebox")
    monkeypatch.setattr(src.main, "messagebox", mock_mb)

    # Фикстура yield возвращает нужные моки, если они понадобятся в тестах
    yield {
        "mock_setup_logging": mock_setup,
        "mock_getLogger": mock_getLogger,
        "mock_logger_instance": mock_logger_instance,
        "mock_Tk": mock_tk_class,
        "mock_root_instance": mock_root_instance,
        "mock_App": mock_app_class,
        "mock_messagebox": mock_mb,
        "mock_shutdown": mock_shutdown,
        "main_module": src.main # Возвращаем сам модуль main
    }

    # Останавливаем патчеры после теста
    patcher_setup_logging.stop()
    patcher_getLogger.stop()
    patcher_shutdown.stop()


@pytest.fixture
def mock_stderr():
    """Перехватывает sys.stderr."""
    original_stderr = sys.stderr
    sys.stderr = captured_stderr = StringIO()
    yield captured_stderr
    sys.stderr = original_stderr


# --- Тесты ---

def test_main_happy_path(patch_main_dependencies, mock_stderr):
    """Test successful execution path."""
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]

    main_module.main()

    # Assertions
    # ИСПРАВЛЕНО: setup_logging вызывается один раз при импорте модуля main
    mocks["mock_setup_logging"].assert_called_once()
    # ИСПРАВЛЕНО: getLogger вызывается один раз при импорте модуля main
    mocks["mock_getLogger"].assert_called_once_with(main_module.__name__)

    logger_instance.info.assert_any_call(f"Starting {config.APP_NAME} application...")
    mocks["mock_Tk"].assert_called_once()
    mocks["mock_App"].assert_called_once_with(mock_root_instance)
    mock_root_instance.mainloop.assert_called_once()
    logger_instance.info.assert_any_call(f"{config.APP_NAME} finished gracefully.")
    logger_instance.critical.assert_not_called()
    mocks["mock_messagebox"].showerror.assert_not_called()

    # --- ИСПРАВЛЕНА ПРОВЕРКА finally ---
    final_log_call = call("="*20 + f" {config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    # Проверяем, что shutdown был вызван хотя бы раз
    assert mocks["mock_shutdown"].call_count >= 1


def test_main_exception_in_mainloop(patch_main_dependencies, mock_stderr):
    """Test exception during mainloop showing messagebox."""
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]
    test_exception = RuntimeError("Boom in mainloop!")
    mock_root_instance.mainloop.side_effect = test_exception
    mock_root_instance.winfo_exists.return_value = True # Убедимся, что окно "существует" для parent

    main_module.main()

    # Assertions
    mocks["mock_setup_logging"].assert_called_once()
    mocks["mock_getLogger"].assert_called_once_with(main_module.__name__)
    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {test_exception}",
        exc_info=True
    )
    # ИСПРАВЛЕНО: Проверяем, что winfo_exists был вызван для определения parent
    mock_root_instance.winfo_exists.assert_called_once()
    mocks["mock_messagebox"].showerror.assert_called_once()
    args, kwargs = mocks["mock_messagebox"].showerror.call_args
    assert "Фатальная ошибка" in args
    assert f"{test_exception}" in args[1] # Проверяем текст ошибки
    assert kwargs['parent'] is mock_root_instance # Parent должен быть установлен

    # --- ИСПРАВЛЕНА ПРОВЕРКА finally ---
    final_log_call = call("="*20 + f" {config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    assert mocks["mock_shutdown"].call_count >= 1


def test_main_exception_in_mainloop_and_messagebox(patch_main_dependencies, mock_stderr):
    """Test exception in mainloop AND messagebox, printing to stderr."""
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]
    main_exception = ValueError("Primary crash")
    mock_root_instance.mainloop.side_effect = main_exception
    mock_root_instance.winfo_exists.return_value = True

    messagebox_exception = tk.TclError("Cannot show box")
    mocks["mock_messagebox"].showerror.side_effect = messagebox_exception

    main_module.main()

    # Assertions
    mocks["mock_setup_logging"].assert_called_once()
    mocks["mock_getLogger"].assert_called_once_with(main_module.__name__)
    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {main_exception}",
        exc_info=True
    )
    mock_root_instance.winfo_exists.assert_called_once()
    mocks["mock_messagebox"].showerror.assert_called_once() # Попытка вызова была

    # Проверяем вывод в stderr
    stderr_output = mock_stderr.getvalue()
    assert f"FATAL UNHANDLED ERROR: {main_exception}" in stderr_output
    assert f"Also failed to show messagebox: {messagebox_exception}" in stderr_output

    # --- ИСПРАВЛЕНА ПРОВЕРКА finally ---
    final_log_call = call("="*20 + f" {config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    assert mocks["mock_shutdown"].call_count >= 1


def test_main_exception_tk_init_fails(patch_main_dependencies, mock_stderr):
    """Test exception during tk.Tk() initialization."""
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    tk_exception = tk.TclError("Display not found")
    mocks["mock_Tk"].side_effect = tk_exception # Настраиваем мок из фикстуры

    main_module.main()

    # Assertions
    mocks["mock_setup_logging"].assert_called_once()
    mocks["mock_getLogger"].assert_called_once_with(main_module.__name__)
    logger_instance.info.assert_any_call(f"Starting {config.APP_NAME} application...")
    mocks["mock_Tk"].assert_called_once() # Попытка создания была
    mocks["mock_App"].assert_not_called() # До создания App не дошло
    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {tk_exception}",
        exc_info=True
    )
    # ИСПРАВЛЕНО: Проверяем, что winfo_exists НЕ вызывался, т.к. root=None
    mocks["mock_root_instance"].winfo_exists.assert_not_called()
    mocks["mock_messagebox"].showerror.assert_called_once()
    args, kwargs = mocks["mock_messagebox"].showerror.call_args
    assert kwargs['parent'] is None # Parent должен быть None

    # --- ИСПРАВЛЕНА ПРОВЕРКА finally ---
    final_log_call = call("="*20 + f" {config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    assert mocks["mock_shutdown"].call_count >= 1


def test_main_exception_root_does_not_exist(patch_main_dependencies, mock_stderr):
    """Test exception in mainloop, root.winfo_exists() returns False."""
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]
    test_exception = RuntimeError("Boom in mainloop!")
    mock_root_instance.mainloop.side_effect = test_exception
    # ИСПРАВЛЕНО: Устанавливаем, что окно не существует
    mock_root_instance.winfo_exists.return_value = False

    main_module.main()

    # Assertions
    mocks["mock_setup_logging"].assert_called_once()
    mocks["mock_getLogger"].assert_called_once_with(main_module.__name__)
    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {test_exception}",
        exc_info=True
    )
    mock_root_instance.winfo_exists.assert_called_once() # Проверка была
    mocks["mock_messagebox"].showerror.assert_called_once()
    args, kwargs = mocks["mock_messagebox"].showerror.call_args
    assert kwargs['parent'] is None # Parent должен быть None, т.к. окно не существует

    # --- ИСПРАВЛЕНА ПРОВЕРКА finally ---
    final_log_call = call("="*20 + f" {config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    assert mocks["mock_shutdown"].call_count >= 1