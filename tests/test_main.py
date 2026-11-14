"""Tests for `python -m pr_checks`, the command the action runs."""

from pathlib import Path

import pytest

from pr_checks.__main__ import FINDINGS_FORMAT, main

__all__ = ()

_BODY = '## Summary\n\nWhy, then what.\n\n## Testing\n\n- [x] CI green\n'


@pytest.fixture(autouse=True)
def pull_request(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Run every test as a terminal would, on a clean pull request by a person."""
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.setenv('PR_TITLE', 'feat: add a rule')
    monkeypatch.setenv('PR_BODY', _BODY)
    monkeypatch.setenv('PR_AUTHOR', 'octocat')
    return monkeypatch


def _files(directory: Path) -> dict[str, str]:
    """Return every file under `directory`, by relative path, with its text."""
    return {
        str(path.relative_to(directory)): path.read_text(encoding='utf-8')
        for path in sorted(directory.rglob('*'))
        if path.is_file()
    }


# -- Usage: what the action runs --


def test_the_action_checks_the_title_and_body_and_writes_the_findings(
    pull_request: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The title, body and author come from the environment; the rules from options.

    The findings directory holds one file per check and kind, and `format` last.
    """
    pull_request.setenv('PR_TITLE', 'feat: added a rule.')
    findings = tmp_path / 'findings'

    code = main(
        [
            f'--findings-dir={findings}',
            '--required-sections=Summary\nTesting\nReview focus',
        ]
    )

    assert code == 1
    assert capsys.readouterr().out == 'title: 1 error(s)\nbody OK (with warnings)\n'
    assert _files(findings) == {
        'errors/title.txt': 'title: must not end with a period\n',
        'format': f'{FINDINGS_FORMAT}\n',
        'warnings/body.txt': (
            "missing template section '## Review focus' — add it unless the change "
            'is too small to need one\n'
        ),
        'warnings/title.txt': "title: subject may not be imperative ('added')\n",
    }


# -- Exit codes and what is printed --


def test_a_clean_pull_request_passes(capsys: pytest.CaptureFixture[str]) -> None:
    """Exit 0, with a line per check."""
    assert main([]) == 0
    assert capsys.readouterr() == ('title OK\nbody OK\n', '')


def test_warnings_alone_pass(
    pull_request: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A warning is printed and does not fail the run."""
    pull_request.setenv('PR_BODY', 'TODO\n')
    assert main([]) == 0
    assert capsys.readouterr().out == 'title OK\nbody OK (with warnings)\n'


def test_an_unchecked_length_is_said(capsys: pytest.CaptureFixture[str]) -> None:
    """With `--max-length=off`, the title's line says its length was not checked."""
    assert main(['--max-length=off']) == 0
    assert capsys.readouterr().out == 'title OK, length not checked\nbody OK\n'


def test_a_body_error_fails_the_run(pull_request: pytest.MonkeyPatch) -> None:
    """An untagged fence in the body is an error."""
    pull_request.setenv('PR_BODY', '```\nx\n```\n')
    assert main([]) == 1


def test_a_missing_body_is_an_empty_one(pull_request: pytest.MonkeyPatch) -> None:
    """GitHub sends no body for a pull request whose description is empty."""
    pull_request.delenv('PR_BODY')
    assert main(['--required-sections=Summary']) == 0


# -- Options --


@pytest.mark.parametrize(
    ('options', 'printed'),
    [
        (['--check-title=false'], 'body OK\n'),
        (['--check-body=FALSE'], 'title OK\n'),
        (['--check-title=false', '--check-body=false'], ''),
    ],
)
def test_a_check_can_be_turned_off(
    options: list[str], printed: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A check that is off does not run and prints nothing."""
    assert main(options) == 0
    assert capsys.readouterr().out == printed


def test_a_bot_author_is_skipped(
    pull_request: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A bot's pull request is not checked, and its findings directory is empty."""
    pull_request.setenv('PR_AUTHOR', 'dependabot[bot]')
    pull_request.setenv('PR_TITLE', 'Bump lib from 1 to 2')

    assert main([f'--findings-dir={tmp_path}']) == 0
    assert capsys.readouterr().out == 'dependabot[bot] is a bot, so no check runs\n'
    assert _files(tmp_path) == {'format': f'{FINDINGS_FORMAT}\n'}


def test_a_bot_author_can_be_checked(pull_request: pytest.MonkeyPatch) -> None:
    """With `--skip-bot-authors=false`, a bot's title answers to the rules."""
    pull_request.setenv('PR_AUTHOR', 'dependabot[bot]')
    pull_request.setenv('PR_TITLE', 'Bump lib from 1 to 2')
    assert main(['--skip-bot-authors=false']) == 1


def test_plan_identifiers_warn_only_when_asked(
    pull_request: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--warn-plan-ids=true` turns the plan identifier warning on."""
    pull_request.setenv('PR_TITLE', 'fix: retry S3 uploads')

    main([])
    assert 'plan identifier' not in capsys.readouterr().err
    main(['--warn-plan-ids=true'])
    assert 'title: contains a plan identifier' in capsys.readouterr().err


def test_blank_lines_and_spaces_in_the_sections_are_ignored(
    pull_request: pytest.MonkeyPatch,
) -> None:
    """A YAML block scalar can leave blank lines and indentation; neither counts."""
    pull_request.setenv('PR_BODY', '## Summary\n')
    assert main(['--required-sections=\n  Summary  \n\n']) == 0


# -- Usage errors --


def test_an_empty_title_is_a_usage_error(
    pull_request: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run outside a pull request event has no title to check."""
    pull_request.delenv('PR_TITLE')
    with pytest.raises(SystemExit) as stopped:
        main([])
    assert stopped.value.code == 2
    assert 'PR_TITLE is empty' in capsys.readouterr().err


@pytest.mark.parametrize(
    ('option', 'message'),
    [
        (
            '--check-body=yes',
            "argument --check-body: expected true or false, not 'yes'",
        ),
        ('--max-length=0', 'argument --max-length: expected a positive whole number'),
    ],
)
def test_an_unusable_option_is_a_usage_error(
    option: str, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bad option stops the run with a message that names it."""
    with pytest.raises(SystemExit) as stopped:
        main([option])
    assert stopped.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize('target', ['elsewhere', 'repo/../elsewhere'])
def test_a_findings_dir_outside_the_allowed_roots_is_refused(
    pull_request: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    target: str,
) -> None:
    """The directory must be under the checkout or a temporary directory."""
    pull_request.delenv('RUNNER_TEMP', raising=False)
    (tmp_path / 'repo').mkdir()
    pull_request.chdir(tmp_path / 'repo')
    pull_request.setattr('tempfile.gettempdir', lambda: str(tmp_path / 'tmp'))

    with pytest.raises(SystemExit) as stopped:
        main([f'--findings-dir={tmp_path / target}'])

    assert stopped.value.code == 2
    assert 'argument --findings-dir' in capsys.readouterr().err
    assert not (tmp_path / 'elsewhere').exists()


def test_a_findings_dir_under_runner_temp_is_written(
    pull_request: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RUNNER_TEMP, where the action puts the directory, is an allowed root."""
    (tmp_path / 'repo').mkdir()
    pull_request.chdir(tmp_path / 'repo')
    pull_request.setattr('tempfile.gettempdir', lambda: str(tmp_path / 'tmp'))
    pull_request.setenv('RUNNER_TEMP', str(tmp_path / 'runner'))

    assert main([f'--findings-dir={tmp_path / "runner" / "findings"}']) == 0
    assert (tmp_path / 'runner' / 'findings' / 'format').is_file()
