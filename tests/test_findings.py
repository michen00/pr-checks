"""Tests for how findings reach a reader: printed, annotated and written to files."""

from pathlib import Path

import pytest

from pr_checks.findings import Findings

__all__ = ()


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Run every test as a terminal would."""
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    return monkeypatch


# -- Usage: how a check ends --


def test_emit_prints_the_findings_and_returns_the_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A check's command line ends by handing its findings to `emit`.

    `emit` prints each finding and returns the process exit code: 0 when nothing
    blocks, warnings or not, and 1 otherwise.
    """
    assert Findings(warnings=['title: not a verb']).emit('title OK') == 0
    assert capsys.readouterr() == (
        'title OK (with warnings)\n',
        'warning: title: not a verb\n',
    )

    assert Findings(errors=['title: ends with a period']).emit('title OK') == 1
    assert capsys.readouterr() == ('', 'error: title: ends with a period\n')


# -- Printing --


def test_a_finding_becomes_an_annotation_in_actions(
    local: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Under GitHub Actions, each finding is a workflow command on stdout."""
    local.setenv('GITHUB_ACTIONS', 'true')

    Findings(errors=['title: e'], warnings=['title: w']).publish()

    assert capsys.readouterr().out == '::warning::title: w\n::error::title: e\n'


def test_an_annotation_cannot_start_a_second_command(
    local: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A newline, carriage return or percent sign in a finding is escaped."""
    local.setenv('GITHUB_ACTIONS', 'true')

    Findings(warnings=['title: a\r\n::stop-commands::x 100%']).publish()

    assert capsys.readouterr().out == (
        '::warning::title: a%0D%0A::stop-commands::x 100%25\n'
    )


def test_merge_folds_one_result_into_another() -> None:
    """`merge` appends the other result's errors and warnings."""
    found = Findings(errors=['a'], warnings=['b'])
    found.merge(Findings(errors=['c'], warnings=['d']))
    assert found == Findings(errors=['a', 'c'], warnings=['b', 'd'])


# -- Recording --


def test_record_writes_each_kind_to_its_own_file(tmp_path: Path) -> None:
    """Errors and warnings go to separate files named for the check, one per line."""
    Findings(
        errors=['title: not Conventional Commit form'],
        warnings=['title: not a verb', 'title: contains a plan identifier'],
    ).record(tmp_path, 'title')

    assert (tmp_path / 'errors' / 'title.txt').read_text(encoding='utf-8') == (
        'title: not Conventional Commit form\n'
    )
    assert (tmp_path / 'warnings' / 'title.txt').read_text(encoding='utf-8') == (
        'title: not a verb\ntitle: contains a plan identifier\n'
    )


def test_a_kind_with_no_findings_writes_no_file(tmp_path: Path) -> None:
    """A clean check creates no file, not even an empty one."""
    Findings(warnings=['body: a TODO marker']).record(tmp_path, 'body')
    Findings().record(tmp_path, 'title')

    files = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob('*.txt'))
    assert files == [Path('warnings/body.txt')]
