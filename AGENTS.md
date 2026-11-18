# Agent Instructions for this Repository

## 1. Repository Identity & Purpose

- This repository is to publish GitHub Actions that check a pull request's title and description before it merges. It holds the check action, `action.yml`, and the comment action, `comment/action.yml`; the first release is to follow.
- **The actions will read text a pull request's author controls.** Such text must reach a shell through `env:` or a file, never through a `${{ }}` expression in a `run:` block; `tests/test_workflow_injection.py` fails on any such expression in a workflow or composite action here.
- **Write in defined terms.** Name the check, the input and the result. Avoid idiom and metaphor.
- **Use the present indicative only for what is true now.** Write a rule, a plan or a future state with a modal verb (_must_, _should_, _may_, _will_ with its date or trigger), so no reader takes it for a description.
- This project uses standard Python tooling (`uv`, `ruff`, `ty`, `basedpyright`, `pylint`, `pytest`).

## 2. Development Workflow

### Environment Setup

- The project uses `uv` for dependency management. `uv` automatically creates and manages a virtual environment (`.venv`) in the project root.
- **Execution:** Prefer `uv run` over direct `python` calls (e.g., use `uv run python -m mymodule` instead of `python -m mymodule`) to ensure the correct environment is used.
- Python version: defined in `.python-version` and `pyproject.toml`.

### Git Configuration

- **Git LFS:** `.gitattributes` stores images, PDFs, Word documents and audio in Git LFS. `make develop` runs `git lfs install --local --skip-repo` when `git-lfs` is installed, and `make sync-main` runs `git lfs pull`.
- **Blame Ignore:** `.git-blame-ignore-revs` lists style-only or other bulk commits for `git blame` to skip. `make develop` runs `git config blame.ignoreRevsFile .git-blame-ignore-revs`.

### Common Commands (Makefile)

The `Makefile` is the primary entry point for development tasks.

- **Install Dependencies:** `make develop` (installs dev deps and git hooks)
- **Run All Checks (CI):** `make check` (runs `make tidy`, the pre-commit hooks, and tests)
- **Run Tests:** `make test` (runs pytest with coverage)
- **Linting:** `make lint` (ruff check --fix)
- **Formatting:** `make format` (ruff format), `make tidy` (best-effort lint autofix + format), or `make tidy-all` (pre-commit + tidy)
- **Clean:** `make clean` (removes artifacts and caches)
- **Releases:** `make release-status` (where a release stands) and `make release-approve` (approve the waiting Release Tag run). [RELEASING.md](RELEASING.md) covers the flow.
- **Git Hooks:** `make enable-pre-commit` / `make disable-pre-commit`. Enabling auto-removes a local `core.hooksPath` if it's set to the default `.git/hooks` (a harmless leftover); a non-default value blocks with a remediation message (`git config --local --unset-all core.hooksPath`, or run `make develop WITH_HOOKS=false` to skip hook installation).

### Testing

- **Test-Driven Development (TDD):** Strongly encouraged. Write tests _before_ implementation to ensure requirements are met and code is robust.
- **Test Categories (Purpose):**
  - **Type 1: Executable Documentation:** Treat these tests like code snippets in tutorials. They should be **DAMP** (Descriptive And Meaningful Phrases) and well-commented. Place them "above the fold" in test files. These are meant for reading and understanding how to use the code.
  - **Type 2: Coverage & Reliability:** Focus on edge cases, path coverage, and confidence. These can be more **DRY** (Don't Repeat Yourself) but must remain readable. Ensure tests never fail opaquely.
- **What to Test:**
  - **Public Interfaces:** Test user-facing code thoroughly.
  - **Private Implementation:** Avoid testing private methods or classes directly; test them through the public interface.
- **Pytest Best Practices:**
  - **Fixtures:** Use `pytest` fixtures for setup/teardown (prefer `yield` fixtures). Use `conftest.py` for shared fixtures.
  - **Parametrization:** Use `@pytest.mark.parametrize` for data-driven testing to cover multiple scenarios efficiently.
  - **Markers:** Use markers to categorize tests, and register each one under `markers` in `pytest.toml` before using it: `--strict-markers` makes an unregistered marker such as `@pytest.mark.slow` a collection error.
  - **Style:** Prefer functional tests over class-based tests.
- Tests are located in `tests/`, and use `pytest`.

## 3. Project Structure

- `src/pr_checks/`: The checks: `title` and `body`, each a module with a command line, on `subject` (the subject rules) and `findings` (how results print and are written). `python -m pr_checks` (`__main__.py`) is what the action runs.
- `action.yml`: The check action. `.github/workflows/pr-checks.yml` runs it from each pull request's tree.
- `comment/`: The comment action, `action.yml`, and the script it runs, `post.sh`. `.github/workflows/pr-checks-comment.yml` runs it from the default branch when the PR checks workflow finishes.
- `scripts/`: Standalone scripts, not a package: `coverage_diff_report.py` (the coverage report CI renders), `concat-gitignores.sh` (generates `.gitignore`), `update-unreleased.sh` (refreshes the changelog's Unreleased section, with `lib/resolve-github-token.sh`; both copied unchanged from michen00/template), and `release/`, the release workflows' scripts.
- `CHANGELOG.md`: Generated by git-cliff from the conventional commits, as `cliff.toml` configures it. Release PR regenerates the whole file for each release.
- `tests/`: Test suite. `tests/release/approve-test.sh` tests `scripts/release/approve.sh` against a stub `gh`, and `tests/test_release_scripts.py` runs it.
- `.github/`: GitHub Actions workflows. [`.github/instructions/CI.instructions.md`](.github/instructions/CI.instructions.md) says which tests enforce the workflows' rules and which rules to keep by hand.
- `.specify/memory/constitution.md`: Project constitution (authoritative reference for design principles, quality gates, and coding standards).
- `pyproject.toml`: Project configuration (build, deps, tools).
- `uv.lock`: Locked dependencies.

### Configuration Files

- **Linting & Formatting:**
  - `.codespellrc`: Spell checking configuration. It converts British spellings to American.
  - `.editorconfig`: Editor configuration.
  - `.gitlint`: Git linting configuration.
  - `.markdownlint.yml`: Markdown linting configuration.
  - `.pre-commit-config.yaml`: Pre-commit hook definitions.
  - `.prettierrc`, `.prettierignore`: Prettier formats YAML and JSON; markdownlint owns Markdown.
  - `.pylintrc`: Configuration for `pylint`, which enables only the checks `ruff`, `ty` and `basedpyright` do not make.
  - `.ruff.toml`: Configuration for `ruff` (linting and formatting).
  - `.yamllint`: YAML linting configuration.
  - `_typos.toml`: Spell checking configuration.
  - `tombi.toml`: TOML formatting and linting configuration.
- **Testing:**
  - `pytest.toml`: Configuration for `pytest`.
  - `.coveragerc`: Coverage configuration.
- **Editor & Environment:**
  - `.vscode/settings.json`, `.vscode/extensions.json`: VS Code workspace settings and recommended extensions.
  - `.devcontainer/devcontainer.json`: Dev container definition.
  - `.python-version`: Specifies the Python version.
- **Type Checking:**
  - `ty.toml`: Configuration for `ty`.
  - `pyrightconfig.json`: Configuration for `basedpyright`, which enables only the checks `ty` does not make.
- **Git:**
  - `.gitignore`: Files to ignore. Generated by `scripts/concat-gitignores.sh`; regenerate it rather than editing it by hand.
  - `scripts/custom.gitignore`: Project-specific ignore patterns, appended verbatim to the end of the generated `.gitignore`. New patterns go here.
  - `.gitattributes`: Git attribute settings.
  - `.git-blame-ignore-revs`: Revisions to ignore in blame.

## 4. Contribution Guidelines

### Commit Messages

Follow **Conventional Commits** format: `<type>(<scope>): <subject>`

- **Types:** `feat`, `fix`, `docs`, `style`, `test`, `build`, `ci`, `refactor`, `perf`, `chore`, `revert`
- **Imperative Mood:** Write subjects as commands (e.g., "add feature" not "added feature")
- **Lowercase Start:** The first character after the colon, and after a `[TICKET-123]` key if there is one, must be a lowercase letter. The commit-msg hook rejects any other start: write `add the API client`, not `API client added`.
- **Summary Length:** Keep the subject line under 51 characters (≤50)
- **Body Line Length:** Wrap body text at 72 characters
- **Atomic Commits:** One logical change per commit

**Example:**

```text
feat(title): reject a trailing period

A subject is a sentence fragment, and the squash commit takes the
title as its subject, so a trailing period ends up on main.
```

- **Code Style:** Enforced by `ruff` and `ty`, with `basedpyright` and `pylint` running only the checks those two do not make.
- **Verification:** Run `make check` to perform final checks (formatting, linting, type checking, pre-commit hooks, and tests) after making code changes.
- **Dependencies:** The package's one runtime dependency is markdown-it-py, which the body check uses to find code blocks. Another must be justified in its pull request, because the actions will install it on every run.
- **Python Idioms:**
  - **Return Values:** Use `NamedTuple` (or `dataclass`) for return values with more than 3 elements, instead of plain tuples.
  - **Enums:** Use `StrEnum` (Python 3.11+) and `auto()` for string-based enumerations.
  - **Path Manipulation:** Prefer `pathlib.Path` over `os.path` or string manipulation for file system paths.
  - **Module Exports (`__all__`):** Define `__all__` as a tuple (not list) to control exports. Omit parentheses if it fits on one line. Place it near the top of the file, immediately below the docstring (or `from __future__` imports).
- **Type Hints:**
  - Use modern type hints (Python 3.12+) for all function signatures (e.g., `list[str]`, `str | None`).
  - Annotate class attributes and significant variables.
- **Documentation:**
  - **Syncing:** Keep `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/CI.instructions.md`, and `README.md` in step with the code, in the same commit as the change. `CLAUDE.md` imports this file.
  - Follow **Google-style** docstrings.
  - **Modules:** Include docstrings at the module level.
  - **Classes:** All classes must have docstrings.
  - **Constants & Enums:** Document constants and Enum members.
  - **Functions & Methods:**
    - **`Args:` Section:** Use judiciously. Do not include an `Args:` section just to list argument names.
    - **When to use `Args:`:** Only if it adds material value (e.g., critical code, complex/opaque logic, special gotchas, or non-obvious parameters).
    - **No Redundancy:** If you do include `Args:`, do not repeat information already clear from the signature (like types or self-explanatory names).

## 5. Specific Task Instructions

### Adding a Dependency

1. Add it to `pyproject.toml`, under `[project] dependencies` or one of the `[dependency-groups]`: `ci` (nox and pre-commit, for CI's jobs; `dev` includes it), `dev` or `test`.
2. Run `uv lock` (or `make develop` which usually handles sync).

### Modifying CI

- Edit the workflow under `.github/workflows/`, and update `.github/instructions/CI.instructions.md` in the same commit.
- `tests/test_ci_jobs.py`, `tests/test_release_workflows.py`, `tests/test_workflow_caches.py`, `tests/test_workflow_injection.py`, `tests/test_workflow_pins.py` and `tests/test_workflows.py` pin the workflows' properties. Change a workflow so they still pass; do not change them to fit the workflow.
