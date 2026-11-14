"""Tests for how findings reach a reader: printed, annotated and recorded to files."""

from pathlib import Path

import pytest

from pr_checks.findings import Findings

__all__ = ()


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Run every test as a terminal would, with no findings file set."""
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.delenv('PR_WARNINGS_FILE', raising=False)
    monkeypatch.delenv('PR_ERRORS_FILE', raising=False)
    return monkeypatch


# -- Usage: how a check ends --


def test_emit_prints_records_and_returns_the_exit_code(
    local: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every check ends by handing its findings to `emit`.

    `emit` returns the process exit code, and a warnings-only result exits 0. It
    prints each finding and, when `PR_WARNINGS_FILE` names a file, appends the
    warnings to it.
    """
    warnings_file = tmp_path / 'title.txt'
    local.setenv('PR_WARNINGS_FILE', str(warnings_file))

    code = Findings(warnings=['title: not a verb']).emit('title OK')
    printed = capsys.readouterr()

    assert code == 0
    assert printed.out == 'title OK (with warnings)\n'
    assert printed.err == 'warning: title: not a verb\n'
    assert warnings_file.read_text(encoding='utf-8') == 'title: not a verb\n'


# -- Printing --


def test_a_finding_becomes_an_annotation_in_actions(
    local: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Under GitHub Actions, each finding is a workflow command on stdout."""
    local.setenv('GITHUB_ACTIONS', 'true')

    assert Findings(errors=['title: e'], warnings=['title: w']).emit('title OK') == 1
    assert capsys.readouterr().out == '::warning::title: w\n::error::title: e\n'


def test_merge_folds_one_result_into_another() -> None:
    """`merge` appends the other result's errors and warnings."""
    found = Findings(errors=['a'], warnings=['b'])
    found.merge(Findings(errors=['c'], warnings=['d']))
    assert found == Findings(errors=['a', 'c'], warnings=['b', 'd'])


# -- Recording --


def test_errors_and_warnings_are_recorded_to_separate_files(
    local: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A blocking error never lands among the advice, and both are kept."""
    warnings_target = tmp_path / 'warnings' / 'title.txt'
    errors_target = tmp_path / 'errors' / 'title.txt'
    local.setenv('PR_WARNINGS_FILE', str(warnings_target))
    local.setenv('PR_ERRORS_FILE', str(errors_target))
    found = Findings(
        errors=['title: not Conventional Commit form'],
        warnings=['title: not a verb', 'title: contains a plan identifier'],
    )

    assert found.emit('title OK') == 1
    assert warnings_target.read_text(encoding='utf-8').splitlines() == [
        'title: not a verb',
        'title: contains a plan identifier',
    ]
    assert errors_target.read_text(encoding='utf-8').splitlines() == [
        'title: not Conventional Commit form'
    ]


@pytest.mark.parametrize('variable', ['PR_WARNINGS_FILE', 'PR_ERRORS_FILE'])
def test_a_clean_check_writes_no_file(
    local: pytest.MonkeyPatch, tmp_path: Path, variable: str
) -> None:
    """A check with nothing to record creates no file, not even an empty one."""
    target = tmp_path / 'findings.txt'
    local.setenv(variable, str(target))

    Findings().emit('ok')

    assert not target.exists()


def test_recording_is_off_without_the_variables(
    local: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A local run sets neither variable, and writes nothing to the working tree."""
    local.chdir(tmp_path)

    Findings(errors=['not Conventional Commit form'], warnings=['not a verb']).emit(
        'ok'
    )

    assert list(tmp_path.iterdir()) == []


def test_a_warnings_recording_failure_is_a_warning_and_still_passes(
    local: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A warnings file that cannot be written loses no warning and fails nothing."""
    blocker = tmp_path / 'blocker'
    blocker.write_text('not a directory', encoding='utf-8')
    target = blocker / 'warnings' / 'title.txt'
    local.setenv('PR_WARNINGS_FILE', str(target))

    assert Findings(warnings=['title: not a verb']).emit('ok') == 0
    assert f'warning: could not record warnings to {target}' in capsys.readouterr().err


def test_an_errors_recording_failure_is_a_warning_and_still_fails(
    local: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An errors file that cannot be written loses no error and changes no verdict."""
    blocker = tmp_path / 'blocker'
    blocker.write_text('not a directory', encoding='utf-8')
    target = blocker / 'errors' / 'title.txt'
    local.setenv('PR_ERRORS_FILE', str(target))

    assert Findings(errors=['title: ends with a period']).emit('ok') == 1
    assert f'warning: could not record errors to {target}' in capsys.readouterr().err


@pytest.mark.parametrize(
    'target', ['elsewhere/title.txt', 'repo/../elsewhere/title.txt']
)
def test_a_findings_file_outside_the_allowed_roots_is_refused(
    local: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    target: str,
) -> None:
    """A path outside the checkout and the temporary directories is refused."""
    local.delenv('RUNNER_TEMP', raising=False)
    (tmp_path / 'repo').mkdir()
    (tmp_path / 'tmp').mkdir()
    local.chdir(tmp_path / 'repo')
    local.setattr('tempfile.gettempdir', lambda: str(tmp_path / 'tmp'))
    local.setenv('PR_WARNINGS_FILE', str(tmp_path / target))

    assert Findings(warnings=['title: not a verb']).emit('ok') == 0

    assert not (tmp_path / 'elsewhere').exists()
    assert 'could not record warnings' in capsys.readouterr().err


def test_a_findings_file_under_runner_temp_is_written(
    local: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RUNNER_TEMP is an allowed root."""
    (tmp_path / 'repo').mkdir()
    local.chdir(tmp_path / 'repo')
    local.setattr('tempfile.gettempdir', lambda: str(tmp_path / 'tmp'))
    local.setenv('RUNNER_TEMP', str(tmp_path / 'runner'))
    target = tmp_path / 'runner' / 'warnings' / 'title.txt'
    local.setenv('PR_WARNINGS_FILE', str(target))

    Findings(warnings=['title: not a verb']).emit('ok')

    assert target.read_text(encoding='utf-8') == 'title: not a verb\n'
