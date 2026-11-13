---
applyTo: '.github/workflows/*.yml'
---

# Workflow notes for AI agents

Each workflow's comments explain its design, and the tests named below enforce its rules. Read the comments on a job before you change it.

- **Do not rename `run-ci` (`Run CI (3.13)`).** The `main-protect` ruleset requires that context, and `bot-automerge.yml` arms only while a ruleset requires it. A new job goes in `run-ci`'s `needs`; `tests/test_ci_jobs.py` fails if one is missing.
- **`CI.yml` runs `make check` as four jobs:** `secrets`, `precommit`, `analysis` and `pytest`. Each hook runs in exactly one of them: `precommit` skips the hooks named in `noxfile.py`'s `_ANALYSIS_HOOKS` and `_SECRET_HOOKS`, which `analysis` and `secrets` run. The `secrets` job stages the change before gitleaks reads it, because gitleaks scans only staged changes. `tests/test_ci_jobs.py` checks both.
- **CI's ruff is stricter than local `make check`'s:** `.github/scripts/ci-ruff-args.sh` replaces ruff's arguments before the pre-commit session runs.
- **Pin every `uses:` to a full commit SHA with its release in a trailing comment, and set `persist-credentials: false` on every `actions/checkout`.** A `docker://` image is the one exception and names an exact version; `lint-github-actions.yml`'s comment says why. `tests/test_workflow_pins.py` enforces all three.
- **Key every cache on `.github/workflows/.cache-buster`.** `make bust-ci-cache` writes a new one, which invalidates every cache; `tests/test_workflow_caches.py` fails if a key leaves it out.
- **Give no other `pull_request` workflow a write scope.** Only `bot-automerge.yml` and `bot-automerge-disarm.yml` hold one, and neither checks out pull request code. `tests/test_workflows.py` enforces both and pins the auto-merge rules that `bot-automerge.yml`'s comments explain.
- **`lint-github-actions.yml` runs only on dispatch,** because the actionlint pre-commit hook already checks every pull request and push. Keep its image tag equal to that hook's `rev`, by hand.
