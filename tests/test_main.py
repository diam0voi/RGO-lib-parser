# tests/test_main.py
import importlib
import logging
import sys
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from src import config as src_config

# --- Фикстуры ---

@pytest.fixture(autouse=True)
def patch_main_dependencies(monkeypatch):
    """Патчит все внешние зависимости ДО импорта main."""
    mock_setup = MagicMock(name="mock_setup_logging")
    patcher_setup_logging = patch("src.utils.setup_logging", mock_setup)
    patcher_setup_logging.start()

    mock_logger_instance = MagicMock(spec=logging.Logger, name="mock_logger_instance")
    mock_logger_instance.info = MagicMock(name="mock_logger_instance.info")
    mock_logger_instance.critical = MagicMock(name="mock_logger_instance.critical")
    mock_getLogger = MagicMock(return_value=mock_logger_instance, name="mock_getLogger")
    patcher_getLogger = patch("logging.getLogger", mock_getLogger)
    patcher_getLogger.start()

    mock_shutdown = MagicMock(name="mock_shutdown")
    patcher_shutdown = patch("logging.shutdown", mock_shutdown)
    patcher_shutdown.start()

    main_module = None
    try:
        modules_to_delete = [m for m in sys.modules if m.startswith("src.")]
        for mod_name in modules_to_delete:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        if "src.config" in sys.modules:
            importlib.reload(sys.modules["src.config"])
        if "src.utils" in sys.modules:
            importlib.reload(sys.modules["src.utils"])

        import src.main as main_module_imported

        main_module = main_module_imported
        assert main_module is not None
        assert hasattr(main_module, "main")
        mock_setup.assert_called_once()
        mock_getLogger.assert_any_call("src.main")
    except Exception as e:
        patcher_setup_logging.stop()
        patcher_getLogger.stop()
        patcher_shutdown.stop()
        pytest.fail(f"Failed to import/reload src.main after patching: {e}")

    # Патчим зависимости ВНУТРИ main ПОСЛЕ его импорта

    mock_tk_class = MagicMock(name="mock_Tk")
    mock_root_instance = MagicMock(spec=tk.Tk, name="mock_root_instance")
    mock_root_instance.mainloop = MagicMock(return_value=None)
    mock_root_instance.winfo_exists = MagicMock(return_value=True) # Для блока except/finally в main
    mock_root_instance.tk = MagicMock(name="mock_root_instance.tk")

    mock_tk_class.return_value = mock_root_instance
    if main_module and hasattr(main_module, 'tk'):
         monkeypatch.setattr(main_module.tk, "Tk", mock_tk_class, raising=False)
    else:
         patcher_tk_global = patch("tkinter.Tk", mock_tk_class)
         patcher_tk_global.start()

    mock_app_class = MagicMock(name="mock_App")
    mock_app_instance = MagicMock(name="mock_app_instance")
    mock_app_class.return_value = mock_app_instance
    monkeypatch.setattr(main_module, "JournalDownloaderApp", mock_app_class)

    mock_mb = MagicMock(name="mock_messagebox")
    mock_mb.showerror = MagicMock(name="mock_messagebox.showerror")
    monkeypatch.setattr(main_module, "messagebox", mock_mb)

    # Сбрасываем моки ПЕРЕД тестом.
    mock_setup.reset_mock()
    mock_getLogger.reset_mock()
    mock_logger_instance.reset_mock()
    mock_logger_instance.info.reset_mock()
    mock_logger_instance.critical.reset_mock()
    mock_shutdown.reset_mock()
    mock_tk_class.reset_mock()
    mock_root_instance.reset_mock()
    mock_app_class.reset_mock()
    mock_mb.reset_mock()
    mock_mb.showerror.reset_mock()

    yield {
        "mock_setup_logging": mock_setup,
        "mock_getLogger": mock_getLogger,
        "mock_logger_instance": mock_logger_instance,
        "mock_Tk": mock_tk_class,
        "mock_root_instance": mock_root_instance,
        "mock_App": mock_app_class,
        "mock_messagebox": mock_mb,
        "mock_shutdown": mock_shutdown,
        "main_module": main_module,
    }

    patcher_setup_logging.stop()
    patcher_getLogger.stop()
    patcher_shutdown.stop()
    modules_to_delete = [m for m in sys.modules if m.startswith("src.")]
    for mod_name in modules_to_delete:
        if mod_name in sys.modules:
            del sys.modules[mod_name]


# --- Тесты ---

def test_main_happy_path(patch_main_dependencies):
    # Этот тест уже делает то, что нам нужно для проверки основного потока
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]

    # Убедимся, что main существует перед вызовом
    assert hasattr(main_module, "main") and callable(main_module.main)

    main_module.main()

    # --- Assertions ---
    # Проверяем логи
    logger_instance.info.assert_any_call(
        f"Starting {src_config.APP_NAME} application..."
    )
    logger_instance.info.assert_any_call(f"{src_config.APP_NAME} finished gracefully.")
    logger_instance.info.assert_any_call(
        "=" * 20 + f" {src_config.APP_NAME} execution ended " + "=" * 20
    )
    assert logger_instance.info.call_count == 3
    logger_instance.critical.assert_not_called()

    # Проверяем вызовы Tk и App (используем моки из фикстуры)
    mocks["mock_Tk"].assert_called_once()
    mocks["mock_App"].assert_called_once_with(mock_root_instance) # Используем mock_App из фикстуры
    mock_root_instance.mainloop.assert_called_once()

    # Проверяем messagebox и shutdown
    mocks["mock_messagebox"].showerror.assert_not_called()
    mocks["mock_shutdown"].assert_called_once()


def test_main_exception_in_mainloop(patch_main_dependencies):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]
    mock_mb_showerror = mocks["mock_messagebox"].showerror

    test_exception = RuntimeError("Boom in mainloop!")
    mock_root_instance.mainloop.side_effect = test_exception
    mock_root_instance.winfo_exists.return_value = True

    main_module.main()

    logger_instance.info.assert_any_call(
        f"Starting {src_config.APP_NAME} application..."
    )
    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {test_exception}", exc_info=True
    )
    logger_instance.info.assert_any_call(
        "=" * 20 + f" {src_config.APP_NAME} execution ended " + "=" * 20
    )
    assert logger_instance.info.call_count == 2

    mocks["mock_Tk"].assert_called_once()
    mocks["mock_App"].assert_called_once_with(mock_root_instance)
    mock_root_instance.mainloop.assert_called_once()

    mock_root_instance.winfo_exists.assert_called_once()
    mock_mb_showerror.assert_called_once()
    args, kwargs = mock_mb_showerror.call_args
    assert "Фатальная ошибка" in args[0]
    assert str(test_exception) in args[1]
    assert kwargs["parent"] is mock_root_instance

    mocks["mock_shutdown"].assert_called_once()


def test_main_exception_in_mainloop_and_messagebox(patch_main_dependencies, capsys):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]
    mock_mb_showerror = mocks["mock_messagebox"].showerror

    main_exception = ValueError("Primary crash")
    messagebox_exception = tk.TclError("Cannot show box")
    mock_root_instance.mainloop.side_effect = main_exception
    mock_root_instance.winfo_exists.return_value = True
    mock_mb_showerror.side_effect = messagebox_exception

    main_module.main()

    logger_instance.info.assert_any_call(
        f"Starting {src_config.APP_NAME} application..."
    )
    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {main_exception}", exc_info=True
    )
    logger_instance.info.assert_any_call(
        "=" * 20 + f" {src_config.APP_NAME} execution ended " + "=" * 20
    )
    assert logger_instance.info.call_count == 2

    mocks["mock_Tk"].assert_called_once()
    mocks["mock_App"].assert_called_once_with(mock_root_instance)
    mock_root_instance.mainloop.assert_called_once()

    mock_root_instance.winfo_exists.assert_called_once()
    mock_mb_showerror.assert_called_once()

    captured = capsys.readouterr()
    stderr_output = captured.err
    assert f"FATAL UNHANDLED ERROR: {main_exception}" in stderr_output
    assert f"Also failed to show messagebox: {messagebox_exception}" in stderr_output

    mocks["mock_shutdown"].assert_called_once()


def test_main_exception_tk_init_fails(patch_main_dependencies):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_mb_showerror = mocks["mock_messagebox"].showerror

    tk_exception = tk.TclError("Display not found")
    # Важно: для этого теста мы *хотим*, чтобы mock_Tk вызывал исключение,
    # поэтому используем side_effect здесь, а не return_value.
    mocks["mock_Tk"].side_effect = tk_exception
    # Убедимся, что return_value не установлен (хотя side_effect имеет приоритет)
    mocks["mock_Tk"].return_value = None

    main_module.main()

    logger_instance.info.assert_any_call(
        f"Starting {src_config.APP_NAME} application..."
    )
    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {tk_exception}", exc_info=True
    )
    logger_instance.info.assert_any_call(
        "=" * 20 + f" {src_config.APP_NAME} execution ended " + "=" * 20
    )
    assert logger_instance.info.call_count == 2

    mocks["mock_Tk"].assert_called_once()
    mocks["mock_App"].assert_not_called()
    # mock_root_instance не должен был быть создан или использован
    mocks["mock_root_instance"].mainloop.assert_not_called()
    mocks["mock_root_instance"].winfo_exists.assert_not_called()

    mock_mb_showerror.assert_called_once()
    args, kwargs = mock_mb_showerror.call_args
    assert "Фатальная ошибка" in args[0]
    assert str(tk_exception) in args[1]
    assert kwargs["parent"] is None

    mocks["mock_shutdown"].assert_called_once()


def test_main_exception_root_does_not_exist(patch_main_dependencies):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]
    mock_mb_showerror = mocks["mock_messagebox"].showerror

    test_exception = RuntimeError("Boom in mainloop!")
    mock_root_instance.mainloop.side_effect = test_exception
    mock_root_instance.winfo_exists.return_value = False

    main_module.main()

    logger_instance.info.assert_any_call(
        f"Starting {src_config.APP_NAME} application..."
    )
    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {test_exception}", exc_info=True
    )
    logger_instance.info.assert_any_call(
        "=" * 20 + f" {src_config.APP_NAME} execution ended " + "=" * 20
    )
    assert logger_instance.info.call_count == 2

    mocks["mock_Tk"].assert_called_once()
    mocks["mock_App"].assert_called_once_with(mock_root_instance)
    mock_root_instance.mainloop.assert_called_once()

    mock_root_instance.winfo_exists.assert_called_once()
    mock_mb_showerror.assert_called_once()
    args, kwargs = mock_mb_showerror.call_args
    assert "Фатальная ошибка" in args[0]
    assert str(test_exception) in args[1]
    assert kwargs["parent"] is None

    mocks["mock_shutdown"].assert_called_once()
