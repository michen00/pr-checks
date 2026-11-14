r"""Run the enabled checks on one pull request, as the action does.

The title, body and author come from the environment, as PR_TITLE, PR_BODY and
PR_AUTHOR, so text the pull request's author wrote never reaches a command line.

With `--findings-dir`, the findings are written there for the comment action:

- `format` holds the layout's version, `1`.
- `errors/<check>.txt` holds a check's errors, one per line.
- `warnings/<check>.txt` holds its warnings, one per line.

`format` is written last, after every check has finished, so a directory without it
holds no complete result.

Usage:
    PR_TITLE='feat: add a rule' PR_BODY="$(cat body.md)" python -m pr_checks \\
        --required-sections $'Summary\\nTesting'
"""

from __future__ import annotations

__all__ = ('FINDINGS_FORMAT', 'main')

import argparse
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .body import check_body
from .subject import SUBJECT_MAX_DEFAULT, check_subject, max_length_argument

if TYPE_CHECKING:
    from .findings import Findings

FINDINGS_FORMAT = 1
"""The version of the findings directory's layout. A change to it is a major release."""


def _boolean(text: str) -> bool:
    """Parse an action input's `true` or `false`, in any case."""
    value = text.strip().lower()
    if value not in {'true', 'false'}:
        message = f'expected true or false, not {text!r}'
        raise argparse.ArgumentTypeError(message)
    return value == 'true'


def _findings_dir(text: str) -> Path:
    """Resolve the findings directory, which must be under the checkout or a temp dir.

    The path is input, and CodeQL's py/path-injection query treats it as such.
    """
    roots = tuple(
        os.path.realpath(root).rstrip(os.sep) + os.sep
        for root in (
            str(Path.cwd()),
            os.environ.get('RUNNER_TEMP', ''),
            tempfile.gettempdir(),
        )
        if root
    )
    resolved = os.path.realpath(text)
    if not (resolved + os.sep).startswith(roots):
        message = f'{text} is not under {", ".join(roots)}'
        raise argparse.ArgumentTypeError(message)
    return Path(resolved)


def _parser() -> argparse.ArgumentParser:
    """Return the command line's parser."""
    parser = argparse.ArgumentParser(
        prog='python -m pr_checks', description='Check a pull request.'
    )
    parser.add_argument(
        '--findings-dir',
        type=_findings_dir,
        help='write the findings here; nothing is written when omitted',
    )
    parser.add_argument(
        '--max-length',
        type=max_length_argument,
        default=SUBJECT_MAX_DEFAULT,
        help=(
            'the most characters the title may have, or off '
            f'(default: {SUBJECT_MAX_DEFAULT})'
        ),
    )
    parser.add_argument(
        '--required-sections',
        default='',
        help='level-two headings the body should have, one per line (default: none)',
    )
    for flag, default, help_text in (
        ('--check-title', True, 'check the title'),
        ('--check-body', True, 'check the body'),
        ('--skip-bot-authors', True, 'check nothing when the author ends in [bot]'),
        ('--warn-plan-ids', False, 'warn on a plan identifier such as Phase 2'),
    ):
        parser.add_argument(
            flag,
            type=_boolean,
            default=default,
            metavar='{true,false}',
            help=f'{help_text} (default: {str(default).lower()})',
        )
    return parser


def _verdict(check: str, found: Findings, *, length_checked: bool) -> str:
    """Return the line that says how a check ended."""
    if not found.ok:
        return f'{check}: {len(found.errors)} error(s)'
    verdict = f'{check} OK'
    if found.warnings:
        verdict += ' (with warnings)'
    if not length_checked:
        verdict += ', length not checked'
    return verdict


def _record(results: dict[str, Findings], directory: Path) -> None:
    """Write every check's findings, then the format file that marks them complete."""
    directory.mkdir(parents=True, exist_ok=True)
    for check, found in results.items():
        found.record(directory, check)
    (directory / 'format').write_text(f'{FINDINGS_FORMAT}\n', encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    """Run the enabled checks and return a process exit code."""
    parser = _parser()
    args = parser.parse_args(argv)
    author = os.environ.get('PR_AUTHOR', '')
    results: dict[str, Findings] = {}
    if args.skip_bot_authors and author.endswith('[bot]'):
        print(f'{author} is a bot, so no check runs')
    else:
        if args.check_title:
            title = os.environ.get('PR_TITLE', '')
            if not title:
                parser.error('PR_TITLE is empty; the title check needs a title')
            results['title'] = check_subject(
                title,
                label='title',
                max_length=args.max_length,
                warn_plan_ids=args.warn_plan_ids,
            )
        if args.check_body:
            sections = [
                line.strip()
                for line in args.required_sections.splitlines()
                if line.strip()
            ]
            results['body'] = check_body(os.environ.get('PR_BODY', ''), sections)
    for check, found in results.items():
        found.publish()
        length_checked = check != 'title' or args.max_length is not None
        print(_verdict(check, found, length_checked=length_checked))
    if args.findings_dir is not None:
        _record(results, args.findings_dir)
    return 0 if all(found.ok for found in results.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
