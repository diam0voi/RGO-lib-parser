# RGO-lib-parser: описание
![Current license: AGPLv3](https://www.gnu.org/graphics/agplv3-155x51.png)
Switch to ENG ---> [![switch to ENG](https://img.shields.io/badge/lang-en-red.svg?style=for-the-badge)](https://github.com/diam0voi/RGO-lib-parser/blob/main/README.md)


### Информативное
|        |                                                                                                                                                             |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Стэк** | [![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=ffe770)](https://www.python.org/) [![Pytest](https://img.shields.io/badge/Pytest-gray?style=flat-square&logo=pytest&logoColor=0a9edc)](https://pytest.org/) [![Ruff](https://img.shields.io/badge/Ruff-gray?style=flat-square&logo=ruff&logoColor=d7ff64)](https://astral.sh/ruff) [![uv](https://img.shields.io/badge/uv-gray?style=flat-square&logo=uv&logoColor=de5fe9)](https://astral.sh/uv) [![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196?logo=conventionalcommits&logoColor=fe5196&style=flat-square)](https://conventionalcommits.org) <br> [![SemVer](https://img.shields.io/github/v/release/diam0voi/RGO-lib-parser?label=SemVer&color=3f4551&style=flat-square&logo=semver)](https://semver.org/) [![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=flat-square&logo=pre-commit&logoColor=#fab040)](https://pre-commit.com/) [![Commitizen](https://img.shields.io/badge/Commitizen-friendly-brightgreen?style=flat-square&)](https://commitizen-tools.github.io/commitizen/) |
| **Метрики** | [![Test Status](https://img.shields.io/github/actions/workflow/status/diam0voi/RGO-lib-parser/ci.yml?branch=main&label=tests&logo=github&style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/diam0voi/RGO-lib-parser/graph/badge.svg)](https://codecov.io/gh/diam0voi/RGO-lib-parser) [![Codacy Badge](https://app.codacy.com/project/badge/Grade/e25b481825024b33864c2c7311ee7fa8)](https://app.codacy.com/gh/diam0voi/RGO-lib-parser/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade) [![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/diam0voi/RGO-lib-parser/badge)](https://scorecard.dev/viewer/?uri=github.com/diam0voi/RGO-lib-parser)|
| **Совместимость** | ![Python Version](https://img.shields.io/badge/python-3.9+-brightgreen?logo=python&logoColor=ffe770&style=flat-square) ![Windows X](https://img.shields.io/badge/Windows%20X%2010+-0078D6?style=flat-square) ![macOS X](https://img.shields.io/badge/MacOS%20X%2013+-000000?logo=macos&logoColor=white&style=flat-square&logoSize=auto) ![Ubuntu X](https://img.shields.io/badge/Ubuntu%20X%2022+-E95420?logo=ubuntu&logoColor=white&style=flat-square&logoSize=auto) |
| **Другое** |  [![GitHub last commit](https://img.shields.io/github/last-commit/diam0voi/RGO-lib-parser?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/commits/main) ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/diam0voi/RGO-lib-parser/total?style=flat-square) [![GitHub repo size](https://img.shields.io/github/repo-size/diam0voi/RGO-lib-parser.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/) [![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/diam0voi/RGO-lib-parser.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/)  |
| | | 


### Простенькая штучка для простенькой задачки
По своей сути - это парсер, предназначенный для конкретного сайта с его отчасти причудливым форматом хранения данных. На нём собраны сканы редких экземпляров очень нишевых исторических литературных источников, которые вам могут понадобится, скажем, для интерактивной панели на выставке. Но просто так вам их не получить! Вы можете только смотреть! Так родилась идея автоматизировать процесс ручного создания целой горы скриншотов: я решил облегчить жизнь знакомым, которым пришлось этим заниматься. 

Это мой первый проект ТАКОГО уровня, так что не удивляйтесь коммитам в 2 строчки и совершенно нелепым косякам, со временем я точно освоюсь и чувство кринжа пройдёт (нет).

Важно: я НЕ ЯВЛЯЮСЬ как владельцем сайта библиотеки, так и правообладателем публикуемого на нём материала, все права защищены и принадлежат текущим владельцам сайта! 


## Примеры работы на разных этапах
![example-cycle-gif](https://github.com/user-attachments/assets/292932c0-d829-407f-b978-e20163b64dff)

---
![Example-start](https://github.com/user-attachments/assets/4ec54270-8c15-4eb1-b83e-0956a8c59e79)

![Example-process](https://github.com/user-attachments/assets/6040a85c-3043-4d02-ad77-e4095adf2ec0)

![Example-result](https://github.com/user-attachments/assets/f57566c9-c692-4e68-91f5-5f2589cf34dc)


## Как воспользоваться

Ниже привёл инструкции по непосредственно запуску ПО для различных операционнок после загрузки соответствующего файла из раздела **Assets** последнего релиза.
Приложение сделано в формате Standalone Portable, строгое наличие языка разработки у вас (Python) **НЕ** требуется!

---

### Windows (`RGO_lib_parser_win64.exe`)

1.  **Скачивание:** скачайте файл `RGO_lib_parser_win64.exe` из релиза.
2.  **Запуск:** найдите у себя на компьютере этот файл и запустите.
3.  **Оповещение безопасности:** Встроенный защитник Windows 10+ SmartScreen наверняка покажет предупреждение ("Windows защитила ваш компьютер"), потому что я не имел оффициального (и дорогущего) сертификата подписи кода.
    *   Если оно вам встретилось, нажмите на **"Подробнее"**.
    *   После этого появится кнопка **"Выполнить в любом случае"**, нажимайте.
    *   Это нужно только при первом запуске. При желании отключите у себя насовсем, инструкции в интернете.

---

### macOS (`RGO_lib_parser_macOS.zip`)

1.  **Скачивание:** скачайте файл `RGO_lib_parser_macOS.zip` из релиза.
2.  **Распаковка:** найдите у себя на компьютере этот архив `.zip` и распакуйте просто двойным кликом.
3.  **Запуск:**
    *   Найдите в распакованном архиве файл `RGO Lib Parser.app`.
    *   Рекомендовано: перетащите этот файл из "Загрузки" в вашу папку "Приложения".
    *   **Важно: правый клик (или `Control`-клик)** по иконке `RGO Lib Parser.app`.
4.  **Оповещение безопасности:** вы наверняка увидите предупреждение, что приложение у вас от неопределённого разработчика, потому что я не обладаю оффициальным (и дорогущим) Apple Developer ID. Но так как вы открываете через "расширенный доступ", вы увидите кнопку **"Открыть"** в диалоговом окне, нажимайте. После этого запуск доступен двойным кликом.

---

### Linux (пока Debian-based - `RGO_lib_parser_ubuntu`)

1.  **Скачивание:** скачайте файл `RGO_lib_parser_ubuntu` (он без расширения) из релиза.
2.  **Работа в терминале:** запустите свой терминал.
3.  **Перемещение:** перейдите в директорию, где оказался скачанный файл (e.g., `cd ~/Downloads` or `cd ~/Загрузки`).
4.  **Флаг исполняемости:** предоставьте файлу разрешение на запуск командой: `chmod +x RGO_lib_parser_ubuntu`
    *(Обычно это нужно только при первом запуске).*
5.  **Запуск:** запустите приложение командой: `./RGO_lib_parser_ubuntu`
---

## Основные инструкции
1. Скачайте последнюю версию программы под свою ОС.
2. Откройте нужный вам документ на сайте библиотеки открытого Русского географического общества (в модуле защищенного просмотра (МЗП)).
3. Убедитесь, что ссылка имеет вид "https://elib.rgo.ru/safe-view/123456789/.../.../.../":   
    ![Example-link](https://github.com/user-attachments/assets/5d3456be-0ecd-42a0-9f6c-de6912b13f45)
4. Скопируйте имя файла на сайте (есть на само́й странице документа или в МЗП) и **реальное** кол-во страниц (в МЗП):   
    ![Example-what-to-copy](https://github.com/user-attachments/assets/1741be2b-ad76-4259-955c-d880832ebbcc)
5. Кайфуйте!


## Идеи на будущее
Думаю внедрить авто-распознавание пустых (несодержательных) разворотов, консольный интерфейс, прикреплять файлы SBOM и SLSA к релизам, покрыть уже интеграционными тестами и пофиксить всё-всё-всё!

## Схемы-деревья репозитория и зависимостей проекта
```
RGO-lib-parser v1.4
├── .github/
│   ├── ISSUE_TEMPLATE/ 
│       ├── bug_report.yml
│       ├── config.yml
│       ├── documentation.yml
│       └── feature_request.yml
│   ├── workflows/
│       ├── .codecov.yml
│       ├── bandit.yml
│       ├── ci.yml
│       ├── crossbuild-release.yml
│       ├── dependabot.yml
│       ├── labeler.yml
│       ├── pull_request_template.md
│       └── scorecard.yml
│   ├── CODEOWNERS(.bib)
│   └── labels.yml
│
│
├── assets/
│   ├── macapp_lilacbook.icns
│   ├── winapp_lilacbook.ico
│   └── window_bnwbook.png
│
│
├── scripts/
│   └── run_app.py
│
│
├── src/
│   ├── __init__.py
│   ├── app_state.py
│   ├── config.py
│   ├── gui.py
│   ├── image_processing.py
│   ├── logic.py
│   ├── main.py
│   ├── settings_manager.py
│   ├── task_manager.py
│   ├── types.py
│   ├── ui_builder.py
│   └── utils.py
│
│
├── tests/        
│   ├── __init__.py
│   ├── test_app_state.py
│   ├── test_config.py
│   ├── test_image_processing.py
│   ├── test_logic.py
│   ├── test_main.py
│   ├── test_settings_manager.py
│   ├── test_task_manager.py
│   ├── test_types.py
│   └── test_utils.py
│
│
├── v0.1 separated/        
│   ├── sdloady_RGO_lib.py
│   └── spready_RGO_lib.py
│
│
├── .codacy.yaml
├── .gitattributes(.bib)
├── .gitignore(.bib)
├── .markdownlint.yaml
├── .pre-commit-config.yaml
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── CONTRIBUTING.ru.md
├── LICENSE(.bib)
├── pyproject.toml
├── README.md
├── README.ru.md
├── SECURITY.md
├── tox.ini
└── uv.lock
```
---
```
RGO-lib-parser v1.4
├── pillow v11.2.1
├── requests v2.32.3
│   ├── certifi v2025.1.31
│   ├── charset-normalizer v3.4.1
│   ├── idna v3.10
│   └── urllib3 v2.4.0
│
├── coverage[toml] v6.5.0 (extra: dev)
├── coveralls v3.3.1 (extra: dev)
│   ├── coverage v6.5.0
│   ├── docopt v0.6.2
│   └── requests v2.32.3 (*)
│
├── lxml v5.3.2 (extra: dev)
├── mypy v1.15.0 (extra: dev)
│   ├── mypy-extensions v1.0.0
│   └── typing-extensions v4.13.2
│
├── pre-commit v3.8.0 (extra: dev)
│   ├── cfgv v3.4.0
│   ├── identify v2.6.9
│   ├── nodeenv v1.9.1
│   ├── pyyaml v6.0.2
│   └── virtualenv v20.30.0
│       ├── distlib v0.3.9
│       ├── filelock v3.18.0
│       └── platformdirs v4.3.7
│
├── pytest v8.3.5 (extra: dev)
│   ├── colorama v0.4.6
│   ├── iniconfig v2.1.0
│   ├── packaging v24.2
│   └── pluggy v1.5.0
│
├── pytest-cov v5.0.0 (extra: dev)
│   ├── coverage[toml] v6.5.0
│   └── pytest v8.3.5 (*)
│
├── ruff v0.11.5 (extra: dev)
├── types-pillow v10.2.0.20240822 (extra: dev)
└── types-requests v2.32.0.20250328 (extra: dev)
    └── urllib3 v2.4.0
(*) Package tree already displayed
```
