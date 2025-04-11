import threading
from typing import Callable

# Общие типы колбэков для GUI
StatusCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]
StopEvent = threading.Event
