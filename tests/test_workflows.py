"""Tests for the workflows' security properties.

Each test reads the workflow definitions and pins one property that a later edit could
remove without any other check failing. The no-interpolation rule is in
test_workflow_injection.py.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

__all__ = ()

_WORKFLOWS = Path(__file__).resolve().parents[1] / '.github' / 'workflows'


def _load(path: Path) -> dict[Any, Any]:
    """Return a parsed workflow definition."""
    document: dict[Any, Any] = yaml.safe_load(path.read_text(encoding='utf-8'))
    return document


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    """Return a workflow's `on:` mapping, which YAML 1.1 parses as the key True."""
    triggers: dict[str, Any] = workflow['on'] if 'on' in workflow else workflow[True]
    return triggers


def _write_scopes(permissions: object) -> set[str]:
    """Return the scopes a `permissions:` value grants write on."""
    if permissions == 'write-all':
        return {'*'}
    if isinstance(permissions, dict):
        return {scope for scope, level in permissions.items() if level == 'write'}
    return set()


def _pull_request_workflows() -> list[Any]:
    """Return every workflow triggered by `pull_request`, as one parameter each."""
    return [
        pytest.param(path, id=path.name)
        for path in sorted(_WORKFLOWS.glob('*.y*ml'))
        if 'pull_request' in _triggers(_load(path))
    ]


@pytest.mark.parametrize('path', _pull_request_workflows())
def test_a_workflow_that_runs_pull_request_code_cannot_write(path: Path) -> None:
    """A `pull_request` workflow runs pull request code, so it holds no write scope."""
    workflow = _load(path)
    assert _write_scopes(workflow.get('permissions')) == set()
    for job_name, job in workflow['jobs'].items():
        assert _write_scopes(job.get('permissions')) == set(), job_name


def test_ci_is_among_the_workflows_checked() -> None:
    """The scan above finds CI.yml, so it cannot pass by finding nothing."""
    assert 'CI.yml' in {param.id for param in _pull_request_workflows()}
