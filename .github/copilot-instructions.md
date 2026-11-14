# Repository Instructions for GitHub Copilot

## Project

- This repository is to publish GitHub Actions that check a pull request's title and description before it merges. It holds the checks as a Python package and no action exists yet.
- No pull request text may reach a shell through a `${{ }}` expression in a `run:` block. Read [SECURITY.md](../SECURITY.md) before changing a workflow.

## 1) High‑Level Details

- **Language:** Python 3.13+
- **Dependency Management:** `uv` (manages `.venv` in project root).
- **Task Runner:** `Makefile` is the primary entry point for all development tasks.

## 2) Build and Validation Information

- **Run All Checks:** `make check` (runs `make tidy`, the pre-commit hooks, and tests).
- **Testing:** `make test` (runs `pytest` with coverage).
- **Linting:** `make lint` (ruff check --fix).
- **Formatting:** `make format` (ruff format), `make tidy` (best-effort lint autofix + format), or `make tidy-all` (pre-commit + tidy).
- **Execution:** Always use `uv run <command>` to ensure execution within the virtual environment.

## 3) Project Layout and Architecture

- `src/pr_checks/`: The checks the actions are to run: `title` and `body`, each a module with a command line, on `subject` (the subject rules) and `findings` (how results print and are recorded).
- `scripts/`: Standalone scripts, not a package: the coverage report CI renders and `concat-gitignores.sh` (generates `.gitignore`).
- `tests/`: Test suite.
- `.specify/memory/constitution.md`: Project constitution (design principles, quality gates, coding standards).
- `pyproject.toml`: Project configuration, dependencies, and tool settings.
- `uv.lock`: Exact dependency versions.
- `.github/`: CI workflows and templates.

## 4) Conventional Commits and Contribution Workflow

### Commit Messages

Follow **Conventional Commits** format: `<type>(<scope>): <subject>`

- **Types:** `feat`, `fix`, `docs`, `style`, `test`, `build`, `ci`, `refactor`, `perf`, `chore`, `revert`
- **Imperative Mood:** Write subjects as commands (e.g., "add feature" not "added feature")
- **Lowercase Start:** The first character after the colon, and after a `[TICKET-123]` key if there is one, must be a lowercase letter. The commit-msg hook rejects any other start: write `add the API client`, not `API client added`.
- **Summary Length:** Keep the subject line under 51 characters (≤50)
- **Body Line Length:** Wrap body text at 72 characters
- **Atomic Commits:** One logical change per commit

- **Recommended Workflow:**
  1. **Setup:** `make develop`
  2. **Develop:** Write code and tests (TDD encouraged).
  3. **Verify:** Run `make check` before committing.

- **Documentation Sync:** Keep `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/CI.instructions.md`, and `README.md` in step with the code, in the same commit as the change.

---

Note to GitHub Copilot: Please trust these instructions and only perform additional searches if the information provided is incomplete or found to be in error.
