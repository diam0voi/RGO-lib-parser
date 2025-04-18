import importlib
from pathlib import Path
from unittest.mock import patch

import src.config

# --- Тесты для src/config.py ---


@patch("src.config.Path.mkdir")  # Мокаем mkdir, чтобы не создавать реальную папку
@patch("src.config.Path.home")  # Мокаем home, чтобы не зависеть от системы
def test_config_paths_success(mock_home, mock_mkdir):
    """Тест успешного определения путей через домашнюю директорию."""
    fake_home_path = Path("/fake/home/success")
    mock_home.return_value = fake_home_path

    # Чтобы выполнилась логика определения путей с моками
    importlib.reload(src.config)

    mock_mkdir.assert_called_once_with(exist_ok=True)

    expected_app_data_dir = fake_home_path / f".{src.config.APP_NAME}_data"
    assert (
        str(expected_app_data_dir / "downloaded_pages") == src.config.DEFAULT_PAGES_DIR
    )
    assert (
        str(expected_app_data_dir / "final_spreads") == src.config.DEFAULT_SPREADS_DIR
    )

    assert hasattr(src.config, "DEFAULT_USER_AGENT")
    assert src.config.DEFAULT_USER_AGENT is not None


# Тест для покрытия блока except при ошибке Path.home()
@patch("src.config.Path.home")  # Мокаем home, чтобы вызвать ошибку
def test_config_paths_error_on_home(mock_home):
    """Тест определения путей, когда Path.home() вызывает ошибку."""
    mock_home.side_effect = OSError("Cannot determine home directory")

    importlib.reload(src.config)

    expected_pages_path = Path("./downloaded_pages")
    expected_spreads_path = Path("./final_spreads")
    
    assert str(expected_pages_path) == src.config.DEFAULT_PAGES_DIR
    assert str(expected_spreads_path) == src.config.DEFAULT_SPREADS_DIR
    assert hasattr(src.config, "DEFAULT_USER_AGENT")
    assert src.config.DEFAULT_USER_AGENT is not None


@patch("src.config.Path.mkdir")
@patch("src.config.Path.home")
def test_config_paths_error_on_mkdir(mock_home, mock_mkdir):
    """Тест определения путей, когда mkdir() вызывает ошибку."""
    fake_home_path = Path("/fake/home/mkdir_error")
    mock_home.return_value = fake_home_path
    mock_mkdir.side_effect = PermissionError("Cannot create directory")

    importlib.reload(src.config)

    expected_pages_path = Path("./downloaded_pages")
    expected_spreads_path = Path("./final_spreads")
    
    assert str(expected_pages_path) == src.config.DEFAULT_PAGES_DIR
    assert str(expected_spreads_path) == src.config.DEFAULT_SPREADS_DIR
    assert hasattr(src.config, "DEFAULT_USER_AGENT")
    assert src.config.DEFAULT_USER_AGENT is not None
