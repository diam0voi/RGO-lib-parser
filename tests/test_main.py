# tests/test_main.py
import pytest
from unittest.mock import MagicMock, call, patch
import tkinter as tk
import sys
from io import StringIO
import logging
import importlib
import os
import runpy


from src import config as src_config


# --- Фикстуры ---

@pytest.fixture(autouse=True)
def patch_main_dependencies(monkeypatch):
    """Патчит все внешние зависимости ДО импорта main."""
    # --- Патчим ДО импорта/релоада main ---
    mock_setup = MagicMock(name="mock_setup_logging")
    patcher_setup_logging = patch('src.utils.setup_logging', mock_setup)
    patcher_setup_logging.start() # Запускаем патч ДО импорта

    mock_logger_instance = MagicMock(spec=logging.Logger, name="mock_logger_instance")
    mock_logger_instance.info = MagicMock()
    mock_logger_instance.critical = MagicMock()
    mock_getLogger = MagicMock(return_value=mock_logger_instance, name="mock_getLogger")
    patcher_getLogger = patch('logging.getLogger', mock_getLogger)
    patcher_getLogger.start() # Запускаем патч ДО импорта

    mock_shutdown = MagicMock(name="mock_shutdown")
    patcher_shutdown = patch('logging.shutdown', mock_shutdown)
    patcher_shutdown.start()

    # --- Теперь импортируем/перезагружаем main ---
    # Это вызовет module-level код main (включая setup_logging и getLogger)
    main_module = None
    try:
        if 'src.main' in sys.modules:
            # Удаляем старый модуль перед перезагрузкой, чтобы применились патчи
            del sys.modules['src.main']
            # Если utils тоже был импортирован, перезагружаем и его, т.к. main его импортирует
            if 'src.utils' in sys.modules:
                # Перезагрузка utils может быть сложной, если он сам имеет состояние
                # или зависимости. Проще его тоже удалить и дать main импортировать заново.
                del sys.modules['src.utils']
        # Импортируем main после применения патчей
        import src.main as main_module_imported
        main_module = main_module_imported
        assert main_module is not None
        assert hasattr(main_module, 'main')
        # Проверяем, что setup_logging был вызван при импорте/перезагрузке
        mock_setup.assert_called_once()
        mock_getLogger.assert_any_call(main_module.__name__) # __name__ будет 'src.main' здесь
    except Exception as e:
        # Останавливаем патчи в случае ошибки импорта
        patcher_setup_logging.stop()
        patcher_getLogger.stop()
        patcher_shutdown.stop()
        pytest.fail(f"Failed to import/reload src.main after patching: {e}")

    # --- Патчим зависимости ВНУТРИ main ПОСЛЕ его импорта ---
    mock_tk_class = MagicMock(name="mock_Tk")
    mock_root_instance = MagicMock(spec=tk.Tk, name="mock_root_instance")
    mock_root_instance.mainloop = MagicMock(return_value=None)
    mock_root_instance.winfo_exists = MagicMock(return_value=True)
    mock_tk_class.return_value = mock_root_instance
    monkeypatch.setattr(main_module.tk, "Tk", mock_tk_class)

    mock_app_class = MagicMock(name="mock_App")
    mock_app_instance = MagicMock(name="mock_app_instance")
    mock_app_class.return_value = mock_app_instance
    monkeypatch.setattr(main_module, "JournalDownloaderApp", mock_app_class)

    mock_mb = MagicMock(name="mock_messagebox")
    monkeypatch.setattr(main_module, "messagebox", mock_mb)

    # Сбрасываем моки ПЕРЕД тестом, КРОМЕ setup_logging и getLogger (они вызывались при импорте)
    # Важно: сбросим их счетчики вызовов, т.к. runpy может вызвать их снова
    mock_setup.reset_mock()
    mock_getLogger.reset_mock()
    mock_logger_instance.reset_mock()
    mock_shutdown.reset_mock()
    mock_tk_class.reset_mock()
    mock_root_instance.reset_mock()
    mock_app_class.reset_mock()
    mock_mb.reset_mock()

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
        "monkeypatch": monkeypatch # <--- Передаем monkeypatch для использования в тесте
    }

    # Останавливаем патчи после теста
    patcher_setup_logging.stop()
    patcher_getLogger.stop()
    patcher_shutdown.stop()
    # Очищаем модуль из кеша, чтобы следующий тест начал с чистого листа
    if 'src.main' in sys.modules:
        del sys.modules['src.main']
    if 'src.utils' in sys.modules:
        del sys.modules['src.utils']


@pytest.fixture
def mock_stderr():
    """Перехватывает sys.stderr."""
    original_stderr = sys.stderr
    sys.stderr = captured_stderr = StringIO()
    yield captured_stderr
    sys.stderr = original_stderr
    captured_stderr.close()


# --- Тесты ---

def test_main_happy_path(patch_main_dependencies):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]

    # Проверяем вызовы при импорте (уже сделано в фикстуре при первом импорте/релоаде)
    # mocks["mock_setup_logging"].assert_called_once() # Вызывается при импорте
    # mocks["mock_getLogger"].assert_any_call(main_module.__name__) # Вызывается при импорте

    main_module.main()

    # Проверки внутри main()
    logger_instance.info.assert_any_call(f"Starting {src_config.APP_NAME} application...")
    mocks["mock_Tk"].assert_called_once()
    mocks["mock_App"].assert_called_once_with(mock_root_instance)
    mock_root_instance.mainloop.assert_called_once()
    logger_instance.info.assert_any_call(f"{src_config.APP_NAME} finished gracefully.")
    logger_instance.critical.assert_not_called()
    mocks["mock_messagebox"].showerror.assert_not_called()
    final_log_call = call("="*20 + f" {src_config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    mocks["mock_shutdown"].assert_called_once()


def test_main_exception_in_mainloop(patch_main_dependencies):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]
    test_exception = RuntimeError("Boom in mainloop!")
    mock_root_instance.mainloop.side_effect = test_exception
    mock_root_instance.winfo_exists.return_value = True

    main_module.main()

    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {test_exception}",
        exc_info=True
    )
    mock_root_instance.winfo_exists.assert_called_once()
    mocks["mock_messagebox"].showerror.assert_called_once()
    args, kwargs = mocks["mock_messagebox"].showerror.call_args
    assert kwargs['parent'] is mock_root_instance
    final_log_call = call("="*20 + f" {src_config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    mocks["mock_shutdown"].assert_called_once()


def test_main_exception_in_mainloop_and_messagebox(patch_main_dependencies, mock_stderr):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]
    main_exception = ValueError("Primary crash")
    messagebox_exception = tk.TclError("Cannot show box")
    mock_root_instance.mainloop.side_effect = main_exception
    mock_root_instance.winfo_exists.return_value = True
    mocks["mock_messagebox"].showerror.side_effect = messagebox_exception

    main_module.main()

    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {main_exception}",
        exc_info=True
    )
    mock_root_instance.winfo_exists.assert_called_once()
    mocks["mock_messagebox"].showerror.assert_called_once()
    stderr_output = mock_stderr.getvalue()
    assert f"FATAL UNHANDLED ERROR: {main_exception}" in stderr_output
    assert f"Also failed to show messagebox: {messagebox_exception}" in stderr_output
    final_log_call = call("="*20 + f" {src_config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    mocks["mock_shutdown"].assert_called_once()


def test_main_exception_tk_init_fails(patch_main_dependencies):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    tk_exception = tk.TclError("Display not found")
    mocks["mock_Tk"].side_effect = tk_exception

    main_module.main()

    logger_instance.info.assert_any_call(f"Starting {src_config.APP_NAME} application...")
    mocks["mock_Tk"].assert_called_once()
    mocks["mock_App"].assert_not_called()
    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {tk_exception}",
        exc_info=True
    )
    mocks["mock_root_instance"].winfo_exists.assert_not_called()
    mocks["mock_messagebox"].showerror.assert_called_once()
    args, kwargs = mocks["mock_messagebox"].showerror.call_args
    assert kwargs['parent'] is None
    final_log_call = call("="*20 + f" {src_config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    mocks["mock_shutdown"].assert_called_once()


def test_main_exception_root_does_not_exist(patch_main_dependencies):
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    logger_instance = mocks["mock_logger_instance"]
    mock_root_instance = mocks["mock_root_instance"]
    test_exception = RuntimeError("Boom in mainloop!")
    mock_root_instance.mainloop.side_effect = test_exception
    mock_root_instance.winfo_exists.return_value = False

    main_module.main()

    logger_instance.critical.assert_called_once_with(
        f"Unhandled exception in main GUI loop: {test_exception}",
        exc_info=True
    )
    mock_root_instance.winfo_exists.assert_called_once()
    mocks["mock_messagebox"].showerror.assert_called_once()
    args, kwargs = mocks["mock_messagebox"].showerror.call_args
    assert kwargs['parent'] is None
    final_log_call = call("="*20 + f" {src_config.APP_NAME} execution ended " + "="*20)
    assert final_log_call in logger_instance.info.call_args_list
    mocks["mock_shutdown"].assert_called_once()



def test_main_entry_point(patch_main_dependencies):
    """Тестирует вызов main() через точку входа if __name__ == '__main__'."""
    mocks = patch_main_dependencies
    main_module = mocks["main_module"]
    monkeypatch = mocks["monkeypatch"] # Получаем monkeypatch из фикстуры

    # Мокаем саму функцию main внутри модуля main, чтобы не выполнять её логику повторно
    mock_main_func = MagicMock(name="mock_main_func_in_module")
    monkeypatch.setattr(main_module, "main", mock_main_func)

    # Используем runpy для запуска модуля 'src.main' как основного скрипта.
    # runpy установит __name__ = '__main__' внутри выполняемого модуля.
    # Важно: все патчи из patch_main_dependencies уже активны.
    # Модуль-уровневый код (setup_logging, getLogger) выполнится СНОВА при вызове runpy.
    # Это нормально, т.к. наши моки перехватят эти вызовы.
    try:
        runpy.run_module('src.main', run_name='__main__')
    except Exception as e:
        # Если runpy падает, это проблема в тесте или настройке
        pytest.fail(f"runpy.run_module failed: {e}")

    # Проверяем, что функция main (которую мы замокали) была вызвана один раз
    # благодаря блоку if __name__ == "__main__":
    mock_main_func.assert_called_once()

    # Дополнительно можно проверить, что модуль-уровневый код был вызван runpy
    # (это будет второй вызов за время жизни теста, первый был при импорте в фикстуре)
    # mocks["mock_setup_logging"].assert_called() # Проверить, что был вызван хотя бы раз
    # mocks["mock_getLogger"].assert_any_call('__main__') # Проверить, что логгер был запрошен с именем __main__