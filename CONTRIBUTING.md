# Contributing

Contributions are welcome, from a typo fix to a new check. Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md). To report a vulnerability, use the private channel in [SECURITY.md](SECURITY.md) rather than an issue.

## Set up

```bash
make develop   # sync dependencies and install the git hooks
```

`make develop` sets up Git LFS only when `git-lfs` is installed, and `.gitattributes` stores images, audio, PDFs and Word documents in Git LFS, so install `git-lfs` first.

## Branches and commits

- Fork the repository and branch from a fresh `main`, named `<type>/<short-description>`.
- Commit subjects are Conventional Commits. The valid types are `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style` and `test`, the description after the colon starts with a lowercase letter, and the whole subject runs to 50 characters at most. The `commit-msg` hooks check the form locally.
- Keep each commit to one logical change.
- Bring a branch up to date with `main` by merging, not rebasing, once it has been pushed.

## Before you open a PR

```bash
make check   # tidy, run the pre-commit hooks, then the tests
```

CI runs the same hooks and tests on every pull request.

Write Markdown prose as one line per paragraph. The `unwrap-markdown-prose-py` hook reflows a hard-wrapped paragraph in place and stops the commit so you can see what changed.

A change to a workflow has to keep the properties `tests/test_workflows.py` and `tests/test_workflow_injection.py` pin.

## Opening the PR

- Merges are squash-only, and the PR title becomes the squash commit, so it must be a valid Conventional Commit. A single-commit PR squashes to that commit's subject instead, so keep the two identical.
- Fill in the [PR template](.github/pull_request_template.md). Summary and Testing always apply.
- Open as a draft while the change is still moving.
- Read what a merge into `main` needs with `gh api repos/michen00/pr-checks/rules/branches/main`. Dependabot's updates merge without a person once CI passes; label one `do not auto-merge` to keep it for a person to merge.
