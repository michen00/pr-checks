"""Tests for the subject rules a title and a commit subject share."""

import pytest

from pr_checks.subject import check_subject, max_length_argument, parse_max_length

__all__ = ()

# -- Usage: how a caller checks a subject and reads the result --


def test_a_well_formed_subject_is_clean() -> None:
    """Check a subject, then read the result.

    `ok` answers the question a caller acts on, whether anything blocks, while
    `errors` and `warnings` say what was found.
    """
    found = check_subject('feat: add config precedence')

    assert found.ok
    assert not found.errors
    assert not found.warnings


def test_a_subject_separates_what_blocks_from_what_advises() -> None:
    """One input can produce both kinds of finding.

    `added` is past tense, which is a judgment, so it is a warning and does not
    block. The trailing period is certain, so it is an error and blocks.
    """
    found = check_subject('feat: added a rule.')

    assert not found.ok
    assert found.errors == ['subject: must not end with a period']
    assert found.warnings == ["subject: subject may not be imperative ('added')"]


# -- Errors: certain problems block --


@pytest.mark.parametrize(
    ('subject_line', 'problem'),
    [
        ('add config precedence', "there is no 'type: ' prefix"),
        ('feature: add config precedence', "'feature' is not a type"),
        ('Fix: add config precedence', "the type 'Fix' must be lowercase"),
        ('fix(): add config precedence', 'the scope must not be empty'),
        ('fix:add config precedence', "'fix' must be followed by ': '"),
        ('fix(api) add config precedence', "'fix(api)' must be followed by ': '"),
        ('fix: ', "nothing follows 'fix: '"),
    ],
)
def test_a_malformed_subject_names_the_part_that_breaks_the_form(
    subject_line: str, problem: str
) -> None:
    """The error says which part of the form is wrong, not only that the whole is."""
    found = check_subject(subject_line)
    assert not found.ok
    assert any(f', because {problem}' in e for e in found.errors)


def test_a_trailing_period_blocks() -> None:
    """A subject ending in a period blocks on that period."""
    assert check_subject('feat: add a rule.').errors == [
        'subject: must not end with a period'
    ]


@pytest.mark.parametrize(
    'subject',
    ['feat: Add a rule', 'fix: URL-encode the owner', 'feat: [PLT-12] Add a rule'],
)
def test_a_capitalized_subject_blocks(subject: str) -> None:
    """A capital blocks, after a ticket key too, and a capitalized verb included."""
    found = check_subject(subject)
    assert not found.ok
    assert any('must start lowercase' in error for error in found.errors)


def test_the_word_after_a_ticket_key_is_the_first_word() -> None:
    """The case and mood rules read past a leading ticket key."""
    assert check_subject('feat: [PLT-12] add a rule').ok
    found = check_subject('feat: [PLT-12] added a rule')
    assert found.warnings == ["subject: subject may not be imperative ('added')"]


def test_scope_and_breaking_marker_parse() -> None:
    """A scoped, breaking-change subject parses cleanly."""
    found = check_subject('feat(api)!: drop legacy field')
    assert found.ok
    assert not found.warnings


@pytest.mark.parametrize(
    'scope', ['PR-check', 'API', 'pr check', 'Benchmark Literature']
)
def test_a_scope_may_hold_any_text_but_a_parenthesis(scope: str) -> None:
    """A scope may hold capitals and spaces, such as the title of a page it edits.

    The Conventional Commits specification does not treat its units as
    case-sensitive.
    """
    assert check_subject(f'docs({scope}): preserve a web UI edit').ok


# -- The maximum length --


@pytest.mark.parametrize(('length', 'expected_ok'), [(50, True), (51, False)])
def test_subject_length_boundary(length: int, *, expected_ok: bool) -> None:
    """A subject blocks past the maximum and not at it."""
    found = check_subject('feat: ' + 'a' * (length - 6))
    assert found.ok is expected_ok
    assert not found.warnings


def test_the_length_error_says_how_much_to_cut() -> None:
    """The error gives the length, the maximum and the number to cut."""
    assert check_subject('feat: ' + 'a' * 47, label='title').errors == [
        'title: 53 chars exceeds hard max 50; cut at least 3'
    ]


def test_the_caller_sets_the_maximum() -> None:
    """The maximum named in the error is the maximum that was applied."""
    subject = 'feat: ' + 'a' * 60  # 66 chars
    assert check_subject(subject, max_length=72).ok
    assert check_subject(subject, max_length=60).errors == [
        'subject: 66 chars exceeds hard max 60; cut at least 6'
    ]


def test_an_unchecked_length_keeps_every_other_rule() -> None:
    """With no maximum, a long subject passes and a trailing period still blocks."""
    assert check_subject('feat: ' + 'a' * 194, max_length=None).ok  # 200 chars
    assert check_subject('fix: guard the empty body.', max_length=None).errors == [
        'subject: must not end with a period'
    ]


@pytest.mark.parametrize(
    ('subject', 'errors'),
    [
        pytest.param('feat: ' + 'a' * 44 + ' (#22)', [], id='50 typed, suffixed'),
        pytest.param(
            'feat: ' + 'a' * 45 + ' (#22)',
            ['subject: 51 chars exceeds hard max 50; cut at least 1'],
            id='51 typed, suffixed',
        ),
        pytest.param(
            'feat: ' + 'a' * 39 + ' (#22) b',
            ['subject: 53 chars exceeds hard max 50; cut at least 3'],
            id='suffix not at the end',
        ),
        pytest.param(
            'feat: ' + 'a' * 45,
            ['subject: 51 chars exceeds hard max 50; cut at least 1'],
            id='51, no suffix',
        ),
    ],
)
def test_a_squash_suffix_can_go_uncounted(subject: str, errors: list[str]) -> None:
    """With `allow_squash_suffix`, a trailing ` (#N)` does not count.

    A pull request merged into another pull request's branch leaves GitHub's squash
    commit, suffix included, among the commits a later check reads.
    """
    assert check_subject(subject, allow_squash_suffix=True).errors == errors


def test_a_typed_suffix_counts_by_default() -> None:
    """A title is measured as typed; GitHub appends its suffix only when squashing."""
    found = check_subject('feat: ' + 'a' * 44 + ' (#22)', label='title')
    assert found.errors == ['title: 56 chars exceeds hard max 50; cut at least 6']


@pytest.mark.parametrize('setting', ['off', 'OFF', ' Off ', 'none', 'false'])
def test_off_leaves_the_length_unchecked(setting: str) -> None:
    """`off`, `none` or `false`, in any case, means no maximum."""
    assert parse_max_length(setting) is None


@pytest.mark.parametrize(('setting', 'maximum'), [('72', 72), (' 50 ', 50), (60, 60)])
def test_a_positive_whole_number_is_the_maximum(
    setting: int | str, maximum: int
) -> None:
    """A positive whole number, as text or an integer, is the maximum."""
    assert parse_max_length(setting) == maximum


@pytest.mark.parametrize('setting', ['', 'sixty', '0', '-3', '3.5'])
def test_an_unusable_maximum_is_an_error(setting: str) -> None:
    """A setting that is neither a positive whole number nor `off` raises."""
    with pytest.raises(ValueError, match='positive whole number or off'):
        parse_max_length(setting)


def test_the_argparse_type_returns_the_parsed_maximum() -> None:
    """The `--max-length` type hands the check a number, or None for `off`."""
    assert max_length_argument('72') == 72
    assert max_length_argument('off') is None


# -- Warnings: judgments advise and never block --


def test_a_past_tense_first_word_warns_only() -> None:
    """A past-tense subject advises but does not block."""
    found = check_subject('feat: added a rule')
    assert found.ok
    assert found.warnings == ["subject: subject may not be imperative ('added')"]


@pytest.mark.parametrize(
    'subject',
    ['feat: adding a rule', 'feat: bringing in a rule', 'fix: trying the fallback'],
)
def test_a_gerund_first_word_warns_only(subject: str) -> None:
    """A gerund subject advises but does not block, a y before the -ing included."""
    found = check_subject(subject)
    assert found.ok
    assert any('imperative' in w for w in found.warnings)


@pytest.mark.parametrize(
    'subject',
    [
        'docs: bring the guide up to date',
        'feat: string the steps together',
        'fix: ping the host before the call',
    ],
)
def test_a_verb_ending_in_ing_is_not_a_gerund(subject: str) -> None:
    """A verb whose own ending is -ing, such as bring, raises no mood warning."""
    assert check_subject(subject).warnings == []


@pytest.mark.parametrize('plan_id', ['F5', 'S3', 'Phase 2', 'Slice 1a'])
def test_a_plan_identifier_is_not_reported_by_default(plan_id: str) -> None:
    """The plan identifier warning is off unless the caller asks for it."""
    assert not check_subject(f'feat: add {plan_id} probe').warnings


@pytest.mark.parametrize('plan_id', ['F5', 'S3', 'Phase 2', 'Slice 1a'])
def test_a_plan_identifier_warns_only_when_asked(plan_id: str) -> None:
    """With `warn_plan_ids`, a plan identifier advises but does not block."""
    found = check_subject(f'feat: add {plan_id} probe', warn_plan_ids=True)
    assert found.ok
    assert found.warnings == [
        'subject: contains a plan identifier; keep it out of the subject'
    ]
