# RGO-lib-parser
Simple thing for a simple task


| Категория        | Статус                                                                                                                                                              |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Тесты & Качество** | [![Test Status](https://img.shields.io/github/actions/workflow/status/diam0voi/RGO-lib-parser/ci.yml?branch=main&label=tests&logo=github)](https://github.com/diam0voi/RGO-lib-parser/actions/workflows/ci.yml) [![Coverage Status](https://coveralls.io/repos/github/diam0voi/RGO-lib-parser/badge.svg?branch=main)](https://coveralls.io/github/diam0voi/RGO-lib-parser?branch=main) |
| **Версия**       | [![GitHub release (latest by date)](https://img.shields.io/github/v/release/diam0voi/RGO-lib-parser)](https://github.com/diam0voi/RGO-lib-parser/releases/latest) [![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/diam0voi/RGO-lib-parser.svg)](https://github.com/diam0voi/RGO-lib-parser/) |
| **Совместимость** | ![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13+-blue?logo=python&logoColor=white) ![Windows](https://img.shields.io/badge/Windows%2010+-0078D6) ![macOS](https://img.shields.io/badge/MacOS%2015+-000000?logo=macos&logoColor=white) ![Ubuntu](https://img.shields.io/badge/Ubuntu%2024+-E95420?logo=ubuntu&logoColor=white) |
| **Другое**       | [![GitHub license](https://img.shields.io/github/license/diam0voi/RGO-lib-parser)](https://github.com/diam0voi/RGO-lib-parser/blob/main/LICENSE) [![GitHub last commit](https://img.shields.io/github/last-commit/diam0voi/RGO-lib-parser)](https://github.com/diam0voi/RGO-lib-parser/commits/main) [![GitHub repo size](https://img.shields.io/github/repo-size/diam0voi/RGO-lib-parser.svg)](https://github.com/diam0voi/RGO-lib-parser/) |


![image](https://github.com/user-attachments/assets/4ec54270-8c15-4eb1-b83e-0956a8c59e79)

![image](https://github.com/user-attachments/assets/6040a85c-3043-4d02-ad77-e4095adf2ec0)

![image](https://github.com/user-attachments/assets/f57566c9-c692-4e68-91f5-5f2589cf34dc)


# **ENG** Instructions:
1. Download and run the program for your OS
2. Open the document you need on the website of the Russian Geographical Society library (in the library's protected view (PV) module)
3. Make sure the link looks like "https://elib.rgo.ru/safe-view/123456789/.../1/..."
4. Enter the name of the open file (you can see it on the main page) and the number of its pages (displayed in the PV module)
5. Enjoy!

# **RU** Инструкция: 
1. Скачайте и запустите программу под вашу ОС
2. Откройте нужный вам документ на сайте библиотеки Русского Географического Общества (в модуле защищённого просмотра (ЗП) библиотеки)
3. Убедитесь, что ссылка имеет вид "https://elib.rgo.ru/safe-view/123456789/.../1/..."
4. Введите имя открытого файла (можно посмотреть на основной странице) и кол-во его страниц (отображается в модуле ЗП)
5. Наслаждайтесь!


#
В будущих обновлениях планируется достичь покрытия 90%+ юнит-тестированием и внедрить некоторые простые фичи.

#
```
├── .github/
│   └── workflows/
│       ├── build-v1.0-release.yml
│       ├── ci.yml
│       └── crossbuild-release.yml
│
│
├── v0.1 separated/        
│   ├── sdloady_RGO_lib.py
│   └── spready_RGO_lib.py
│
│
├── src/
│   ├── config.py
│   ├── ru_geo_lib_parser_by_b0s.py
│   └── rgo_lib_parser_test.py
│
│
├── assets/
│   ├── macapp_lilacbook.icns
│   ├── winapp_lilacbook.ico
│   └── window_bnwbook.png
│
│
├── .gitignore
├── CODE_OF_CONDUCT.md
├── LICENSE
├── README.md
└── requirements.txt
```
