"""Tests for the body check: an untagged code fence blocks; the rest only advises."""

import io
import time
from pathlib import Path

import pytest

from pr_checks import body as body_check
from pr_checks.body import check_body
from pr_checks.findings import Findings

__all__ = ()

_SECTIONS = ('Summary', 'Testing')

_GOOD_BODY = """## Summary

Why, then what.

## Testing

- [x] CI green
"""

# -- Usage: how a caller checks a body --


def test_a_body_is_checked_against_the_sections_the_caller_names() -> None:
    """The caller names the sections, so each repository keeps its own template.

    A missing section advises rather than blocks, because a small change may not
    need it.
    """
    found = check_body(_GOOD_BODY, ['Summary', 'Testing', 'Review focus'])

    assert not check_body(_GOOD_BODY, _SECTIONS).warnings
    assert found.ok
    assert found.warnings == [
        (
            "missing template section '## Review focus' — add it unless the change is "
            'too small to need one'
        )
    ]


def test_no_section_is_expected_by_default() -> None:
    """Without a list of sections, a body with no headings has no section finding."""
    assert check_body('Fix the typo in the README.\n') == Findings()


# -- Sections --


def test_a_wrong_level_heading_does_not_satisfy() -> None:
    """'### Summary' does not satisfy the '## Summary' section."""
    found = check_body('### Summary\n\nwhy\n\n### Testing\n\n- [x] ok\n', _SECTIONS)
    assert [w.split(' — ')[0] for w in found.warnings] == [
        "missing template section '## Summary'",
        "missing template section '## Testing'",
    ]


def test_a_heading_with_extra_text_is_accepted() -> None:
    """A level-two heading whose text starts with the section satisfies it."""
    body = '## Summary of changes\n\nwhy\n\n## Testing details\n\n- [x] ok\n'
    assert not check_body(body, _SECTIONS).warnings


# -- Fences: an untagged fence blocks --


def test_an_untagged_fence_blocks() -> None:
    """A fence without a language tag blocks, since one can always be added."""
    found = check_body(
        '## Summary\n\n```\nx\n```\n\n## Testing\n\n- [x] ok\n', _SECTIONS
    )
    assert found.errors == [
        (
            'a fenced code block has no language tag — add one, using text when the '
            'block is not code'
        )
    ]
    assert not found.warnings


@pytest.mark.parametrize(
    ('body', 'untagged'),
    [
        pytest.param('```\nraw\n```\n', True, id='backticks'),
        pytest.param('```python\nx\n```\n', False, id='tagged backticks'),
        pytest.param('~~~\nraw\n~~~\n', True, id='tildes'),
        pytest.param('~~~python\nx\n~~~\n', False, id='tagged tildes'),
        pytest.param('````\nraw\n````\n', True, id='four backticks'),
        pytest.param(
            '````markdown\n```python\nprint(1)\n```\n````\nafter\n',
            False,
            id='tagged fence inside a longer one',
        ),
        pytest.param(
            '````text\n```\nstill code\n````\nprose\n',
            False,
            id='shorter run stays open',
        ),
        pytest.param(
            '~~~text\n```\n~~~\nprose\n', False, id='other character stays open'
        ),
        pytest.param(
            '```text\n```python\n```\nprose\n', False, id='tagged run stays open'
        ),
        pytest.param(
            '```x``` is inline\n```python\ncode\n```\n',
            False,
            id='inline span is not a fence',
        ),
        pytest.param('- step\n  ```\n  raw\n  ```\n', True, id='indented in a list'),
        pytest.param('```text\nraw\n', False, id='unclosed runs to the end'),
        pytest.param(
            'Example:\n\n    ```\n    raw\n    ```\n',
            False,
            id='bare run inside indented code',
        ),
        pytest.param(
            '```text\n    ```\n```\n', False, id='indented run inside a tagged fence'
        ),
        pytest.param(
            '<!--\nExample:\n```\nraw\n```\n-->\n',
            False,
            id='inside a multi-line HTML comment',
        ),
        pytest.param(
            '<details>\n```\nraw\n```\n</details>\n',
            False,
            id='details without a blank line',
        ),
        pytest.param('<pre>\n```\nraw\n```\n</pre>\n', False, id='inside pre'),
        pytest.param('```\r\nraw\r\n```\r\n', True, id='CRLF line endings'),
    ],
)
def test_a_fence_is_what_commonmark_parses_as_one(body: str, *, untagged: bool) -> None:
    """A fence is reported exactly when CommonMark parses one with no tag."""
    found = check_body(body)
    assert any('language tag' in e for e in found.errors) is untagged


def test_an_untagged_fence_holding_a_marker_reports_only_the_fence() -> None:
    """The fence check reads the raw body; the marker inside it is code."""
    found = check_body(
        '## Summary\n\n```\nTODO\n```\n\n## Testing\n\n- [x] ok\n', _SECTIONS
    )
    assert any('language' in e for e in found.errors)
    assert not any('TODO' in f for f in (*found.errors, *found.warnings))


# -- Leftover template text: each advises --


def test_a_placeholder_warns_and_names_the_slot() -> None:
    """The warning quotes the slot, so the author can find it in a long body."""
    body = (
        '## Summary\n\nwhy\n\n## Testing\n\n- [x] ok\n'
        '- [ ] <change-specific verification>\n'
    )
    found = check_body(body, _SECTIONS)

    assert found.ok
    assert found.warnings == [
        (
            'unfilled template placeholder <change-specific verification> — replace it '
            'with the real value, or delete the line'
        )
    ]


def test_an_html_tag_is_not_a_placeholder() -> None:
    """An HTML tag such as <details> is not mistaken for a placeholder."""
    body = (
        '## Summary\n\n<details><summary>x</summary>y</details>\n\n'
        '## Testing\n\n- [x] ok\n'
    )
    assert not check_body(body, _SECTIONS).warnings


def test_a_stray_angle_bracket_does_not_hide_a_placeholder() -> None:
    """A `<` before a slot on the same line does not swallow the slot."""
    body = '## Summary\n\nWhen a < b, use <reason>.\n\n## Testing\n\n- [x] ok\n'
    found = check_body(body, _SECTIONS)
    assert any('placeholder <reason>' in w for w in found.warnings)


def test_a_todo_marker_warns_only() -> None:
    """A TODO marker in an otherwise complete body advises but does not block."""
    found = check_body('## Summary\n\nwhy\n\n## Testing\n\n- [ ] TODO wire up CI\n')
    assert found.ok
    assert found.warnings == [
        (
            'a TODO marker is still in the body — resolve it, or say in the body why '
            'it stays'
        )
    ]


@pytest.mark.parametrize(
    'directive',
    [
        '<!-- markdownlint-disable MD033 -->',
        '<!-- markdownlint-enable MD033 -->',
        '<!-- markdownlint-disable-next-line MD033 -->',
        '<!-- markdownlint-disable-file MD033 -->',
        '<!-- markdownlint-capture -->',
        '<!-- markdownlint-restore -->',
        '<!-- markdownlint-disable -->',
        '<!--markdownlint-disable   MD033  MD013-->',
    ],
)
def test_a_markdownlint_directive_warns_only(directive: str) -> None:
    """Every markdownlint directive form advises but does not block."""
    found = check_body(f'## Summary\n\nwhy\n\n{directive}\n\n## Testing\n\n- [x] ok\n')
    assert found.ok
    assert any('markdownlint' in w for w in found.warnings)


def test_the_markdownlint_warning_quotes_only_the_directive() -> None:
    """A directive can share its line with markup the body has to keep.

    The warning quotes the comment, which is all that has to go, so a remedy of
    "delete the line" does not take a `<details>` block with it.
    """
    body = (
        '## Summary\n\nwhy\n\n<details><!-- markdownlint-disable MD033 -->\n'
        '<summary>Files touched</summary>\n</details>\n\n'
        '## Testing\n\n- [x] ok\n'
    )
    found = check_body(body, _SECTIONS)

    assert found.ok
    assert any('<!-- markdownlint-disable MD033 -->' in w for w in found.warnings)
    assert not any('<details>' in w for w in found.warnings)


@pytest.mark.parametrize(
    'body',
    [
        pytest.param(
            '## Summary\n\n<!-- kept deliberately for the next reader -->\n',
            id='an ordinary HTML comment',
        ),
        pytest.param(
            '## Summary\n\nI dropped the markdownlint-disable lines.\n',
            id='prose naming a directive',
        ),
    ],
)
def test_what_is_not_a_directive_is_not_reported(body: str) -> None:
    """Only a markdownlint directive comment is template noise."""
    assert not check_body(body).warnings


def test_every_finding_says_what_to_do_about_it() -> None:
    """Each finding, error or warning, carries its own remedy after a dash.

    The author reading it may never have opened this repository's documentation.
    """
    body = (
        '## Summary\n\nTODO explain <why>\n\n'
        '<!-- markdownlint-disable MD033 -->\n\n'
        '## Testing\n\n```\nnot tagged\n```\n'
    )
    found = check_body(body, _SECTIONS)
    findings = (*found.errors, *found.warnings)

    assert len(findings) == 4
    for finding in findings:
        assert ' — ' in finding, f'no remedy in: {finding}'


# -- Code is shown, not left behind: the noise scans skip it --


@pytest.mark.parametrize(
    'body',
    [
        pytest.param('```python\n# TODO: wire this up\n```\n', id='TODO in a fence'),
        pytest.param('the `TBD` body warning\n', id='TBD in a code span'),
        pytest.param('write ``TODO`` to mean it\n', id='TODO in a double-tick span'),
        pytest.param('```text\nN/A — <reason>\n```\n', id='slot in a fence'),
        pytest.param(
            '```markdown\n<!-- markdownlint-disable MD033 -->\n```\n',
            id='directive in a fence',
        ),
        pytest.param(
            'omit `<!-- markdownlint-disable MD033 -->` from the body\n',
            id='directive in a code span',
        ),
    ],
)
def test_text_in_code_is_not_reported(body: str) -> None:
    """A marker, slot or directive written as code is an example."""
    assert not check_body(body).warnings


@pytest.mark.parametrize(
    'body',
    [
        pytest.param('TODO explain why\n\n```python\nx = 1\n```\n', id='TODO'),
        pytest.param('<reason>\n\n```python\nx = 1\n```\n', id='slot'),
        pytest.param(
            '```markdown\n<!-- markdownlint-capture -->\n```\n\n'
            '<!-- markdownlint-disable MD033 -->\n',
            id='directive',
        ),
        pytest.param(
            '```python\nx = 1\n```\n\nTODO explain\n\n```python\ny = 2\n```\n',
            id='TODO between two fences',
        ),
    ],
)
def test_text_beside_code_is_still_reported(body: str) -> None:
    """Removing code does not hide what is left in the prose around it."""
    found = check_body(body)
    assert found.ok
    assert len(found.warnings) == 1


@pytest.mark.parametrize(
    ('body', 'reported'),
    [
        pytest.param(
            '````markdown\n```python\n<slot>\n```\n````\n',
            False,
            id='inside a nested inner fence',
        ),
        pytest.param('````text\n```\n<slot>\n````\n', False, id='after a shorter run'),
        pytest.param(
            '```text\n```python\n<slot>\n```\n', False, id='after a tagged run'
        ),
        pytest.param('~~~text\n<slot>\n~~~\n', False, id='inside a tilde fence'),
        pytest.param(
            '````markdown\n```python\nx\n```\n````\n<slot>\n',
            True,
            id='after a nested fence closes',
        ),
        pytest.param('```x``` is inline\n<slot>\n', True, id='after an inline span'),
        pytest.param(
            'Example:\n\n    <slot>\n', False, id='inside an indented code block'
        ),
    ],
)
def test_fence_boundaries_decide_what_is_code(body: str, *, reported: bool) -> None:
    """A placeholder is skipped inside a code block and reported outside one."""
    found = check_body(body)
    assert any('placeholder' in w for w in found.warnings) is reported


@pytest.mark.parametrize(
    ('pattern', 'line'),
    [
        pytest.param('_PLACEHOLDER', '<' * 60_000, id='angle brackets'),
        pytest.param('_INLINE_CODE', '`' * 20_000, id='backticks'),
    ],
)
def test_a_long_run_of_one_character_is_scanned_quickly(
    pattern: str, line: str
) -> None:
    """Neither noise pattern backtracks across a long run on one line.

    GitHub caps a body at 65,536 characters. The time the patterns these replaced
    took grew with the square of the run's length, or faster. Each pattern is timed
    alone: the parser's own time on such a body grows only linearly, but varies too
    much between machines for a bound on the whole check.
    """
    scan = getattr(body_check, pattern)
    start = time.perf_counter()
    scan.sub(' ', line)
    assert time.perf_counter() - start < 1


# -- The command line --


@pytest.mark.parametrize('body', [_GOOD_BODY, '## Summary\n\nonly this\n'])
def test_a_missing_section_does_not_fail_the_command(body: str, tmp_path: Path) -> None:
    """The command exits 0 either way, because a missing section only advises."""
    body_file = tmp_path / 'body.md'
    body_file.write_text(body, encoding='utf-8')
    assert (
        body_check.main(['--body-file', str(body_file), '--require', *_SECTIONS]) == 0
    )


def test_an_untagged_fence_fails_the_command(tmp_path: Path) -> None:
    """The command exits 1 when a fence has no language tag."""
    body_file = tmp_path / 'body.md'
    body_file.write_text(_GOOD_BODY + '\n```\nx\n```\n', encoding='utf-8')
    assert body_check.main(['--body-file', str(body_file)]) == 1


def test_the_command_reads_standard_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no `--body-file`, the command reads the body from standard input."""
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.setattr('sys.stdin', io.StringIO('## Summary\n'))

    assert body_check.main(['--require', 'Summary', 'Testing']) == 0
    assert "'## Testing'" in capsys.readouterr().err
