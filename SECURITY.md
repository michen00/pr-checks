# Security policy

## Supported versions

There is no release yet. Once there is, fixes will go to the latest release. Every `vX.Y.Z` tag will stay where it was published: a ruleset over `refs/tags/v*.*.*` blocks updating or deleting it, and a second ruleset over `refs/tags/v*` blocks deletion.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: [report a vulnerability](https://github.com/michen00/pr-checks/security/advisories/new). Please do not open a public issue for a security report.

This is a personal project maintained on a best-effort basis. Expect an acknowledgment within a week.

## What the actions will read

The actions this repository is to publish will read a pull request's title and description, which the pull request's author writes. Two properties must hold for every workflow and action here, and a change that breaks either is a security regression rather than a bug:

- No pull request text reaches a shell through a workflow expression. An expression in a `run:` block is substituted before the shell parses the line, so each value travels through `env:` or a file instead. `tests/test_workflow_injection.py` fails on any expression in a `run:` block of a workflow or composite action here.
- A workflow that runs on `pull_request`, and so runs the pull request's code, holds no write scope. `tests/test_workflows.py` fails on one that does.
