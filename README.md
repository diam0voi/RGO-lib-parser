# RGO-lib-parser: description
На русском --> [![Ru](https://img.shields.io/badge/lang-ru-red.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/blob/main/README.ru.md)

### Simple thing for a simple task
At its core - you're looking at the parser designed for a specific site with its somewhat bizarre data storage format. This site, however, contains scans of rare and very niche historical literary sources that you may need, as for example, for an interactive panel at certain exhibition. But you can't just get them! You forced to only watch! So the idea was born to automate the process of manually creating a whole plethora of screenshots: I decided to make life easier for my bros who had to do this. 

This is my first project of SUCH a level, so don't be surprised by 2-line commits and ridiculous bugs, I'll definitely get used to it over time and the feeling of cringe will pass (no).

|        |                                                                                                                                                             |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Quality** | [![Test Status](https://img.shields.io/github/actions/workflow/status/diam0voi/RGO-lib-parser/ci.yml?branch=main&label=tests&logo=github&style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/actions/workflows/ci.yml) [![Coverage Status](https://coveralls.io/repos/github/diam0voi/RGO-lib-parser/badge.svg?branch=main)](https://coveralls.io/github/diam0voi/RGO-lib-parser?branch=main) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black) [![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits&logoColor=white&style=flat-square)](https://conventionalcommits.org) ![SemVer](https://img.shields.io/github/v/release/diam0voi/RGO-lib-parser?label=SemVer&color=darkblue&&style=flat-square) |
| **Compatibility** | ![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13+-green?logo=python&logoColor=yellow&style=flat-square) ![Windows](https://img.shields.io/badge/Windows%2010+-0078D6?style=flat-square) ![macOS](https://img.shields.io/badge/MacOS%2015+-000000?logo=macos&logoColor=white&style=flat-square) ![Ubuntu](https://img.shields.io/badge/Ubuntu%2024+-E95420?logo=ubuntu&logoColor=white&style=flat-square) |
| **Other**       |  [![GitHub last commit](https://img.shields.io/github/last-commit/diam0voi/RGO-lib-parser?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/commits/main) ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/diam0voi/RGO-lib-parser/total?style=flat-square) [![GitHub repo size](https://img.shields.io/github/repo-size/diam0voi/RGO-lib-parser.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/) [![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/diam0voi/RGO-lib-parser.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/)  |
| | | 

## How the app works (example)
![image](https://github.com/user-attachments/assets/4ec54270-8c15-4eb1-b83e-0956a8c59e79)

![image](https://github.com/user-attachments/assets/6040a85c-3043-4d02-ad77-e4095adf2ec0)

![image](https://github.com/user-attachments/assets/f57566c9-c692-4e68-91f5-5f2589cf34dc)


## Instructions:
1. Download and run the program for your OS
2. Open the document you need on the website of the open Russian Geographical Society (Obshestvo) library (in the library's protected view (PV) module)
3. Make sure the link looks like "https://elib.rgo.ru/safe-view/123456789/.../.../..."
4. Enter the name of the open file (you can see it on the main page) and the number of its pages (displayed in the PV module)
5. Enjoy!


## Ideas for future
Add auto-recognition of blank (non-useful) spreads, CLI interface, and integration tests!

##
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
│       ├── ci.yml
│       ├── crossbuild-release.yml
│       ├── dependabot.yml
│       ├── labeler.yml
│       └── pull_request_template.md
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

```
RGO-lib-parser v1.4
├── pillow v11.2.1
├── requests v2.32.3
│   ├── certifi v2025.1.31
│   ├── charset-normalizer v3.4.1
│   ├── idna v3.10
│   └── urllib3 v2.4.0
├── coverage[toml] v6.5.0 (extra: dev)
├── coveralls v3.3.1 (extra: dev)
│   ├── coverage v6.5.0
│   ├── docopt v0.6.2
│   └── requests v2.32.3 (*)
├── lxml v5.3.2 (extra: dev)
├── mypy v1.15.0 (extra: dev)
│   ├── mypy-extensions v1.0.0
│   └── typing-extensions v4.13.2
├── pre-commit v3.8.0 (extra: dev)
│   ├── cfgv v3.4.0
│   ├── identify v2.6.9
│   ├── nodeenv v1.9.1
│   ├── pyyaml v6.0.2
│   └── virtualenv v20.30.0
│       ├── distlib v0.3.9
│       ├── filelock v3.18.0
│       └── platformdirs v4.3.7
├── pytest v8.3.5 (extra: dev)
│   ├── colorama v0.4.6
│   ├── iniconfig v2.1.0
│   ├── packaging v24.2
│   └── pluggy v1.5.0
├── pytest-cov v5.0.0 (extra: dev)
│   ├── coverage[toml] v6.5.0
│   └── pytest v8.3.5 (*)
├── ruff v0.11.5 (extra: dev)
├── types-pillow v10.2.0.20240822 (extra: dev)
└── types-requests v2.32.0.20250328 (extra: dev)
    └── urllib3 v2.4.0
(*) Package tree already displayed
```