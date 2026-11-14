"""Tests for the title check's command line: its arguments and exit codes."""

import pytest

from pr_checks import title

__all__ = ()


@pytest.fixture(autouse=True)
def local(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Run every test as a terminal would, with no title in the environment."""
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.delenv('PR_TITLE', raising=False)
    monkeypatch.delenv('PR_WARNINGS_FILE', raising=False)
    monkeypatch.delenv('PR_ERRORS_FILE', raising=False)
    return monkeypatch


def test_the_exit_code_says_whether_anything_blocks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exit 0 when nothing blocks and 1 when something does."""
    assert title.main(['feat: add a rule']) == 0
    assert capsys.readouterr().out == 'title OK\n'

    assert title.main(['Add a rule']) == 1
    assert 'error: title: not Conventional Commit form' in capsys.readouterr().err


def test_a_warning_alone_does_not_fail(capsys: pytest.CaptureFixture[str]) -> None:
    """A warnings-only title exits 0, and the log says it passed with warnings."""
    assert title.main(['feat: added a rule']) == 0
    assert capsys.readouterr().out == 'title OK (with warnings)\n'


def test_the_title_falls_back_to_pr_title(local: pytest.MonkeyPatch) -> None:
    """With no argument, the check reads the PR_TITLE environment variable."""
    local.setenv('PR_TITLE', 'feat: ok')
    assert title.main([]) == 0


def test_no_title_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    """With no argument and no PR_TITLE, the check stops with a usage error."""
    with pytest.raises(SystemExit) as stopped:
        title.main([])

    assert stopped.value.code == 2
    assert 'provide a title argument or set PR_TITLE' in capsys.readouterr().err


def test_the_flag_sets_the_maximum() -> None:
    """A 56-character title fails at the default of 50 and passes at 72."""
    long_title = 'feat: ' + 'a' * 50

    assert title.main([long_title]) == 1
    assert title.main([long_title, '--max-length', '72']) == 0


def test_off_passes_a_long_title_and_says_so(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--max-length off` passes a long title, and the log says so."""
    long_title = 'feat: ' + 'a' * 54  # 60 chars

    assert title.main([long_title, '--max-length', 'off']) == 0
    assert capsys.readouterr() == ('title OK, length not checked\n', '')


@pytest.mark.parametrize('setting', ['0', '-3', 'sixty'])
def test_an_unusable_flag_is_a_usage_error(
    setting: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bad `--max-length` stops with a usage error that names the flag."""
    with pytest.raises(SystemExit) as stopped:
        title.main(['docs: fix a typo', '--max-length', setting])

    assert stopped.value.code == 2
    assert 'argument --max-length: expected a positive whole number or off' in (
        capsys.readouterr().err
    )


def test_plan_identifiers_warn_only_with_the_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--warn-plan-ids` turns the plan identifier warning on."""
    assert title.main(['fix: retry S3 uploads']) == 0
    assert 'plan identifier' not in capsys.readouterr().err

    assert title.main(['fix: retry S3 uploads', '--warn-plan-ids']) == 0
    assert 'title: contains a plan identifier' in capsys.readouterr().err
