# tests/test_config.py
import importlib
from pathlib import Path
from unittest.mock import patch

# Импортируем модуль config один раз глобально,
# чтобы он был доступен для reload в тестах.
import src.config

# --- Тесты для src/config.py ---


@patch("src.config.Path.mkdir")  # Мокаем mkdir, чтобы не создавать реальную папку
@patch("src.config.Path.home")  # Мокаем home, чтобы не зависеть от системы
def test_config_paths_success(mock_home, mock_mkdir):
    """Тест успешного определения путей через домашнюю директорию."""
    # Настраиваем мок Path.home()
    fake_home_path = Path("/fake/home/success")
    mock_home.return_value = fake_home_path

    # Перезагружаем модуль config, чтобы выполнилась логика определения путей с моками
    importlib.reload(src.config)

    # Проверяем, что mkdir был вызван для ожидаемой директории
    # Path() внутри config.py создает экземпляр, на котором вызывается mkdir
    # Мы не можем напрямую проверить аргумент mock_mkdir без сложного мокинга Path,
    # но можем проверить, что он был вызван один раз с нужными параметрами.
    mock_mkdir.assert_called_once_with(exist_ok=True)

    # Проверяем, что пути установлены относительно fake_home_path
    expected_app_data_dir = fake_home_path / f".{src.config.APP_NAME}_data"
    assert (
        str(expected_app_data_dir / "downloaded_pages") == src.config.DEFAULT_PAGES_DIR
    )
    assert (
        str(expected_app_data_dir / "final_spreads") == src.config.DEFAULT_SPREADS_DIR
    )

    # Убедимся, что другие константы не пропали
    assert hasattr(src.config, "DEFAULT_USER_AGENT")
    assert src.config.DEFAULT_USER_AGENT is not None


# Тест для покрытия блока except при ошибке Path.home()
@patch("src.config.Path.home")  # Мокаем home, чтобы вызвать ошибку
def test_config_paths_error_on_home(mock_home):
    """Тест определения путей, когда Path.home() вызывает ошибку."""
    # Настраиваем мок Path.home() на вызов исключения
    mock_home.side_effect = OSError("Cannot determine home directory")

    # Перезагружаем модуль config
    importlib.reload(src.config)

    # Проверяем, что пути установлены относительно текущей директории ('.')
    # как в блоке except
    expected_pages_path = Path("./downloaded_pages")
    expected_spreads_path = Path("./final_spreads")
    assert str(expected_pages_path) == src.config.DEFAULT_PAGES_DIR
    assert str(expected_spreads_path) == src.config.DEFAULT_SPREADS_DIR

    # Убедимся, что другие константы не пропали
    assert hasattr(src.config, "DEFAULT_USER_AGENT")
    assert src.config.DEFAULT_USER_AGENT is not None


# Тест для покрытия блока except при ошибке mkdir()
@patch("src.config.Path.mkdir")  # Мокаем mkdir, чтобы вызвать ошибку
@patch("src.config.Path.home")  # Мокаем home, чтобы он успешно вернул путь
def test_config_paths_error_on_mkdir(mock_home, mock_mkdir):
    """Тест определения путей, когда mkdir() вызывает ошибку."""
    # Настраиваем мок Path.home()
    fake_home_path = Path("/fake/home/mkdir_error")
    mock_home.return_value = fake_home_path

    # Настраиваем мок mkdir на вызов исключения
    mock_mkdir.side_effect = PermissionError("Cannot create directory")

    # Перезагружаем модуль config
    importlib.reload(src.config)

    # Проверяем, что пути установлены относительно текущей директории ('.')
    # как в блоке except
    expected_pages_path = Path("./downloaded_pages")
    expected_spreads_path = Path("./final_spreads")
    assert str(expected_pages_path) == src.config.DEFAULT_PAGES_DIR
    assert str(expected_spreads_path) == src.config.DEFAULT_SPREADS_DIR

    # Убедимся, что другие константы не пропали
    assert hasattr(src.config, "DEFAULT_USER_AGENT")
    assert src.config.DEFAULT_USER_AGENT is not None
