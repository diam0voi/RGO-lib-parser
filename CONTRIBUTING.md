# Contributing to RGO-lib-parser

На Русском --> [![Ru](https://img.shields.io/badge/lang-ru-red.svg?style=flat-square)](https://github.com/diam0voi/RGO-lib-parser/blob/main/CONTRIBUTING.ru.md)


### Welcome future contributor!

I'm happy to see you're willing to make the project better. Thank you in advance for your contribution to RGO-lib-parser. This guide will help you get your environment set up quickly and outline how to contribute effectively.

We value constructive community interaction over technical acumen and strive to make RGO-lib-parser an inclusive environment, great even for first-time open-source contributors. Please be kind to one another.

## Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python:** Version 3.9 or higher. [Download from python.org](https://www.python.org/downloads/) (make sure to check 'Add Python to PATH' during installation on Windows).
2.  **Git:** The version control system. [Download Git](https://git-scm.com/downloads/).
3.  **uv:** My beloved package manager and task runner. Install it after Python:
    ```bash
    # Use the pip that comes with Python
    pip install uv
    # Or (if pip is not in PATH):
    # python -m pip install uv
    ```
    Ensure the directory containing the `uv` executable is in your system's PATH.

## Setup

After meeting the prerequisites, setting up the project involves these steps:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/diam0voi/RGO-lib-parser.git
    cd RGO-lib-parser
    ```

2.  **Create virtual environment and install dependencies:**
    We use `uv` to manage the environment and dependencies. Run this single command:
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

*   **Run the application:**
    ```bash
    uv run app
    # or from an active venv: python -m src.main
    ```
*   **Run tests (pytest):**
    ```bash
    uv run test
    # or from an active venv: pytest
    ```
*   **Run linter and formatting checks (ruff):**
    ```bash
    uv run lint
    # or from an active venv: ruff check src tests && ruff format --check src tests
    ```
*   **Run type checks (mypy via tox):**
    ```bash
    uv run typecheck
    # or from an active venv: tox -e typing
    ```
*   **Run all checks (like in CI):**
    ```bash
    uv run check-all
    # or from an active venv: tox
    ```
*   **Show available commands:**
    ```bash
    uv run help
    # or: uv run --list
    ```

## Development Workflow

RGO-lib-parser uses the [GitHub flow](https://guides.github.com/introduction/flow/) as the main versioning workflow.

1.  **Fork** the repository on GitHub.
2.  Clone *your* fork locally.
3.  **Create a new branch** for each feature, fix, or improvement: `git checkout -b feature/your-feature` or `fix/your-fix`. It is very important to separate new features or improvements into separate feature branches.
4.  Write your code and add tests for your changes.
5.  **Ensure all checks pass locally:**
    *   Format the code: `ruff format src tests` (optional, `uv run lint` includes a check)
    *   Run the linter: `uv run lint`
    *   Run tests: `uv run test`
    *   Run type checks: `uv run typecheck`
6.  Commit your changes (`git commit -m "feat: Describe your feature"`) and push them to *your* fork (`git push origin feature/your-feature`).
7.  **Send a Pull Request (PR)** from each feature branch to the **main** branch of the original repository. This allows us to review and pull in new features or improvements more efficiently.
8.  Ensure all CI checks (GitHub Actions) pass on your PR.
9.  Wait for a code review and address any feedback.

## Code Style and Checks

*   We use `ruff` for linting and formatting, `mypy` (via `tox`) for type checking, and `pytest` for testing. Configurations are in `pyproject.toml` and `tox.ini`.
*   Please run `uv run lint`, `uv run test`, and `uv run typecheck` before submitting a PR to ensure your code adheres to the project's standards.
*   All pull requests **SHOULD** adhere to the [Conventional Commits specification](https://conventionalcommits.org/). Use prefixes like `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.

## License Agreement

By submitting a patch (Pull Request), you agree that your contribution will be licensed under the [GNU Affero General Public License v3.0 only (AGPL-3.0-only)](LICENSE). Furthermore, if the project license changes in the future, we will assume you agree with the change unless you object in a timely manner after the change is announced.

## Code of Conduct

Please review and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md) in all interactions within the project.

## Issue Tracker

Found a bug or have an idea for a new feature? Check the [existing Issues](https://github.com/diam0voi/RGO-lib-parser/issues) first to see if it's already being discussed. If not, feel free to open a new one!

### Thank you, and we look forward to your contributions!