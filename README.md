# Description of the RGO-lib-parser: 
На русском --> [![Ru](https://img.shields.io/badge/lang-ru-red.svg?style=for-the-badge)](https://github.com/diam0voi/RGO-lib-parser/blob/main/README.ru.md)


|        |                                                                                                                                                             |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Stack** | [![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=ffe770)](https://www.python.org/) [![Pytest](https://img.shields.io/badge/Pytest-gray?style=flat-square&logo=pytest&logoColor=0a9edc)](https://pytest.org/) [![Ruff](https://img.shields.io/badge/Ruff-gray?style=flat-square&logo=ruff&logoColor=d7ff64)](https://astral.sh/ruff) [![uv](https://img.shields.io/badge/uv-gray?style=flat-square&logo=uv&logoColor=de5fe9)](https://astral.sh/uv) [![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196?logo=conventionalcommits&logoColor=fe5196&style=flat-square)](https://conventionalcommits.org) <br> [![SemVer](https://img.shields.io/github/v/release/diam0voi/RGO-lib-parser?label=SemVer&color=3f4551&style=flat-square&logo=semver)](https://semver.org/) [![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=flat-square&logo=pre-commit&logoColor=#fab040)](https://pre-commit.com/) [![Commitizen](https://img.shields.io/badge/commitizen-friendly-brightgreen?style=flat-square&)](https://commitizen-tools.github.io/commitizen/) |
| **Quality** | [![Test Status](https://img.shields.io/github/actions/workflow/status/diam0voi/RGO-lib-parser/ci.yml?branch=main&label=tests&logo=github&style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/diam0voi/RGO-lib-parser/graph/badge.svg)](https://codecov.io/gh/diam0voi/RGO-lib-parser) [![Codacy Badge](https://app.codacy.com/project/badge/Grade/e25b481825024b33864c2c7311ee7fa8)](https://app.codacy.com/gh/diam0voi/RGO-lib-parser/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade) [![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/diam0voi/RGO-lib-parser/badge)](https://scorecard.dev/viewer/?uri=github.com/diam0voi/RGO-lib-parser)|
| **Compatibility** | ![Python Version](https://img.shields.io/badge/python-3.9+-brightgreen?logo=python&logoColor=ffe770&style=flat-square) ![Windows X](https://img.shields.io/badge/Windows%20X%2010+-0078D6?style=flat-square) ![macOS X](https://img.shields.io/badge/MacOS%20X%2013+-000000?logo=macos&logoColor=white&style=flat-square&logoSize=auto) ![Ubuntu X](https://img.shields.io/badge/Ubuntu%20X%2022+-E95420?logo=ubuntu&logoColor=white&style=flat-square&logoSize=auto) |
| **Other** |  [![GitHub last commit](https://img.shields.io/github/last-commit/diam0voi/RGO-lib-parser?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/commits/main) ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/diam0voi/RGO-lib-parser/total?style=flat-square) [![GitHub repo size](https://img.shields.io/github/repo-size/diam0voi/RGO-lib-parser.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/) [![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/diam0voi/RGO-lib-parser.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/)  |
| | | 


### Simple thing for a simple task
At its core - you're looking at the parser designed for a specific site with somewhat bizarre data storage format. This site, however, contains scans of rare and very niche historical literary sources that you may need, as for example, for an interactive panel at certain exhibition. But you can't just get them! You forced to only watch! So the idea was born to automate the process of manually creating a whole plethora of screenshots: I decided to make life easier for my bros who had to do this. 

This is my first project of SUCH a level, so don't be surprised by 2-line commits and ridiculous bugs, I'll definitely get used to it over time and the feeling of cringe will pass (no).

Important: I'm NOT the owner of the site nor of the library materials therein, all rights reserved and belongs to the RGO lib owners! 


## Illustrations of app working
![example-cycle-gif](https://github.com/user-attachments/assets/292932c0-d829-407f-b978-e20163b64dff)

![Example-start](https://github.com/user-attachments/assets/4ec54270-8c15-4eb1-b83e-0956a8c59e79)

![Example-process](https://github.com/user-attachments/assets/6040a85c-3043-4d02-ad77-e4095adf2ec0)

![Example-result](https://github.com/user-attachments/assets/f57566c9-c692-4e68-91f5-5f2589cf34dc)


## How to Run

Below are instructions for running the application on different operating systems after downloading the corresponding file from the **Assets** section of this release.  
The application is made in the Standalone Portable format, strict availability of the development language (Python) **is NOT** required!

---

### Windows (`RGO_lib_parser_win64.exe`)

1.  **Download:** Download the `RGO_lib_parser_win64.exe` file from release.
2.  **Run:** Find the downloaded `.exe` file (usually in your "Downloads" folder) and double-click it to run.
3.  **Security Warning:** Windows Defender SmartScreen might show a warning ("Windows protected your PC") because the application is not signed with an official (and expensive) code signing certificate.
    *   If you see this warning, click on **"More info"**.
    *   Then, click the **"Run anyway"** button that appears.
    *   This only needs to be done the first time you run the application.

---

### macOS (`RGO_lib_parser_macOS.zip`)

1.  **Download:** Download the `RGO_lib_parser_macOS.zip` file from release.
2.  **Unzip:** Find the downloaded `.zip` file (usually in "Downloads") and double-click it. macOS will automatically unzip it, creating the `RGO Lib Parser.app` file nearby.
3.  **(Optional but Recommended):** Drag `RGO Lib Parser.app` from "Downloads" to your "Applications" folder.
4.  **First Run (Important!):**
    *   Locate `RGO Lib Parser.app` (in Downloads or Applications).
    *   **Right-click** (or `Control`-click) the `RGO Lib Parser.app` icon.
    *   Select **"Open"** from the context menu.
5.  **Security Confirmation:** You might see a warning about the app being from an unidentified developer because it's downloaded from the internet and not signed with an Apple Developer ID. Since you used "Open" via right-click, you should see an **"Open"** button in this dialog. Click it.
6.  **Subsequent Runs:** After opening it this way once, macOS will remember your choice, and you can launch `RGO Lib Parser.app` by double-clicking it like any other application.

---

### Linux (Ubuntu/Debian, etc. - `RGO_lib_parser_ubuntu`)

1.  **Download:** Download the `RGO_lib_parser_ubuntu` file (it has no extension) from release.
2.  **Open Terminal:** Launch your terminal application.
3.  **Navigate:** Go to the directory where you downloaded the file (e.g., `cd ~/Downloads` or `cd ~/Загрузки`).
4.  **Make Executable:** Grant the file permission to run: `chmod +x RGO_lib_parser_ubuntu`
    *(You usually only need to do this once after downloading).*
5.  **Run:** Execute the application from the terminal: `./RGO_lib_parser_ubuntu`
    *(The `./` is important - it tells the terminal to run the file in the current directory).*

## General instructions:
1. Download and run the program for your OS.
2. Open the document you need on the website of the open Russian Geographical Society (ru. "Obshestvo") library in the library's protected view (PV) module.
3. Make sure the link looks like "https://elib.rgo.ru/safe-view/123456789/.../.../.../": <br>
    ![Example-link](https://github.com/user-attachments/assets/5d3456be-0ecd-42a0-9f6c-de6912b13f45)
4. Copy/paste the name of the original file (accessible on the main page or in PV module) and the **actual** number of its pages (in PV module): <br>
    ![Example-what-to-copy](https://github.com/user-attachments/assets/1741be2b-ad76-4259-955c-d880832ebbcc)
5. Enjoy!


## Ideas for future
Add auto-recognition of blank (non-useful) spreads, CLI interface, integration tests, SBOM & SLSA files, and fixes, baby, fixes!

## Repository & dependencies trees 
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
