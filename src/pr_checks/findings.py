"""What a check found, and how its findings reach a reader.

Errors block and warnings advise. A check reports a problem as an error only when
it detects the problem exactly and the author can always fix it; a heuristic
finding is a warning.
"""

from __future__ import annotations

__all__ = ('Findings',)

import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _command_data(message: str) -> str:
    """Escape a workflow command's message, as GitHub's own toolkit does.

    An unescaped newline in a finding would start a second command.
    """
    return message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def _publish(severity: str, message: str) -> None:
    """Print one finding, as a workflow annotation under GitHub Actions.

    An annotation reaches the Checks tab and the run summary; a plain line reaches
    only the job log. GitHub reads workflow commands from stdout.
    """
    if os.environ.get('GITHUB_ACTIONS', ''):
        print(f'::{severity}::{_command_data(message)}')
    else:
        print(f'{severity}: {message}', file=sys.stderr)


@dataclass(slots=True)
class Findings:
    """Result of a check: errors block, warnings advise."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: Findings) -> None:
        """Fold another result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    @property
    def ok(self) -> bool:
        """Whether there are no errors."""
        return not self.errors

    def publish(self) -> None:
        """Print every finding, the warnings first."""
        for warning in self.warnings:
            _publish('warning', warning)
        for error in self.errors:
            _publish('error', error)

    def emit(self, ok_message: str) -> int:
        """Print the findings, and `ok_message` if nothing blocks.

        Returns:
            0 when nothing blocks, warnings or not; 1 otherwise.
        """
        self.publish()
        if self.ok:
            suffix = ' (with warnings)' if self.warnings else ''
            print(f'{ok_message}{suffix}')
            return 0
        return 1

    def record(self, directory: Path, check: str) -> None:
        """Write the findings to `errors/<check>.txt` and `warnings/<check>.txt`.

        Each file holds one finding per line, and a kind with no findings writes no
        file.
        """
        for kind, items in (('errors', self.errors), ('warnings', self.warnings)):
            if items:
                path = directory / kind / f'{check}.txt'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    ''.join(f'{item}\n' for item in items), encoding='utf-8'
                )
