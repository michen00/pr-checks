# Security policy

## Supported versions

There is no release yet. Once there is, fixes will go to the latest release. Every `vX.Y.Z` tag will stay where it was published: a ruleset over `refs/tags/v*.*.*` blocks updating or deleting it, and a second ruleset over `refs/tags/v*` blocks deletion. The major tag the check action's callers pin, `v0` for 0.y.z releases, will move forward to each release, which the second ruleset allows. Every tag will be signed with the release key; [RELEASING.md](RELEASING.md) says how to verify one.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: [report a vulnerability](https://github.com/michen00/pr-checks/security/advisories/new). Please do not open a public issue for a security report.

This is a personal project maintained on a best-effort basis. Expect an acknowledgment within a week.

## What the actions read

The check action reads a pull request's title and description, which the pull request's author writes. It checks out nothing and runs none of the pull request's code; its checks are the copy shipped with the action. Two properties must hold for every workflow and action here, and a change that breaks either is a security regression rather than a bug:

- No pull request text reaches a shell through a workflow expression. An expression in a `run:` block is substituted before the shell parses the line, so each value travels through `env:` or a file instead. `tests/test_workflow_injection.py` fails on any expression in a `run:` block of a workflow or composite action here.
- A workflow that runs on `pull_request`, and so runs the pull request's code, holds no write scope. `tests/test_workflows.py` fails on one that does.

The comment action writes, so it runs on `workflow_run`, from the default branch. It renders each finding with HTML and Markdown link syntax escaped, takes the pull request's number from the API rather than from the artifact the pull request's run uploaded, and edits or deletes only a bot's comment that starts with its marker.
