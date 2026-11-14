"""Tests that action.yml hands each input to the checks, through the environment.

The check step's script runs under bash here, with its `${{ }}` expressions resolved
from the action's input defaults, so the wiring is exercised rather than read. The
install step needs a package index, so the PR checks workflow covers it instead,
on every pull request.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

__all__ = ()

_ROOT = Path(__file__).resolve().parents[1]
_ACTION: dict[str, Any] = yaml.safe_load(
    (_ROOT / 'action.yml').read_text(encoding='utf-8')
)
_EXPRESSION = re.compile(r'\$\{\{\s*(.*?)\s*\}\}')
_PULL_REQUEST = {
    'title': 'feat: add a rule',
    'body': '## Summary\n\nWhy.\n',
    'author': 'octocat',
}


def _step(name: str) -> dict[str, Any]:
    """Return the action's step called `name`."""
    return next(step for step in _ACTION['runs']['steps'] if step.get('name') == name)


def _check(tmp_path: Path, **inputs: str) -> subprocess.CompletedProcess[str]:
    """Run the check step as the runner would, with `inputs` over the defaults."""
    values = {
        name: str(spec.get('default', '')) for name, spec in _ACTION['inputs'].items()
    }
    values.update(_PULL_REQUEST)
    values.update({name.replace('_', '-'): value for name, value in inputs.items()})
    context = {f'inputs.{name}': value for name, value in values.items()}
    context['github.action_path'] = str(_ROOT)
    context['runner.temp'] = str(tmp_path)

    # The virtual environment's python, standing in for the one the install step makes.
    venv_python = tmp_path / 'pr-checks-venv' / 'bin' / 'python'
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding='utf-8'
    )
    venv_python.chmod(0o755)

    step = _step('Check the pull request')
    env = {
        name: _EXPRESSION.sub(lambda match: context[match[1]], str(value))
        for name, value in step['env'].items()
    }
    return subprocess.run(
        ['bash', '-c', step['run']],
        env={'PATH': os.environ['PATH'], **env},
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


# -- Usage: a pull request as the defaults check it --


def test_the_defaults_check_the_title_and_body(tmp_path: Path) -> None:
    """With only the pull request's own fields, both checks run and record."""
    result = _check(tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == 'title OK\nbody OK\n'
    assert (tmp_path / 'pr-checks-findings' / 'format').read_text(encoding='utf-8') == (
        '1\n'
    )


# -- Each input reaches the checks --


@pytest.mark.parametrize(
    ('inputs', 'code', 'printed'),
    [
        pytest.param(
            {'max_length': '10'}, 1, 'title: 1 error(s)\nbody OK\n', id='max-length'
        ),
        pytest.param(
            {'required_sections': 'Summary\nTesting'},
            0,
            'title OK\nbody OK (with warnings)\n',
            id='required-sections',
        ),
        pytest.param({'check_title': 'false'}, 0, 'body OK\n', id='check-title'),
        pytest.param({'check_body': 'false'}, 0, 'title OK\n', id='check-body'),
        pytest.param(
            {'author': 'renovate[bot]', 'title': 'Update lib'},
            0,
            'renovate[bot] is a bot, so no check runs\n',
            id='skip-bot-authors',
        ),
        pytest.param(
            {
                'author': 'renovate[bot]',
                'title': 'Update lib',
                'skip_bot_authors': 'false',
            },
            1,
            'title: 1 error(s)\nbody OK\n',
            id='skip-bot-authors off',
        ),
        pytest.param(
            {'title': 'fix: retry S3 uploads', 'warn_plan_ids': 'true'},
            0,
            'title OK (with warnings)\nbody OK\n',
            id='warn-plan-ids',
        ),
    ],
)
def test_an_input_reaches_the_checks(
    tmp_path: Path, inputs: dict[str, str], code: int, printed: str
) -> None:
    """Changing an input changes what the checks do."""
    result = _check(tmp_path, **inputs)
    assert (result.returncode, result.stdout) == (code, printed), result.stderr


def test_a_title_is_text_and_never_script(tmp_path: Path) -> None:
    """A title holding shell syntax reaches the check as text and runs nothing."""
    result = _check(tmp_path, title='feat: add $(touch pwned) "quoted" `and ticks`')

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / 'pwned').exists()


def test_a_section_that_starts_with_a_hyphen_is_not_an_option(tmp_path: Path) -> None:
    """Each value follows its option after `=`, so `-h` is a heading, not help."""
    result = _check(tmp_path, required_sections='-h')
    assert (result.returncode, result.stdout) == (
        0,
        'title OK\nbody OK (with warnings)\n',
    )


# -- The definition itself --


def test_every_input_is_used() -> None:
    """An input the steps never read would be accepted and silently ignored."""
    text = (_ROOT / 'action.yml').read_text(encoding='utf-8')
    unused = [
        name
        for name in _ACTION['inputs']
        if not re.search(rf'inputs\.{re.escape(name)}(?![\w-])', text)
    ]
    assert unused == []


def test_the_upload_takes_the_directory_the_checks_write() -> None:
    """The artifact is the findings directory the check step names."""
    findings_dir = _step('Check the pull request')['env']['FINDINGS_DIR']
    assert _step('Upload the findings')['with']['path'] == findings_dir
