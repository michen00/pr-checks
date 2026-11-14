# pr-checks

[![Build Status](https://img.shields.io/github/actions/workflow/status/michen00/pr-checks/CI.yml?branch=main&style=plastic)](https://github.com/michen00/pr-checks/actions/workflows/CI.yml)
[![License](https://img.shields.io/github/license/michen00/pr-checks?style=plastic)](LICENSE)

GitHub Actions that check a pull request's title and description before it merges.

## Status

Pre-release. As of 2026-11-14 the check action is here but no version is tagged, and the action that posts the findings as a comment is to follow.

## What it checks

An error fails the step; a warning is an annotation and does not.

- **The title** must be a Conventional Commit subject, because a squash merge makes it the commit's subject. A malformed type or scope, a title over the maximum length, a trailing period, or a capital first letter is an error. A first word that may not be imperative, such as `added`, is a warning.
- **The body** may not hold a fenced code block without a language tag, which is an error. A missing section the caller asked for, an unfilled `<placeholder>`, a TBD or TODO marker, or a markdownlint directive comment is a warning. Code blocks and code spans are not searched for leftovers.

A pull request whose author's login ends in `[bot]`, such as Dependabot's, is not checked.

## Usage

```yaml
name: PR checks
on:
  pull_request:
    types: [opened, edited, synchronize, reopened]
permissions:
  contents: read
jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: michen00/pr-checks@v1 # once v1 is released
        with:
          required-sections: |
            Summary
            Testing
```

The action checks out nothing. It runs on the runner's own `python3`, which must be 3.12 or later; CI tries it on `ubuntu-24.04` and `ubuntu-latest`.

| Input | Default | Meaning |
| --- | --- | --- |
| `max-length` | `50` | The most characters the title may have, or `off` |
| `required-sections` | none | Level-two headings the body should have, one per line |
| `check-title`, `check-body` | `true` | Whether to run each check |
| `skip-bot-authors` | `true` | Whether to check nothing when the author's login ends in `[bot]` |
| `warn-plan-ids` | `false` | Whether to warn on a plan identifier such as `Phase 2` or `S3` in the title |
| `upload-findings` | `true` | Whether to upload the findings as an artifact, for the comment action |
| `artifact-name` | `pr-check-findings` | The artifact's name |
| `title`, `body`, `author` | the pull request's | What to check, for a workflow on another event |

## Development

```bash
make develop   # install the dependencies and the git hooks
make check     # tidy, run the pre-commit hooks, then the tests
make test      # run the tests with coverage
make help      # list every target
```

[CONTRIBUTING.md](CONTRIBUTING.md) covers branches, commits and pull requests, and [SECURITY.md](SECURITY.md) covers reporting a vulnerability.

## License

[MIT](LICENSE)
