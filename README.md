# RGO-lib-parser: description
На русском ---> [![На Русском](https://img.shields.io/badge/lang-ru-red.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/blob/main/README.ru.md)

### Simple thing for a simple task
At its core - you're looking at the parser designed for a specific site with its somewhat bizarre data storage format. This site, however, contains scans of rare and very niche historical literary sources that you may need, as for example, for an interactive panel at certain exhibition. But you can't just get them! You forced to only watch! So the idea was born to automate the process of manually creating a whole plethora of screenshots: I decided to make life easier for my bros who had to do this. 

This is my first project of SUCH a level, so don't be surprised by 2-line commits and ridiculous bugs, I'll definitely get used to it over time and the feeling of cringe will pass (no).

|        |                                                                                                                                                             |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Quality** | [![Test Status](https://img.shields.io/github/actions/workflow/status/diam0voi/RGO-lib-parser/ci.yml?branch=main&label=tests&logo=github&style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/actions/workflows/ci.yml) [![Coverage Status](https://coveralls.io/repos/github/diam0voi/RGO-lib-parser/badge.svg?branch=main)](https://coveralls.io/github/diam0voi/RGO-lib-parser?branch=main) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black) [![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits&logoColor=white&style=flat-square)](https://conventionalcommits.org) |
| **Compatibility** | ![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13+-green?logo=python&logoColor=yellow&style=flat-square) ![Windows](https://img.shields.io/badge/Windows%2010+-0078D6?style=flat-square) ![macOS](https://img.shields.io/badge/MacOS%2015+-000000?logo=macos&logoColor=white&style=flat-square) ![Ubuntu](https://img.shields.io/badge/Ubuntu%2024+-E95420?logo=ubuntu&logoColor=white&style=flat-square) |
| **Other**       |  [![GitHub last commit](https://img.shields.io/github/last-commit/diam0voi/RGO-lib-parser?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/commits/main) [![GitHub repo size](https://img.shields.io/github/repo-size/diam0voi/RGO-lib-parser.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/) [![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/diam0voi/RGO-lib-parser.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/) ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/diam0voi/RGO-lib-parser/total?style=flat-square) |
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
In future update, it's planned to achieve 90%+ coverage with unit testing and implement some simple features with changed organization of the repo.

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
