# RGO-lib-parser: описание
[![switch to ENG](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/diam0voi/RGO-lib-parser/README.md)

### Простенькая штучка для простенькой задачки
По своей сути - это парсер, предназначенный для конкретного сайта с его отчасти причудливым форматом хранения данных. На нём собраны сканы редких экземпляров очень нишевых исторических литературных источников, которые вам могут понадобится, скажем, для интерактивной панели на выставке. Но просто так вам их не получить! Вы можете только смотреть! Так родилась идея автоматизировать процесс ручного создания целой горы скриншотов: я решил облегчить жизнь знакомым, которым пришлось этим заниматься. 

Это мой первый проект ТАКОГО уровня, так что не удивляйтесь коммитам в 2 строчки и совершенно нелепым косякам, со временем я точно освоюсь и чувство кринжа пройдёт (нет).

### Информативное
|        |                                                                                                                                                             |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Качество** | [![Test Status](https://img.shields.io/github/actions/workflow/status/diam0voi/RGO-lib-parser/ci.yml?branch=main&label=tests&logo=github)](https://github.com/diam0voi/RGO-lib-parser/actions/workflows/ci.yml) [![Coverage Status](https://coveralls.io/repos/github/diam0voi/RGO-lib-parser/badge.svg?branch=main)](https://coveralls.io/github/diam0voi/RGO-lib-parser?branch=main) |
| **Совместимость** | ![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13+-green?logo=python&logoColor=yellow) ![Windows](https://img.shields.io/badge/Windows%2010+-0078D6) ![macOS](https://img.shields.io/badge/MacOS%2015+-000000?logo=macos&logoColor=white) ![Ubuntu](https://img.shields.io/badge/Ubuntu%2024+-E95420?logo=ubuntu&logoColor=white) |
| **Другое**       |  [![GitHub last commit](https://img.shields.io/github/last-commit/diam0voi/RGO-lib-parser)](https://github.com/diam0voi/RGO-lib-parser/commits/main) [![GitHub repo size](https://img.shields.io/github/repo-size/diam0voi/RGO-lib-parser.svg)](https://github.com/diam0voi/RGO-lib-parser/) [![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/diam0voi/RGO-lib-parser.svg)](https://github.com/diam0voi/RGO-lib-parser/) |
| | | 

## Образец работы приложения на разных этапах
![image](https://github.com/user-attachments/assets/4ec54270-8c15-4eb1-b83e-0956a8c59e79)

![image](https://github.com/user-attachments/assets/6040a85c-3043-4d02-ad77-e4095adf2ec0)

![image](https://github.com/user-attachments/assets/f57566c9-c692-4e68-91f5-5f2589cf34dc)


## Инструкция
1. Скачайте последнюю версию программы под свою ОС. 
2. Откройте нужный вам документ на сайте библиотеки открытого Русского географического общества (в модуле защищенного просмотра (ЗП) библиотеки)
3. Убедитесь, что ссылка имеет вид "https://elib.rgo.ru/safe-view/123456789/.../.../..."
4. Скопируйте название открытого файла (есть на странице со справкой о документе) и количество его страниц (отображается в в модуле ЗП)
5. Кайфуйте!


## Идеи на будущее
В будущем обновлении планирую достичь 90%+ покрытия юнит-тестированием и реализовать некоторые простые функции с правкой организации репозитория. 

##
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
├── README.ru.md
└── requirements.txt
```
