"""Tests that every action a workflow or this repository's action runs is pinned.

A tag can be moved to other code after it was reviewed; a commit SHA cannot. Every
`uses:` is pinned to a full commit SHA with the release it names in a trailing comment,
the form Dependabot moves together. The one exception is a `docker://` image, which
Dependabot does not update in any form; it must name an exact version, never a
floating tag. Every checkout also drops its credential, so no later step finds the job's
token in .git/config.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

__all__ = ()

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / '.github' / 'workflows'
_USES = re.compile(
    r'^\s*(?:-\s+)?uses:\s*(?P<ref>\S+)\s*(?:#\s*(?P<comment>.*\S))?\s*$'
)
_PINNED = re.compile(r'^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$')
_RELEASE = re.compile(r'^v\d+\.\d+\.\d+$')
_DOCKER_EXACT = re.compile(r'^docker://[\w./-]+:\d+\.\d+\.\d+$')
_SHA = '3d3c42e5aac5ba805825da76410c181273ba90b1'


def _problem(line: str) -> str | None:
    """Return why a `uses:` line is not pinned, or None if it is."""
    match = _USES.match(line)
    if match is None:
        return 'not a uses: line'
    ref, comment = match['ref'], match['comment']
    if ref.startswith('./'):
        return None
    if ref.startswith('docker://'):
        return None if _DOCKER_EXACT.match(ref) else f'{ref} names no exact version'
    if not _PINNED.match(ref):
        return f'{ref} is not pinned to a full commit SHA'
    if comment is None or not _RELEASE.match(comment):
        return f'{ref} has no exact release in its comment'
    return None


def _uses_lines() -> list[Any]:
    """Return every `uses:` line in the definitions, named by file and line number."""
    params = []
    definitions = [
        *_WORKFLOWS.glob('*.y*ml'),
        *_ROOT.glob('action.y*ml'),
        *_ROOT.glob('*/action.y*ml'),
    ]
    for path in sorted(definitions):
        lines = path.read_text(encoding='utf-8').splitlines()
        params.extend(
            pytest.param(line, id=f'{path.relative_to(_ROOT)}:{number}')
            for number, line in enumerate(lines, 1)
            if _USES.match(line)
        )
    return params


def _checkout_steps() -> list[Any]:
    """Return every actions/checkout step, named by file and job."""
    params = []
    for path in sorted(_WORKFLOWS.glob('*.y*ml')):
        workflow = yaml.safe_load(path.read_text(encoding='utf-8'))
        for job_id, job in workflow['jobs'].items():
            params.extend(
                pytest.param(step, id=f'{path.name}:{job_id}')
                for step in job.get('steps', [])
                if step.get('uses', '').startswith('actions/checkout@')
            )
    return params


@pytest.mark.parametrize('line', _uses_lines())
def test_every_action_is_pinned_to_a_commit_with_its_release(line: str) -> None:
    """A `uses:` names a local action, a SHA with its release, or an exact image."""
    assert _problem(line) is None, _problem(line)


@pytest.mark.parametrize('step', _checkout_steps())
def test_every_checkout_drops_its_credential(step: dict[str, Any]) -> None:
    """actions/checkout keeps the job's token in .git/config unless told not to."""
    assert step.get('with', {}).get('persist-credentials') is False


def test_the_scans_find_what_they_check() -> None:
    """Both scans find checkouts, so neither can pass by finding nothing."""
    assert any('actions/checkout@' in param.values[0] for param in _uses_lines())
    assert _checkout_steps()


@pytest.mark.parametrize(
    ('line', 'pinned'),
    [
        (f'- uses: actions/checkout@{_SHA} # v7.0.1', True),
        (f'  uses: owner/repo/path@{_SHA} # v1.2.3', True),
        ('- uses: ./.github/actions/local', True),
        ('- uses: docker://rhysd/actionlint:1.7.12', True),
        ('- uses: actions/checkout@v7', False),
        (f'- uses: actions/checkout@{_SHA}', False),
        ('- uses: actions/checkout@3d3c42e5 # v7.0.1', False),
        (f'- uses: actions/checkout@{_SHA} # v7', False),
        ('- uses: docker://rhysd/actionlint:latest', False),
        ('- uses: docker://rhysd/actionlint:1', False),
        ('- uses: docker://rhysd/actionlint', False),
    ],
)
def test_the_pin_check_tells_a_commit_from_a_tag(line: str, *, pinned: bool) -> None:
    """A SHA with an exact release passes; a tag, short SHA or bare major does not."""
    assert (_problem(line) is None) is pinned
