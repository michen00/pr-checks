# pr-checks

[![Build Status](https://img.shields.io/github/actions/workflow/status/michen00/pr-checks/CI.yml?branch=main&style=plastic)](https://github.com/michen00/pr-checks/actions/workflows/CI.yml)
[![License](https://img.shields.io/github/license/michen00/pr-checks?style=plastic)](LICENSE)

GitHub Actions that check a pull request's title and description before it merges.

## Status

Pre-release. As of 2026-11-14 both actions are here, but no version is tagged.

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
      - uses: michen00/pr-checks@v0
        with:
          required-sections: |
            Summary
            Testing
```

`v0` will move to each 0.y.z release as it is published; pin a `vX.Y.Z` tag, or the commit it points at, to stay on one release.

The action checks out nothing. It sets up uv with `astral-sh/setup-uv`, which puts uv on the job's `PATH` for later steps, and runs on the runner's own `python3`, which must be 3.12 or later; CI tries it on `ubuntu-24.04` and `ubuntu-latest`.

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

## Posting the findings as a comment

The comment action posts the findings on the pull request as one comment: the errors, then the warnings. It edits the comment as the findings change and deletes it once there are none.

```yaml
name: PR checks comment
on:
  workflow_run:
    workflows: [PR checks]
    types: [completed]
permissions:
  actions: read
  pull-requests: write
jobs:
  comment:
    runs-on: ubuntu-latest
    steps:
      - uses: michen00/pr-checks/comment@<commit SHA> # vX.Y.Z
```

It runs in a workflow of its own because `workflow_run` takes the definition from the default branch, so the token that writes the comment never runs the pull request's code. Pin it to the commit a release's tag points at, since it writes, with the release in a trailing comment so that Dependabot moves the two together. `gh api repos/michen00/pr-checks/commits/vX.Y.Z --jq .sha` prints that commit.

| Input | Default | Meaning |
| --- | --- | --- |
| `github-token` | the job's token | Needs `actions: read` and `pull-requests: write` |
| `artifact-name` | `pr-check-findings` | The check action's artifact |
| `marker` | `<!-- pr-checks:findings -->` | Hidden text that marks the action's own comment |
| `handoff` | `true` | Whether to end the comment with a prompt to hand to a coding agent |

## Development

```bash
make develop   # install the dependencies and the git hooks
make check     # tidy, run the pre-commit hooks, then the tests
make test      # run the tests with coverage
make help      # list every target
```

[CONTRIBUTING.md](CONTRIBUTING.md) covers branches, commits and pull requests, [RELEASING.md](RELEASING.md) covers making a release, and [SECURITY.md](SECURITY.md) covers reporting a vulnerability.

## License

[MIT](LICENSE)
