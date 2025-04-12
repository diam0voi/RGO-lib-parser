# Contributing to RGO-lib-parser

На Русском --> [![Ru](https://img.shields.io/badge/lang-ru-red.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/blob/main/CONTRIBUTING.ru.md)



### Welcome future contributor!

We're happy to see you're willing to make the project better. Thank you in advance for your contribution to RGO-lib-parser. This guide will help you get your environment set up quickly and outline how to contribute effectively.

We value constructive community interaction over technical acumen and strive to make RGO-lib-parser an inclusive environment, great even for first-time open-source contributors. Please be kind to one another.

## Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python:** Version 3.9 or higher. [Download from python.org](https://www.python.org/downloads/) (make sure to check 'Add Python to PATH' during installation on Windows, as `pipx` might need it).
2.  **Git:** The version control system. [Download Git](https://git-scm.com/downloads/).
3.  **pipx:** A tool to install and run Python applications in isolated environments. If you don't have it, install it first (requires Python and pip):
    ```bash
    python -m pip install --user pipx
    python -m pipx ensurepath
    ```
    *(You might need to restart your terminal after running `ensurepath` for the PATH changes to take effect)*.
    [More pipx installation options](https://pipx.pypa.io/stable/installation/).
4.  **Core Development Tools (uv & tox):** Install them using `pipx`:
    ```bash
    pipx install uv
    pipx install tox
    ```
    *(These commands should now be available globally)*.

## Setup

After meeting the prerequisites, setting up the project involves these steps:

1.  **Clone the repository:** (If you haven't already)
    ```bash
    git clone https://github.com/diam0voi/RGO-lib-parser.git
    cd RGO-lib-parser
    ```

2.  **Create virtual environment and install dependencies:**
    Run this single command:
    ```bash
    uv run setup
    ```
    This command will:
    *   Create (if it doesn't exist) a virtual environment in the `.venv` directory.
    *   Install all required dependencies (including development dependencies) into this environment using `uv pip install`.

3.  **Activate the virtual environment:**
    Before running code or development commands, activate the created environment:
    *   **Linux / macOS (bash/zsh):**
        ```bash
        source .venv/bin/activate
        ```
    *   **Windows (CMD):**
        ```bat
        .venv\Scripts\activate.bat
        ```
    *   **Windows (PowerShell):**
        ```powershell
        .venv\Scripts\Activate.ps1
        # If the command fails, you might need to change the Execution Policy:
        # Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
        ```
    You'll know the environment is active when you see `(.venv)` at the beginning of your terminal prompt.

## Running Tasks

All common development tasks are run via `uv run` (or directly if the environment is activated):

*   **Run the application:** `uv run app`
*   **Run tests (pytest):** `uv run test`
*   **Run linter and formatting checks (ruff):** `uv run lint`
*   **Run type checks (mypy via tox):** `uv run typecheck`
*   **Run all checks (like in CI):** `uv run check-all`
*   **Show available commands:** `uv run help`

## Development Workflow

RGO-lib-parser uses the [GitHub flow](https://guides.github.com/introduction/flow/) as the main versioning workflow.

1.  **Fork** the repository on GitHub.
2.  Clone *your* fork locally.
3.  **Create a new branch** for each feature, fix, or improvement: `git checkout -b feature/your-feature` or `fix/your-fix`. It is very important to separate new features or improvements into separate feature branches.
4.  Write your code and add tests for your changes.
5.  **Ensure all checks pass locally:** `uv run lint`, `uv run test`, `uv run typecheck`.
6.  Commit your changes (`git commit -m "feat: Describe your feature"`) and push them to *your* fork (`git push origin feature/your-feature`).
7.  **Send a Pull Request (PR)** from each feature branch to the **main** branch of the original repository.
8.  Ensure all CI checks (GitHub Actions) pass on your PR.
9.  Wait for a code review and address any feedback.

## Code Style and Checks

*   We use `ruff` for linting and formatting, `mypy` (via `tox`) for type checking, and `pytest` for testing. Configurations are in `pyproject.toml` and `tox.ini`.
*   Please run checks before submitting a PR.
*   All pull requests **SHOULD** adhere to the [Conventional Commits specification](https://conventionalcommits.org/).

## License Agreement

By submitting a patch (Pull Request), you agree that your contribution will be licensed under the [GNU Affero General Public License v3.0 only (AGPL-3.0-only)](LICENSE). Furthermore, if the project license changes in the future, we will assume you agree with the change unless you object in a timely manner after the change is announced.

## Code of Conduct

Please review and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md) in all interactions within the project.

## Issue Tracker

Found a bug or have an idea? Check the [existing Issues](https://github.com/diam0voi/RGO-lib-parser/issues) first. If not, feel free to open a new one!

### Thank you, and we look forward to your contributions!