"""The rules every Conventional Commit subject line must follow.

A pull request title becomes the subject of its squash commit, so a title answers
to the same rules as a commit subject.
"""

from __future__ import annotations

__all__ = (
    'CONVENTIONAL_TYPES',
    'SUBJECT_MAX_DEFAULT',
    'check_subject',
    'max_length_argument',
    'parse_max_length',
)

import argparse
import re
from typing import cast

from .findings import Findings

CONVENTIONAL_TYPES = (
    'feat',
    'fix',
    'docs',
    'style',
    'refactor',
    'perf',
    'test',
    'build',
    'ci',
    'chore',
    'revert',
)
"""The types a subject may open with."""

# A scope may hold any text but a closing parenthesis, spaces and capitals included.
_CONVENTIONAL = re.compile(
    r'^(?:' + '|'.join(CONVENTIONAL_TYPES) + r')'
    r'(?:\([^)]+\))?!?: (?P<subject>.+)$'
)

# Matches every string, so an error can name the part that is wrong.
_LOOSE_FORM = re.compile(
    r'(?P<type>[^(!:\s]*)(?P<scope>\([^)]*\))?!?(?P<rest>.*)', re.DOTALL
)

SUBJECT_MAX_DEFAULT = 50
"""The most characters a subject line may have unless the caller sets another number.

git-commit(1) asks for "a single short (no more than 50 characters) line".
"""

# `false` is among them because a YAML boolean false reaches an action as 'false'.
_UNCHECKED = frozenset({'off', 'none', 'false'})

_NON_IMPERATIVE = frozenset(
    {
        'added',
        'adds',
        'fixed',
        'fixes',
        'updated',
        'updates',
        'removed',
        'removes',
        'changed',
        'changes',
        'refactored',
        'renamed',
        'moved',
        'deleted',
        'created',
        'implemented',
        'introduced',
        'bumped',
        'merged',
    }
)

# A vowel before -ing: matches adding, not bring or string.
_ING_FORM = re.compile(r'[aeiouy].*ing$')

_PLAN_ID = re.compile(r'\b(?:F\d+|S\d+|Phase\s*\d+|Slice\s*\w+)\b')

_TICKET_KEY = re.compile(r'^\[[A-Z][A-Z0-9]*-[0-9]+\] ')

# GitHub appends ' (#N)' to a squash commit's subject. The author did not type it.
_SQUASH_SUFFIX = re.compile(r' \(#\d+\)$')


def _looks_non_imperative(first_word: str) -> bool:
    """Whether the first word reads as past tense, third person or an -ing form."""
    low = first_word.lower()
    return low in _NON_IMPERATIVE or _ING_FORM.search(low) is not None


def _form_problem(subject_line: str) -> str:
    """Return the first part of a subject that breaks the Conventional Commit form."""
    parts = cast('re.Match[str]', _LOOSE_FORM.fullmatch(subject_line))
    kind, scope, rest = parts['type'], parts['scope'], parts['rest']
    if kind not in CONVENTIONAL_TYPES:
        if kind.lower() in CONVENTIONAL_TYPES:
            return f"the type '{kind}' must be lowercase"
        return (
            f"'{kind}' is not a type (types: {', '.join(CONVENTIONAL_TYPES)})"
            if ':' in subject_line
            else "there is no 'type: ' prefix"
        )
    if scope == '()':
        return 'the scope must not be empty'
    head = subject_line[: len(subject_line) - len(rest)]
    return (
        f"nothing follows '{head}: '"
        if rest.startswith(': ')
        else f"'{head}' must be followed by ': ' (a colon, then a space)"
    )


def parse_max_length(setting: int | str) -> int | None:
    """Parse a positive whole number, or `off`, `none` or `false` in any case as None.

    Raises:
        ValueError: The setting is neither a positive whole number nor `off`.
    """
    text = str(setting).strip()
    if text.lower() in _UNCHECKED:
        return None
    if text.isdigit() and int(text) > 0:
        return int(text)
    message = f'expected a positive whole number or off, not {setting!r}'
    raise ValueError(message)


def max_length_argument(text: str) -> int | None:
    """Parse a `--max-length` value for argparse.

    Raises:
        argparse.ArgumentTypeError: parse_max_length rejects the value.
    """
    try:
        return parse_max_length(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def check_subject(
    subject_line: str,
    *,
    label: str = 'subject',
    max_length: int | None = SUBJECT_MAX_DEFAULT,
    allow_squash_suffix: bool = False,
    warn_plan_ids: bool = False,
) -> Findings:
    """Validate one Conventional Commit subject line.

    Args:
        subject_line: The title or the commit subject.
        label: The name each finding opens with, such as `title`.
        max_length: The most characters the line may have; None leaves the length
            unchecked and keeps every other rule.
        allow_squash_suffix: Do not count a trailing ` (#N)`, which GitHub appends
            to a squash commit's subject.
        warn_plan_ids: Warn on an identifier such as `Phase 2`, `Slice 1a`, `S3` or
            `F1`. The pattern also matches names such as Amazon S3.
    """
    found = Findings()
    match = _CONVENTIONAL.match(subject_line)
    if match is None:
        found.errors.append(
            f"{label}: not Conventional Commit form 'type(scope): subject', "
            f'because {_form_problem(subject_line)}'
        )
        return found

    subject = match['subject']

    first_word = _TICKET_KEY.sub('', subject, count=1).partition(' ')[0]
    measured = (
        _SQUASH_SUFFIX.sub('', subject_line, count=1)
        if allow_squash_suffix
        else subject_line
    )
    length = len(measured)
    if max_length is not None and length > max_length:
        found.errors.append(
            f'{label}: {length} chars exceeds hard max {max_length}; '
            f'cut at least {length - max_length}'
        )
    if subject_line.endswith('.'):
        found.errors.append(f'{label}: must not end with a period')
    if first_word[:1].isupper():
        found.errors.append(
            f"{label}: subject must start lowercase ('{first_word}'); if that word "
            'is a name or an acronym, open on another word'
        )

    if _looks_non_imperative(first_word):
        found.warnings.append(
            f"{label}: subject may not be imperative ('{first_word}')"
        )
    if warn_plan_ids and _PLAN_ID.search(subject):
        found.warnings.append(
            f'{label}: contains a plan identifier; keep it out of the subject'
        )
    return found
