# pr-checks

[![Build Status](https://img.shields.io/github/actions/workflow/status/michen00/pr-checks/CI.yml?branch=main&style=plastic)](https://github.com/michen00/pr-checks/actions/workflows/CI.yml)
[![License](https://img.shields.io/github/license/michen00/pr-checks?style=plastic)](LICENSE)

GitHub Actions that check a pull request's title and description before it merges.

## Status

Pre-release. As of 2026-11-12 this repository holds only its tooling: linting, type checking, tests and CI. The checks and the actions that run them are to follow, and nothing here is ready to use yet.

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
