"""Check a pull request title against the subject rules.

Usage:
    python -m pr_checks.title "feat: add config precedence"
    PR_TITLE="fix: guard empty body" python -m pr_checks.title
    python -m pr_checks.title --max-length 72 "fix: guard empty body"
    python -m pr_checks.title --max-length off --warn-plan-ids "fix: guard empty body"
"""

from __future__ import annotations

__all__ = ('main',)

import argparse
import os

from .subject import SUBJECT_MAX_DEFAULT, check_subject, max_length_argument


def main(argv: list[str] | None = None) -> int:
    """Check the title and return a process exit code."""
    parser = argparse.ArgumentParser(description='Check a pull request title.')
    parser.add_argument(
        'title',
        nargs='?',
        default=os.environ.get('PR_TITLE'),
        help='the title; falls back to the PR_TITLE environment variable',
    )
    parser.add_argument(
        '--max-length',
        type=max_length_argument,
        default=SUBJECT_MAX_DEFAULT,
        help=(
            'the most characters a title may have, or off to leave it unchecked '
            f'(default: {SUBJECT_MAX_DEFAULT})'
        ),
    )
    parser.add_argument(
        '--warn-plan-ids',
        action='store_true',
        help='warn on a plan identifier such as Phase 2 or S3',
    )
    args = parser.parse_args(argv)
    if not args.title:
        parser.error('provide a title argument or set PR_TITLE')

    found = check_subject(
        args.title,
        label='title',
        max_length=args.max_length,
        warn_plan_ids=args.warn_plan_ids,
    )
    unchecked = args.max_length is None
    return found.emit('title OK, length not checked' if unchecked else 'title OK')


if __name__ == '__main__':
    raise SystemExit(main())
