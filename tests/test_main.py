# tests/test_main.py
import importlib
import logging
import runpy
import sys
import tkinter as tk
from unittest.mock import MagicMock, patch  # <--- Убедись, что patch импортирован

import pytest

# Убрали traceback, т.к. отладка завершена
# import traceback
from src import config as src_config

# --- Фикстуры ---


@pytest.fixture(autouse=True)
def patch_main_dependencies(monkeypatch):
    """Патчит все внешние зависимости ДО импорта main."""
    # --- Патчим ДО импорта/релоада main ---
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

    # --- Теперь импортируем/перезагружаем main ---
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

    # --- Патчим зависимости ВНУТРИ main ПОСЛЕ его импорта ---

    # УБРАНА ОТЛАДКА: Возвращаем простое создание моков Tk
    mock_tk_class = MagicMock(name="mock_Tk")
    mock_root_instance = MagicMock(spec=tk.Tk, name="mock_root_instance")
    mock_root_instance.mainloop = MagicMock(return_value=None)
    mock_root_instance.winfo_exists = MagicMock(return_value=True)
    mock_tk_class.return_value = (
        mock_root_instance  # Устанавливаем возвращаемое значение
    )
    monkeypatch.setattr(main_module.tk, "Tk", mock_tk_class)

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

    # Останавливаем патчи после теста
    patcher_setup_logging.stop()
    patcher_getLogger.stop()
    patcher_shutdown.stop()
    # Очищаем модули из кеша после теста для чистоты
    modules_to_delete = [m for m in sys.modules if m.startswith("src.")]
    for mod_name in modules_to_delete:
        if mod_name in sys.modules:
            del sys.modules[mod_name]


# --- Тесты ---


def test_main_happy_path(patch_main_dependencies):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]

    main_module.main()

    logger_instance.info.assert_any_call(
        f"Starting {src_config.APP_NAME} application..."
    )
    logger_instance.info.assert_any_call(f"{src_config.APP_NAME} finished gracefully.")
    logger_instance.info.assert_any_call(
        "=" * 20 + f" {src_config.APP_NAME} execution ended " + "=" * 20
    )
    assert logger_instance.info.call_count == 3

    mocks["mock_Tk"].assert_called_once()
    mocks["mock_App"].assert_called_once_with(mock_root_instance)
    mock_root_instance.mainloop.assert_called_once()

    logger_instance.critical.assert_not_called()
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


def test_main_entry_point(patch_main_dependencies):
    """Тестирует вызов main() через точку входа if __name__ == '__main__'."""
    mocks = patch_main_dependencies

    # Сбрасываем моки
    mocks["mock_Tk"].reset_mock()
    mocks["mock_root_instance"].reset_mock()
    mocks["mock_logger_instance"].info.reset_mock()
    mocks["mock_logger_instance"].critical.reset_mock()
    mocks["mock_shutdown"].reset_mock()
    # Мок App из фикстуры нам больше не нужен для проверок в этом тесте,
    # т.к. мы будем проверять мок, созданный внутри 'with patch'
    # mocks["mock_App"].reset_mock()

    # Удаляем модули src
    modules_to_delete = [m for m in sys.modules if m.startswith("src.")]
    for mod_name in modules_to_delete:
        if mod_name in sys.modules:
            del sys.modules[mod_name]

    try:
        # Получаем наш мок корневого окна
        mock_root = mocks["mock_root_instance"]
        # Создаем отдельный мок для App ИМЕННО для этого теста/runpy
        mock_app_for_runpy = MagicMock(name="mock_app_instance_for_runpy")

        # Патчим _get_default_root И JournalDownloaderApp в ИСХОДНОМ модуле gui
        with (
            patch("tkinter._get_default_root", return_value=mock_root),
            patch(
                "src.gui.JournalDownloaderApp", return_value=mock_app_for_runpy
            ) as mock_app_class_in_runpy,
        ):  # <--- ИЗМЕНЕН ПУТЬ ПАТЧА
            # Запускаем runpy ВНУТРИ контекста патчей
            runpy.run_module("src.main", run_name="__main__")

    except Exception as e:
        pytest.fail(f"runpy.run_module failed unexpectedly: {e}")

    # --- Проверки ---
    # Теперь ожидаем настоящий happy path

    # Проверяем, что mock_Tk (класс) был вызван ровно один раз
    mocks["mock_Tk"].assert_called_once()

    # Проверяем, что JournalDownloaderApp (запатченный в src.gui) был вызван
    # с mock_root_instance (который вернул mock_Tk)
    mock_app_class_in_runpy.assert_called_once_with(
        mocks["mock_root_instance"]
    )  # Эта проверка должна теперь работать

    # Проверяем вызов mainloop у mock_root_instance
    mocks["mock_root_instance"].mainloop.assert_called_once()

    # Проверяем логи - теперь "finished gracefully" ДОЛЖЕН быть
    mocks["mock_logger_instance"].info.assert_any_call(
        f"Starting {src_config.APP_NAME} application..."
    )
    mocks["mock_logger_instance"].info.assert_any_call(
        f"{src_config.APP_NAME} finished gracefully."
    )
    mocks["mock_logger_instance"].info.assert_any_call(
        "=" * 20 + f" {src_config.APP_NAME} execution ended " + "=" * 20
    )
    assert mocks["mock_logger_instance"].info.call_count == 3
    mocks[
        "mock_logger_instance"
    ].critical.assert_not_called()  # Критических ошибок быть не должно
    mocks["mock_shutdown"].assert_called_once()
