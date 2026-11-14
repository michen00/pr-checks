# Releasing

The maintainer makes releases; contributors need nothing here, and [CONTRIBUTING.md](CONTRIBUTING.md) covers what they do. A release is three things: a GPG-signed `vX.Y.Z` tag; the major tag, which callers of the check action pin, moved to the same commit; and a GitHub release whose notes are the version's `CHANGELOG.md` section. Nothing is built or uploaded: callers run the actions from the tagged tree.

The flow is automated except for one approval, which stands between a merged pull request and a tag signed with the CI release key.

## Default flow

1. **Release PR** (`.github/workflows/release-pr.yml`) opens the release PR by itself when a commit worth releasing lands on `main`. Every Conventional Commit type bumps at least the patch version, so the version alone cannot decide that; the workflow counts the commits `cliff.toml` puts in its features, fixes, performance and revert groups, plus any marked breaking. Run the workflow by hand, or `make release-pr`, to choose the version or to release a batch with none of those; a manual run skips that count. Leave `version` empty to derive it with `git cliff --bumped-version`, or pass `X.Y.Z` or `vX.Y.Z`. The pull request stamps the version into `CHANGELOG.md`, `pyproject.toml` and `uv.lock`, points the README's usage snippet at the release's major tag, and is committed through the API, so GitHub signs its commit.
1. **Start its checks.** GitHub starts no workflow for a pull request that the default token opened. Close the release PR and reopen it, and the required checks run. Closing it tags nothing.
1. **Review and merge it** with its title, `chore(release): prepare vX.Y.Z`, as the commit's subject.
1. **Release Tag** (`.github/workflows/release-tag.yml`) starts when that commit lands on `main`, and waits on the protected `release` environment.
1. **Approve the release.** Run `make release-approve`. It finds the waiting Release Tag run, shows the tag it will create, the major tag it will move and the commit both will point at, and asks you to confirm. The run can also be approved from its page on GitHub. Rejecting it leaves no tag behind.
1. Once approved, Release Tag checks that the commit's subject and `pyproject.toml` name the same version, and that the commit is the merge of this repository's `release/vX.Y.Z` branch. It then creates the GPG-signed annotated tag, verifies it and pushes it, moves the major tag (`v0` for a 0.y.z release, `vN` otherwise) to the same commit, signed the same way, and publishes the GitHub release.

A release that is never approved waits. There is no timeout and no reminder, so a merged release PR can sit indefinitely; `make release-status` shows whether that has happened.

## Checking release status

```bash
make release-status   # latest release, any open release PR, any run awaiting approval
make release-approve  # approve the waiting run after confirming what will be tagged
```

Both read the repository through `gh` and need no other local state. `make release-approve` does nothing when no run is waiting. It approves a Release Tag run only when a push to `main` started it, because a run's workflow file comes from the ref the run started on, and only when the run's commit is a release commit.

## Why Release PR sometimes does nothing

**Release PR** refuses to prepare a release while the last prepared version is still untagged: on a push it says so and stops, and a manual run fails. That covers the approval window, in which a `fix` merged while Release Tag waits would otherwise propose a second PR for the version already on its way out. It also holds after an approval is rejected, which leaves a prepared version with no tag; the manual fallback below clears it.

If the version moves while a release PR is open, such as a `feat` landing on top of a pending patch, the next run opens a PR for the new version and closes the superseded one, so that no open PR would release an older version.

## Manual fallback

Run these from a clone with the release commit, signing with your own key:

```bash
git switch main && git pull
commit="$(git log -1 --format=%H --grep='^chore(release): prepare vX.Y.Z')"
git tag -a -s vX.Y.Z -m vX.Y.Z "$commit"
git tag -f -a -s v0 -m vX.Y.Z "$commit"
git push origin vX.Y.Z
git push --force origin refs/tags/v0
gh release create vX.Y.Z --verify-tag --title vX.Y.Z --generate-notes
```

Use the release's major tag in place of `v0` from 1.0.0 on. `--generate-notes` writes the notes from the merged pull requests, leaving out the bots `.github/release.yml` names; replace them with the version's `CHANGELOG.md` section with `gh release edit vX.Y.Z --notes-file <file>`.

## Signing model

- **Tags** are annotated and GPG-signed. Release Tag signs with the CI release key rather than a maintainer's personal key, verifies each signature before pushing, and accepts an existing `vX.Y.Z` tag on a rerun only when it is a validly signed annotated tag on the release commit. The `version-tags-immutable` ruleset keeps every `vX.Y.Z` tag from being moved or deleted once pushed. `tags-no-delete` keeps every `v*` tag from being deleted but lets the major tag move, and Release Tag moves it only forward, to a descendant of the commit it points at.
- **Commits** on `main` are signed, which the `main-protect` ruleset requires: GitHub signs the squash commit of every merge and the release PR's commit, which Release PR makes through the API.
- The protected `release` environment, set up as below, keeps the key from being usable by anyone who can merge a pull request: the tagging job waits for the maintainer's approval before it runs, and only a run on `main` may deploy to it.

### One-time setup

Set this up once, locally, before the first release PR merges. A job that names an environment that does not exist creates it without protection, so create the environment first. Never paste private key material into an issue, a pull request or a chat transcript.

```bash
# 1. Create the `release` environment, with you as its required reviewer and
#    deployments from main only.
jq -n --argjson id "$(gh api user --jq .id)" '{
  reviewers: [{type: "User", id: $id}],
  deployment_branch_policy: {protected_branches: false, custom_branch_policies: true}
}' | gh api -X PUT repos/michen00/pr-checks/environments/release --input -
gh api -X POST repos/michen00/pr-checks/environments/release/deployment-branch-policies \
  -f name=main -f type=branch

# 2. Generate a dedicated release key (not your personal key), with a passphrase.
PASSPHRASE='<choose-a-strong-passphrase>'
gpg --batch --passphrase "$PASSPHRASE" \
  --quick-generate-key 'pr-checks release <you@example.com>' rsa4096 sign 2y

# 3. Note its fingerprint.
gpg --list-secret-keys --keyid-format=long

# 4. Store the key as secrets of the `release` environment, so that only the job
#    that waits for approval can read it.
gpg --armor --export-secret-keys <FINGERPRINT> |
  gh secret set RELEASE_GPG_PRIVATE_KEY --env release --repo michen00/pr-checks
gh secret set RELEASE_GPG_PASSPHRASE --env release --repo michen00/pr-checks \
  --body "$PASSPHRASE"

# 5. Register the public key so signed tags display as Verified on GitHub.
#    Paste the output at https://github.com/settings/gpg/new
gpg --armor --export <FINGERPRINT>
```

Piping the export into `gh secret set` leaves no key file on disk. Confirm the secrets landed with `gh secret list --env release --repo michen00/pr-checks`. Without the private key, Release Tag fails at the import step and creates no tag; a GitHub App token cannot stand in for it, because GitHub signs commits it creates through the API but never an annotated tag. The key expires in two years; rotate it by repeating steps 2 to 5.

## Verifying a release

```bash
curl -fsSL https://github.com/michen00.gpg | gpg --import   # the maintainer's public keys
git fetch --tags --force origin   # --force updates a major tag that has moved
git verify-tag vX.Y.Z
```

Replace `vX.Y.Z` with the release you use. `git verify-tag v0` checks the major tag the same way.
