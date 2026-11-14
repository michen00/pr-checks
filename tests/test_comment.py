"""Tests for the comment action: its script against a stub `gh`, and its wiring.

The comment must be idempotent across every push to a pull request: findings create
it or edit it, no findings delete it, and a clean run with no comment calls no write
endpoint at all.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

__all__ = ()

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / 'comment' / 'post.sh'
_SHA = 'a' * 40
_MARKER = '<!-- pr-checks:findings -->'
_OPEN_PULL = {'number': 7, 'state': 'open', 'head': {'sha': _SHA}}

# GitHub's cap on a comment body. Repeated here rather than read from the script, so a
# wrong constant there fails here.
_COMMENT_MAX = 65536

# A stub `gh`: it logs each call, answers a `--jq` lookup by running the real jq on
# PULLS, prints COMMENTS for the comment listing, and echoes each write.
_STUB = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >>"$GH_LOG"
case "$*" in
  *"/commits/"*"/pulls"*)
    while [ "$1" != --jq ]; do shift; done
    jq -r "$2" <<<"$PULLS" ;;
  *"/issues/7/comments"*) LIST_BRANCH ;;
  *"-X PATCH"*)
    last="${@: -1}"; printf 'PATCH %s\n%s\n' "$*" "$(cat "${last#body=@}")" ;;
  *"-X DELETE"*) echo "DELETE $*" ;;
  *"pr comment"*) printf 'POST\n%s\n' "$(cat "${@: -1}")" ;;
esac
"""


def _run(  # noqa: PLR0913
    tmp_path: Path,
    *,
    warnings: dict[str, str] | None = None,
    errors: dict[str, str] | None = None,
    comments: tuple[tuple[int, str, str], ...] = (),
    pulls: tuple[dict[str, Any], ...] = (_OPEN_PULL,),
    findings_format: str | None = '1\n',
    handoff: str = 'true',
    head_sha: str = _SHA,
    list_branch: str = 'printf "%s" "$COMMENTS"',
) -> subprocess.CompletedProcess[str]:
    """Run the script on a findings directory, against the stub `gh`.

    `comments` lists the pull request's comments as (id, user type, body).
    """
    findings = tmp_path / 'findings'
    findings.mkdir()
    if findings_format is not None:
        (findings / 'format').write_text(findings_format, encoding='utf-8')
    for kind, files in (('warnings', warnings), ('errors', errors)):
        if files is not None:
            (findings / kind).mkdir()
            for stem, text in files.items():
                (findings / kind / f'{stem}.txt').write_text(text, encoding='utf-8')

    binaries = tmp_path / 'bin'
    binaries.mkdir()
    stub = binaries / 'gh'
    stub.write_text(_STUB.replace('LIST_BRANCH', list_branch), encoding='utf-8')
    stub.chmod(0o755)

    return subprocess.run(
        ['bash', str(_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env={
            'PATH': f'{binaries}{os.pathsep}{os.environ["PATH"]}',
            'GH_LOG': str(tmp_path / 'gh.log'),
            'PULLS': json.dumps(list(pulls)),
            'COMMENTS': json.dumps(
                [
                    {'id': id_, 'user': {'type': kind}, 'body': body}
                    for id_, kind, body in comments
                ]
            ),
            'REPO': 'owner/name',
            'HEAD_SHA': head_sha,
            'FINDINGS_DIR': str(findings),
            'MARKER': _MARKER,
            'HANDOFF': handoff,
        },
    )


def _gh_calls(tmp_path: Path) -> list[str]:
    """Return every `gh` call the stub logged."""
    log = tmp_path / 'gh.log'
    return log.read_text(encoding='utf-8').splitlines() if log.exists() else []


# -- Usage: what a run does with each kind of result --


def test_findings_with_no_comment_are_posted(tmp_path: Path) -> None:
    """The first run that finds anything creates the comment, marker first."""
    result = _run(tmp_path, warnings={'title': 'title: not a verb\n'})

    assert result.returncode == 0, result.stderr
    posted = result.stdout.split('POST\n', 1)[1]
    assert posted.startswith(f'{_MARKER}\n')
    assert '- title: not a verb' in posted


def test_findings_replace_this_actions_comment(tmp_path: Path) -> None:
    """A later run edits the bot comment that starts with the marker."""
    result = _run(
        tmp_path,
        warnings={'title': 'title: not a verb\n'},
        comments=((41, 'User', 'hello'), (42, 'Bot', f'{_MARKER}\nold')),
    )

    assert 'PATCH' in result.stdout
    assert 'issues/comments/42' in result.stdout
    assert 'title: not a verb' in result.stdout
    assert 'POST' not in result.stdout


def test_no_findings_delete_the_comment(tmp_path: Path) -> None:
    """Once nothing is left to say, the comment goes."""
    result = _run(tmp_path, warnings={}, comments=((42, 'Bot', f'{_MARKER}\nold'),))
    assert 'DELETE' in result.stdout
    assert 'issues/comments/42' in result.stdout


@pytest.mark.parametrize('warnings', [{}, None], ids=['empty', 'absent'])
def test_a_clean_run_with_no_comment_writes_nothing(
    tmp_path: Path, warnings: dict[str, str] | None
) -> None:
    """With no findings and no comment, no write endpoint is called."""
    result = _run(tmp_path, warnings=warnings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ''


def test_a_persons_comment_with_the_marker_is_left_alone(tmp_path: Path) -> None:
    """Only a bot's comment is this action's, so a person quoting the marker is not."""
    result = _run(
        tmp_path,
        warnings={'title': 'title: not a verb\n'},
        comments=((42, 'User', f'{_MARKER}\nquoted'),),
    )
    assert 'POST' in result.stdout
    assert 'PATCH' not in result.stdout


# -- Findings this run cannot read leave the comment alone --


@pytest.mark.parametrize('findings_format', [None, '2\n'], ids=['missing', 'newer'])
def test_findings_in_another_format_change_nothing(
    tmp_path: Path, findings_format: str | None
) -> None:
    """A run that did not finish, or a newer layout, calls no API at all."""
    result = _run(
        tmp_path,
        warnings={},
        comments=((42, 'Bot', f'{_MARKER}\nold'),),
        findings_format=findings_format,
    )

    assert result.returncode == 0
    assert 'the comment is unchanged' in result.stdout
    assert _gh_calls(tmp_path) == []


# -- The pull request comes from the API --


def test_a_head_sha_that_is_not_a_sha_is_refused(tmp_path: Path) -> None:
    """The SHA goes into an API path, so anything else stops the run."""
    result = _run(tmp_path, warnings={'title': 'x\n'}, head_sha='main; rm -rf /')

    assert result.returncode == 1
    assert 'not a commit SHA' in result.stdout
    assert _gh_calls(tmp_path) == []


@pytest.mark.parametrize(
    'pulls',
    [
        pytest.param((), id='no pull request'),
        pytest.param(({**_OPEN_PULL, 'state': 'closed'},), id='closed'),
        pytest.param(({**_OPEN_PULL, 'head': {'sha': 'b' * 40}},), id='head moved on'),
    ],
)
def test_no_open_pull_request_with_this_head_means_no_comment(
    tmp_path: Path, pulls: tuple[dict[str, Any], ...]
) -> None:
    """A run whose head is no longer an open pull request's head comments nowhere."""
    result = _run(tmp_path, warnings={'title': 'x\n'}, pulls=pulls)

    assert result.returncode == 0
    assert 'nothing to comment on' in result.stdout
    assert 'POST' not in result.stdout


def test_a_pull_request_number_that_is_not_a_number_is_refused(tmp_path: Path) -> None:
    """The number goes into an API path, so anything else stops the run."""
    result = _run(
        tmp_path, warnings={'title': 'x\n'}, pulls=({**_OPEN_PULL, 'number': '7/x'},)
    )
    assert result.returncode == 1
    assert 'not a pull request number' in result.stdout


# -- What the comment says --


def _section(text: str, heading: str) -> str:
    """Return the text from `**heading**` to the next bold heading or the end."""
    start = text.index(f'**{heading}**')
    end = text.find('\n**', start + 1)
    return text[start : end if end != -1 else len(text)]


def test_findings_are_grouped_by_the_check_that_raised_them(tmp_path: Path) -> None:
    """The file name is the check's, and each finding lands under its own."""
    result = _run(
        tmp_path,
        warnings={'title': 'title: not a verb\n', 'body': 'a TBD marker\n'},
    )

    assert 'title: not a verb' in _section(result.stdout, 'title')
    assert 'a TBD marker' not in _section(result.stdout, 'title')
    assert 'a TBD marker' in _section(result.stdout, 'body')


def test_errors_come_first_under_their_own_heading(tmp_path: Path) -> None:
    """What blocks the merge is read before what only advises."""
    result = _run(
        tmp_path,
        warnings={'title': "title: subject may not be imperative ('adds')\n"},
        errors={'title': 'title: 53 chars exceeds hard max 50; cut at least 3\n'},
    )

    text = result.stdout
    assert text.index('Why the checks failed') < text.index('exceeds hard max')
    assert text.index('exceeds hard max') < text.index('Advisory findings')
    assert text.index('Advisory findings') < text.index('may not be imperative')


def test_warnings_alone_do_not_claim_a_failure(tmp_path: Path) -> None:
    """A passing run with advice never says the checks failed."""
    result = _run(tmp_path, warnings={'title': 'title: not a verb\n'})

    assert 'Advisory findings' in result.stdout
    assert 'Why the checks failed' not in result.stdout


@pytest.mark.parametrize(
    ('warnings', 'errors'),
    [
        ({'body': 'unfilled template placeholder <placeholder>\n'}, None),
        (None, {'body': 'a slot <img src=x onerror=alert(1)>\n'}),
        ({'<img src=x>': 'a finding\n'}, None),
    ],
    ids=['warning', 'error', 'file name'],
)
def test_html_in_a_finding_renders_as_text(
    tmp_path: Path, warnings: dict[str, str] | None, errors: dict[str, str] | None
) -> None:
    """A finding can quote the author, so its HTML is escaped, as is a file's name."""
    result = _run(tmp_path, warnings=warnings, errors=errors)

    assert '<placeholder>' not in result.stdout
    assert '<img' not in result.stdout
    assert '&lt;' in result.stdout


def test_a_finding_cannot_carry_a_disguised_link(tmp_path: Path) -> None:
    """Markdown link syntax is escaped too, so a label cannot hide where it goes."""
    result = _run(
        tmp_path,
        warnings={
            'body': '<details><summary>go</summary>[click](http://evil.example)</details>\n'
        },
    )

    assert '<details><summary>go</summary>' not in result.stdout
    assert '[click](' not in result.stdout
    assert r'\[click\]' in result.stdout


def test_an_oversized_body_is_cut_where_a_reader_can_see(tmp_path: Path) -> None:
    """Escaping can carry a body past GitHub's limit; it is cut, with a notice.

    `&` becomes `&amp;`, so this finding grows fivefold.
    """
    result = _run(tmp_path, warnings={'body': f'unfilled slot <a{"&" * 20000}>\n'})

    posted = result.stdout.split('POST\n', 1)[1]
    assert len(posted.encode()) <= _COMMENT_MAX
    assert 'unfilled slot' in posted
    assert 'cut off here' in posted
    assert posted.rstrip().endswith('</details>')


def test_findings_that_fit_are_not_cut(tmp_path: Path) -> None:
    """A budget that was merely too small would cut every comment."""
    result = _run(tmp_path, warnings={'title': 'title: not a verb\n'})
    assert 'cut off here' not in result.stdout


def test_the_handoff_names_this_pull_request(tmp_path: Path) -> None:
    """The prompt names the pull request, and asks for a decision on each warning."""
    result = _run(tmp_path, warnings={'title': 'title: not a verb\n'})

    assert 'Hand these to a coding agent' in result.stdout
    assert 'owner/name#7' in result.stdout
    assert 'gh pr view 7 --repo owner/name --comments' in result.stdout
    assert 'decide whether it is worth acting on' in result.stdout


def test_the_handoff_can_be_left_out(tmp_path: Path) -> None:
    """`handoff: false` leaves the prompt off."""
    result = _run(tmp_path, warnings={'title': 'title: not a verb\n'}, handoff='false')

    assert 'title: not a verb' in result.stdout
    assert 'Hand these to a coding agent' not in result.stdout


def test_two_marked_comments_do_not_crash_the_lookup(tmp_path: Path) -> None:
    """Two racing runs can each post once; the next run edits the first."""
    comments = json.dumps(
        [
            {'id': 42, 'user': {'type': 'Bot'}, 'body': f'{_MARKER}\na'},
            {'id': 43, 'user': {'type': 'Bot'}, 'body': f'{_MARKER}\nb'},
        ]
    )
    result = _run(
        tmp_path,
        warnings={'title': 'title: not a verb\n'},
        list_branch=f"printf '%s' '{comments}'",
    )

    assert result.returncode == 0, result.stderr
    assert 'issues/comments/42' in result.stdout
    assert 'issues/comments/43' not in result.stdout


# -- The action and the workflow that calls it --

_ACTION: dict[str, Any] = yaml.safe_load(
    (_ROOT / 'comment' / 'action.yml').read_text(encoding='utf-8')
)


def _workflow(name: str) -> dict[Any, Any]:
    """Return a parsed workflow; YAML 1.1 parses its `on:` key as True."""
    workflow: dict[Any, Any] = yaml.safe_load(
        (_ROOT / '.github' / 'workflows' / name).read_text(encoding='utf-8')
    )
    return workflow


def test_the_action_downloads_the_triggering_runs_artifact() -> None:
    """The findings come from the run that triggered this one."""
    download = next(
        step
        for step in _ACTION['runs']['steps']
        if step.get('uses', '').startswith('actions/download-artifact@')
    )
    assert download['with']['run-id'] == '${{ github.event.workflow_run.id }}'
    assert download['continue-on-error'] is True


def test_every_input_of_the_action_is_used() -> None:
    """An input the steps never read would be accepted and silently ignored."""
    text = (_ROOT / 'comment' / 'action.yml').read_text(encoding='utf-8')
    assert [
        name for name in _ACTION['inputs'] if f'inputs.{name} }}}}' not in text
    ] == []


def test_the_caller_runs_when_the_checks_finish_however_they_ended() -> None:
    """It names the checks' workflow by its name, and filters on no conclusion."""
    caller = _workflow('pr-checks-comment.yml')
    triggers = caller['on'] if 'on' in caller else caller[True]

    assert triggers == {
        'workflow_run': {
            'workflows': [_workflow('pr-checks.yml')['name']],
            'types': ['completed'],
        }
    }


def test_the_caller_holds_exactly_the_scopes_it_needs() -> None:
    """Reading the artifact, and writing the comment; nothing else."""
    assert _workflow('pr-checks-comment.yml')['permissions'] == {
        'contents': 'read',
        'actions': 'read',
        'pull-requests': 'write',
    }


def test_the_caller_runs_the_copy_on_the_default_branch() -> None:
    """A checkout with a `ref:` could fetch the pull request's code into this job."""
    steps = _workflow('pr-checks-comment.yml')['jobs']['comment']['steps']
    checkout = next(
        step for step in steps if step['uses'].startswith('actions/checkout@')
    )

    assert 'ref' not in checkout['with']
    assert steps[-1] == {'uses': './comment'}


def test_the_caller_never_overlaps_itself() -> None:
    """The upsert reads, then writes, so a canceled run could leave a duplicate."""
    assert (
        _workflow('pr-checks-comment.yml')['concurrency']['cancel-in-progress'] is False
    )
