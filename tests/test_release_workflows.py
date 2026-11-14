"""Tests for what the release workflows tag, and who may hold the release key.

Release PR opens a pull request whose title becomes the release commit's subject, and
Release Tag tags that commit once a maintainer approves it. Each test pins one
property a later edit could remove without any other check failing.
"""

import os
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

__all__ = ()

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / '.github' / 'workflows'
_PREFIX = 'chore(release): prepare '


def _workflow(name: str) -> dict[Any, Any]:
    """Return the parsed definition of the workflow file ``name``."""
    document: dict[Any, Any] = yaml.safe_load(
        (_WORKFLOWS / name).read_text(encoding='utf-8')
    )
    return document


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    """Return a workflow's `on:` mapping, which YAML 1.1 parses as the key True."""
    triggers: dict[str, Any] = workflow['on'] if 'on' in workflow else workflow[True]
    return triggers


def _steps(workflow: dict[Any, Any], job: str) -> dict[str, dict[str, Any]]:
    """Return a job's steps keyed by name."""
    return {step.get('name', ''): step for step in workflow['jobs'][job]['steps']}


def test_release_tag_runs_only_for_a_release_commit_pushed_to_main() -> None:
    """Release Tag runs on a push to main whose head commit is a release PR's.

    A `pull_request` trigger would run the workflow file of the pull request's merge
    ref, and a push to another branch that branch's own.
    """
    workflow = _workflow('release-tag.yml')
    assert _triggers(workflow) == {'push': {'branches': ['main']}}
    assert workflow['jobs']['release-tag']['if'] == (
        f"startsWith(github.event.head_commit.message, '{_PREFIX}v')"
    )


def test_the_release_pr_is_titled_as_release_tag_expects() -> None:
    """The release PR's title is the subject Release Tag runs for and Release PR skips.

    A squash merge makes the title the commit's subject. Release PR skips that
    commit, since its tag does not exist yet and it would propose the release again.
    """
    release_pr = _workflow('release-pr.yml')
    create = _steps(release_pr, 'release-pr')['Create release PR']['with']
    assert create['title'] == f'{_PREFIX}${{{{ needs.resolve.outputs.tag }}}}'
    assert create['commit-message'] == create['title']
    guard = ' '.join(release_pr['jobs']['resolve']['if'].split())
    assert (
        f"!startsWith(github.event.head_commit.message, '{_PREFIX.strip()}')" in guard
    )


def test_only_the_approved_job_reads_the_release_key() -> None:
    """The release key's secrets appear only in the job that waits for approval.

    The environment's required reviewer is what stands between a merged pull request
    and a tag signed with the key.
    """
    readers = {
        path.name
        for path in _WORKFLOWS.glob('*.y*ml')
        if 'RELEASE_GPG_' in path.read_text(encoding='utf-8')
    }
    assert readers == {'release-tag.yml'}
    workflow = _workflow('release-tag.yml')
    assert list(workflow['jobs']) == ['release-tag']
    job = workflow['jobs']['release-tag']
    assert job['environment'] == 'release'
    assert workflow['permissions'] == {'contents': 'read'}
    assert job['permissions'] == {'contents': 'write'}


@pytest.mark.parametrize(
    'step', ['Create and push the signed tag', 'Move the major tag']
)
def test_a_tag_is_verified_before_it_is_pushed(step: str) -> None:
    """Each tag's signature is checked before the tag leaves the runner."""
    script = _steps(_workflow('release-tag.yml'), 'release-tag')[step]['run']
    assert 'git verify-tag' in script
    assert script.rindex('git verify-tag') < script.index('git push')


def test_the_write_job_of_release_pr_runs_no_tool_of_the_repository() -> None:
    """The job holding the write token runs no tool the prepare job installs.

    git-cliff, uv, pre-commit and the tests run under the read-only token, and their
    output reaches the write job as an artifact.
    """
    steps = _workflow('release-pr.yml')['jobs']['release-pr']['steps']
    actions = {step['uses'].split('@')[0] for step in steps if 'uses' in step}
    assert actions == {
        'actions/checkout',
        'actions/download-artifact',
        'peter-evans/create-pull-request',
    }
    for step in steps:
        script = step.get('run', '')
        for tool in ('uv ', 'nox', 'pre-commit', 'git cliff', 'scripts/'):
            assert tool not in script, (step.get('name'), tool)


def test_the_worthiness_gate_counts_the_groups_cliff_toml_releases() -> None:
    """Release PR counts the features, fixes, performance and revert groups by index.

    cliff.toml numbers its groups, and the gate matches the numbers rather than the
    labels, so renumbering one without the other changes what a push may release.
    """
    config = tomllib.loads((_ROOT / 'cliff.toml').read_text(encoding='utf-8'))
    groups = {
        parser['message']: parser['group']
        for parser in config['git']['commit_parsers']
        if 'group' in parser
    }
    indexes = [groups[f'^{kind}'][5:7] for kind in ('feat', 'fix', 'perf', 'revert')]
    script = _steps(_workflow('release-pr.yml'), 'resolve')['Resolve release version']
    assert f'^<!-- ({"|".join(indexes)}) -->' in script['run']


def _resolve(
    tmp_path: Path, subject: str, version: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    """Run Release Tag's resolve step on a commit with ``subject`` and ``version``.

    Returns the finished step and the outputs it wrote.
    """
    repo = tmp_path / 'repo'
    shutil.copytree(_ROOT / 'scripts' / 'release', repo / 'scripts' / 'release')
    (repo / 'pyproject.toml').write_text(
        f'[project]\nname = "pr-checks"\nversion = "{version}"\n', encoding='utf-8'
    )
    env = {
        key: value for key, value in os.environ.items() if not key.startswith('GIT_')
    }
    env |= {
        'GIT_CONFIG_GLOBAL': os.devnull,
        'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_AUTHOR_NAME': 'GitHub',
        'GIT_AUTHOR_EMAIL': 'noreply@github.com',
        'GIT_COMMITTER_NAME': 'GitHub',
        'GIT_COMMITTER_EMAIL': 'noreply@github.com',
    }
    for args in (
        ['init', '-q', '-b', 'main'],
        ['add', '.'],
        ['commit', '-qm', subject],
    ):
        subprocess.run(['git', *args], cwd=repo, env=env, check=True)
    output = tmp_path / 'output'
    output.touch()
    step = _steps(_workflow('release-tag.yml'), 'release-tag')[
        'Resolve the release tag'
    ]
    result = subprocess.run(
        ['bash', '-e', '-c', step['run']],
        cwd=repo,
        env={**env, 'GITHUB_OUTPUT': str(output)},
        capture_output=True,
        text=True,
        check=False,
    )
    outputs = dict(
        line.split('=', 1) for line in output.read_text(encoding='utf-8').splitlines()
    )
    return result, outputs


@pytest.mark.parametrize(
    ('subject', 'version', 'expected'),
    [
        (
            'chore(release): prepare v0.2.0 (#31)',
            '0.2.0',
            {'tag': 'v0.2.0', 'major': 'v0'},
        ),
        ('chore(release): prepare v1.2.3', '1.2.3', {'tag': 'v1.2.3', 'major': 'v1'}),
    ],
    ids=['squash-merged', 'rebase-merged'],
)
def test_release_tag_tags_the_release_its_commit_names(
    tmp_path: Path, subject: str, version: str, expected: dict[str, str]
) -> None:
    """The tag comes from the commit's subject, and the major tag from the tag."""
    result, outputs = _resolve(tmp_path, subject, version)
    assert result.returncode == 0, result.stderr
    assert outputs == expected


@pytest.mark.parametrize(
    ('subject', 'version'),
    [
        ('chore(release): prepare v0.2.0 (#31)', '0.1.9'),
        ('chore(release): prepare v0.2.0; echo pwned (#31)', '0.2.0'),
    ],
    ids=['version-mismatch', 'malformed-subject'],
)
def test_release_tag_refuses_a_commit_that_does_not_name_its_version(
    tmp_path: Path, subject: str, version: str
) -> None:
    """A subject that disagrees with pyproject.toml, or names no clean tag, fails."""
    result, outputs = _resolve(tmp_path, subject, version)
    assert result.returncode != 0
    assert outputs == {}
