"""Check a pull request body for its expected sections and leftover template text.

A fenced code block without a language tag is an error, because the author can
always add one: `text` fits a block that is not code. Every other finding is a
warning, because each can have a legitimate exception: a missing section, which a
small change may not need, and leftover placeholders, TBD or TODO markers, and
markdownlint directive comments. The placeholder, marker and directive scans read
the body with its code removed, so a token quoted as an example is not reported.

The caller names the level-two headings to expect; by default the check expects
none.

Usage:
    python -m pr_checks.body --body-file body.md --require Summary Testing
    gh pr view 12 --json body -q .body | python -m pr_checks.body
"""

from __future__ import annotations

__all__ = ('check_body', 'main')

import argparse
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from markdown_it import MarkdownIt

from .findings import Findings

if TYPE_CHECKING:
    from collections.abc import Sequence

_HTML_TAGS = frozenset(
    {
        'b',
        'br',
        'code',
        'details',
        'em',
        'hr',
        'i',
        'kbd',
        'sub',
        'summary',
        'sup',
    }
)
# Neither pattern backtracks across a long run of `<` or backticks.
_PLACEHOLDER = re.compile(r'<([^<>\n]+)>')
_INLINE_CODE = re.compile(r'(?<!`)(?P<ticks>`+)(?!`).+?(?<!`)(?P=ticks)(?!`)')
_TBD = re.compile(r'\b(?:TBD|TODO)\b')
# CommonMark without extensions: GFM's add nothing to how code blocks are found.
_PARSER = MarkdownIt('commonmark')
_CODE_BLOCKS = frozenset({'fence', 'code_block'})
_MARKDOWNLINT = re.compile(
    r'<!--\s*markdownlint-(?:disable|enable|capture|restore|configure-file)\b[^>]*-->'
)


def _unfilled_placeholder(text: str) -> str | None:
    """Return the first unfilled angle-bracket placeholder, or None.

    It returns the slot so the finding can say which one to fill. An HTML tag the
    author meant to keep, such as `<details>`, is skipped.
    """
    for match in _PLACEHOLDER.finditer(text):
        inner = match.group(1).strip().lstrip('/')
        first = inner.split(maxsplit=1)[0].lower() if inner else ''
        if first in _HTML_TAGS:
            continue
        if inner[:1].isalpha():
            return match.group(0)
    return None


def _markdownlint_scaffolding(text: str) -> str | None:
    """Return the first markdownlint directive comment in the body, or None.

    GitHub does not lint a pull request body, so a directive in one is left over
    from a template. The scan is line by line, so a match never spans a newline.
    """
    for line in text.splitlines():
        if (match := _MARKDOWNLINT.search(line)) is not None:
            return match.group(0)
    return None


def _lines(body: str) -> list[str]:
    """Split the body as the parser does, so its line numbers index this list.

    `str.splitlines` also breaks on form feeds and Unicode separators, which the
    parser leaves inside a line.
    """
    return body.replace('\r\n', '\n').replace('\r', '\n').split('\n')


def _strip_code(body: str) -> str:
    """Return the body with code blocks dropped and inline code spans blanked out."""
    code: set[int] = set()
    for token in _PARSER.parse(body):
        if token.type in _CODE_BLOCKS and token.map is not None:
            code.update(range(*token.map))
    return '\n'.join(
        _INLINE_CODE.sub(' ', line)
        for number, line in enumerate(_lines(body))
        if number not in code
    )


def _has_unlabeled_fence(body: str) -> bool:
    """Whether a fenced code block has no language tag.

    The parser decides what is a fence: a run of backticks inside a longer fence,
    an indented code block or an HTML block is content, and only the whole block
    structure tells them apart.
    """
    return any(
        token.type == 'fence' and not token.info.strip()
        for token in _PARSER.parse(body)
    )


def _has_heading(body: str, section: str) -> bool:
    """Whether the body has a level-two heading whose text starts with the section."""
    pattern = rf'^##[ \t]+{re.escape(section)}\b'
    return re.search(pattern, body, re.IGNORECASE | re.MULTILINE) is not None


def check_body(body: str, required: Sequence[str] = ()) -> Findings:
    """Check a pull request body for the `required` sections and leftover text."""
    found = Findings()
    found.warnings.extend(
        f"missing template section '## {section}' — add it unless the change is too "
        'small to need one'
        for section in required
        if not _has_heading(body, section)
    )
    prose = _strip_code(body)
    if (slot := _unfilled_placeholder(prose)) is not None:
        found.warnings.append(
            f'unfilled template placeholder {slot} — replace it with the real value, '
            'or delete the line'
        )
    if (marker := _TBD.search(prose)) is not None:
        found.warnings.append(
            f'a {marker.group(0)} marker is still in the body — resolve it, or say in '
            'the body why it stays'
        )
    if (directive := _markdownlint_scaffolding(prose)) is not None:
        found.warnings.append(
            f'leftover markdownlint directive {directive} — delete it, and its line '
            'too when the line holds nothing else'
        )
    if _has_unlabeled_fence(body):
        found.errors.append(
            'a fenced code block has no language tag — add one, using text when the '
            'block is not code'
        )
    return found


def main(argv: list[str] | None = None) -> int:
    """Check the body and return a process exit code."""
    parser = argparse.ArgumentParser(description='Check a pull request body.')
    parser.add_argument(
        '--body-file',
        type=Path,
        help='path to the body; reads standard input when omitted',
    )
    parser.add_argument(
        '--require',
        nargs='*',
        default=[],
        metavar='SECTION',
        help='level-two headings to expect (default: none)',
    )
    args = parser.parse_args(argv)
    if args.body_file:
        body = args.body_file.read_text(encoding='utf-8')
    else:
        body = sys.stdin.read()
    return check_body(body, args.require).emit('body OK')


if __name__ == '__main__':
    raise SystemExit(main())
