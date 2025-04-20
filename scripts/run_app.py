import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src import main

if __name__ == "__main__":
    main.main()  # Для сохранения относительных импортов
