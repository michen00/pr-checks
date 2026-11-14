## Summary

This PR prepares release `@RELEASE_TAG@`. It stamps the release into `CHANGELOG.md` as its own section, sets the package version in `pyproject.toml` and `uv.lock`, and points the README's usage snippet at the release's major tag.

Merge it with its title as the commit's subject: Release Tag reads the version from that subject and checks it against `pyproject.toml`. The merge tags nothing until `make release-approve` approves the Release Tag run waiting on the `release` environment. That run then pushes the signed tag `@RELEASE_TAG@`, moves the major tag to the same commit and publishes the GitHub release.

## Testing

- [x] Release PR ran the test suite on these files before opening this PR
- [ ] CI is green: GitHub starts no workflow for a pull request the default token opened, so close and reopen this PR to start its checks. Closing it tags nothing, because Release Tag runs only when the release commit lands on `main`.
