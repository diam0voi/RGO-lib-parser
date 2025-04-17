import logging
import sys
import tkinter as tk
from tkinter import messagebox

from . import config, utils
from .gui import JournalDownloaderApp

utils.setup_logging()
logger = logging.getLogger(__name__)


def main():
    """Функция запуска приложения."""
    logger.info(f"Starting {config.APP_NAME} application...")
    root = None
    try:
        root = tk.Tk()
        app = JournalDownloaderApp(root)
        root.mainloop()
        logger.info(f"{config.APP_NAME} finished gracefully.")

    except Exception as main_e:
        logger.critical(
            f"Unhandled exception in main GUI loop: {main_e}", exc_info=True
        )
        try:
            parent_window = root if root and root.winfo_exists() else None
            messagebox.showerror(
                "Фатальная ошибка",
                f"Произошла непредвиденная ошибка:\n{main_e}\n\nПриложение будет закрыто.\nПодробности в лог-файле: {config.LOG_FILE}",
                parent=parent_window,
            )
        except Exception as mb_e:
            print(f"FATAL UNHANDLED ERROR: {main_e}", file=sys.stderr)
            print(f"Also failed to show messagebox: {mb_e}", file=sys.stderr)
    finally:
        logger.info("=" * 20 + f" {config.APP_NAME} execution ended " + "=" * 20)
        logging.shutdown()


if __name__ == "__main__":  # pragma: no cover
    main()
