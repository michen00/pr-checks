"""The release scripts that decide what gets tagged and what a release pins.

parse-version.sh is the parser every release workflow runs a version through before
acting on it, and subject-tag.sh reads a release commit's subject through it, so
their edges are pinned here. approve.sh has its own suite, which runs against a
stubbed `gh`.
"""

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

__all__ = ()

_ROOT = Path(__file__).resolve().parents[1]
_RELEASE = _ROOT / 'scripts' / 'release'


def _run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    """Run a command from the repository root and capture its output."""
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_approve_suite_passes() -> None:
    """approve.sh's own suite, run against its stubbed `gh`, passes."""
    result = _run('bash', _ROOT / 'tests' / 'release' / 'approve-test.sh')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [('0.1.0', 'v0.1.0'), ('v1.2.3', 'v1.2.3'), ('v10.20.30', 'v10.20.30')],
)
def test_a_version_is_normalized_to_its_tag(raw: str, expected: str) -> None:
    """A bare or v-prefixed X.Y.Z prints as vX.Y.Z."""
    result = _run(_RELEASE / 'parse-version.sh', raw)
    assert result.returncode == 0
    assert result.stdout.strip() == expected


@pytest.mark.parametrize(
    'raw',
    ['v1.2', '1.2.3.4', 'v1.2.x', 'v1.2.3; rm -rf /', 'v1.2.3\nv4.5.6', '', 'V1.2.3'],
)
def test_anything_but_three_runs_of_digits_is_refused(raw: str) -> None:
    """A version that is not exactly X.Y.Z exits 1 and prints no tag."""
    result = _run(_RELEASE / 'parse-version.sh', raw)
    assert result.returncode == 1
    assert not result.stdout


def test_a_bare_version_is_refused_where_a_tag_is_required() -> None:
    """With --require-v, the leading v is mandatory."""
    assert _run(_RELEASE / 'parse-version.sh', '1.2.3', '--require-v').returncode == 1
    result = _run(_RELEASE / 'parse-version.sh', 'v1.2.3', '--require-v')
    assert result.stdout.strip() == 'v1.2.3'


@pytest.mark.parametrize(
    'subject',
    ['chore(release): prepare v0.2.0 (#31)', 'chore(release): prepare v0.2.0'],
    ids=['squash-merged', 'rebase-merged'],
)
def test_a_release_subject_names_its_tag(subject: str) -> None:
    """A release commit's subject gives its tag, with or without a PR number."""
    result = _run(_RELEASE / 'subject-tag.sh', subject)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'v0.2.0'


@pytest.mark.parametrize(
    'subject',
    [
        'fix: a bug (#30)',
        'chore(release): prepare 0.2.0',
        'chore(release): prepare v0.2.0; rm -rf / (#31)',
        'chore(release): prepare v0.2',
        'chore(release):  prepare v0.2.0',
        'Revert "chore(release): prepare v0.2.0"',
    ],
)
def test_any_other_subject_names_no_tag(subject: str) -> None:
    """A subject that is not exactly a release PR's title exits 1 and prints no tag."""
    result = _run(_RELEASE / 'subject-tag.sh', subject)
    assert result.returncode == 1
    assert not result.stdout


def test_bump_pins_moves_only_version_pins_of_the_check_action(tmp_path: Path) -> None:
    """Version pins follow the release and major pins its major; nothing else moves."""
    readme = tmp_path / 'README.md'
    readme.write_text(
        '      - uses: michen00/pr-checks@v0\n'
        '      - uses: michen00/pr-checks@v0 # a comment\n'
        'Pinned at michen00/pr-checks@v0.1.10.\n'
        'Or at michen00/pr-checks@v0.\n'
        'Tracking michen00/pr-checks@main beside actions/checkout@v7\n'
        '      - uses: michen00/pr-checks/comment@<commit SHA> # vX.Y.Z\n',
        encoding='utf-8',
    )
    result = _run(_RELEASE / 'bump-pins.sh', 'v1.0.0', readme)
    assert result.returncode == 0, result.stderr
    assert readme.read_text(encoding='utf-8') == (
        '      - uses: michen00/pr-checks@v1\n'
        '      - uses: michen00/pr-checks@v1 # a comment\n'
        'Pinned at michen00/pr-checks@v1.0.0.\n'
        'Or at michen00/pr-checks@v1.\n'
        'Tracking michen00/pr-checks@main beside actions/checkout@v7\n'
        '      - uses: michen00/pr-checks/comment@<commit SHA> # vX.Y.Z\n'
    )


def test_bump_pins_leaves_a_pin_already_on_the_releases_major(tmp_path: Path) -> None:
    """A patch release within the README's major tag changes nothing."""
    readme = tmp_path / 'README.md'
    original = '      - uses: michen00/pr-checks@v0\n'
    readme.write_text(original, encoding='utf-8')
    result = _run(_RELEASE / 'bump-pins.sh', 'v0.1.1', readme)
    assert result.returncode == 0, result.stderr
    assert readme.read_text(encoding='utf-8') == original


def test_bump_pins_fails_on_a_file_with_no_pin(tmp_path: Path) -> None:
    """A file naming no version of the check action exits 3 rather than passing."""
    readme = tmp_path / 'README.md'
    readme.write_text(
        'uses: michen00/pr-checks/comment@abc # v0.1.0\n', encoding='utf-8'
    )
    assert _run(_RELEASE / 'bump-pins.sh', 'v0.2.0', readme).returncode == 3


def test_bump_pins_refuses_an_invalid_tag(tmp_path: Path) -> None:
    """A tag the parser refuses never reaches the file."""
    readme = tmp_path / 'README.md'
    original = 'uses: michen00/pr-checks@v0\n'
    readme.write_text(original, encoding='utf-8')
    assert _run(_RELEASE / 'bump-pins.sh', 'v0.2.0/x', readme).returncode == 2
    assert readme.read_text(encoding='utf-8') == original


def test_the_readme_carries_a_pin_for_a_release_to_move() -> None:
    """Release PR fails without a version pin in the README, so one is there."""
    readme = (_ROOT / 'README.md').read_text(encoding='utf-8')
    assert re.search(r'michen00/pr-checks@v\d', readme)


def test_the_first_release_version_matches_the_tag_pattern() -> None:
    """With no tag yet, --bumped-version proposes a version Release PR can tag."""
    config = tomllib.loads((_ROOT / 'cliff.toml').read_text(encoding='utf-8'))
    initial = config['bump']['initial_tag']
    assert re.fullmatch(config['git']['tag_pattern'], initial)
    assert _run(_RELEASE / 'parse-version.sh', initial, '--require-v').returncode == 0
