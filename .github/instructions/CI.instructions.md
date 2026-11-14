---
applyTo: '.github/workflows/*.yml'
---

# Workflow notes for AI agents

`tests/test_ci_jobs.py` and `tests/test_workflow*.py` enforce the workflows' rules, and each workflow's comments explain its design. Keep two rules by hand:

- Do not rename the job named `Run CI (3.13)`: the `main-protect` ruleset requires that context.
- Keep the actionlint image tag in `lint-github-actions.yml` equal to the actionlint hook's `rev` in `.pre-commit-config.yaml`.
