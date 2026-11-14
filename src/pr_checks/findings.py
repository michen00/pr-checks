"""What a check found, and how its findings reach a reader.

Errors block and warnings advise. A check reports a problem as an error only when
it detects the problem exactly and the author can always fix it; a heuristic
finding is a warning.
"""

from __future__ import annotations

__all__ = ('Findings',)

import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def _command_data(message: str) -> str:
    """Escape a workflow command's message, as GitHub's own toolkit does.

    An unescaped newline in a finding would start a second command.
    """
    return message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def _record_roots() -> tuple[str, ...]:
    """Return the checkout and temporary directories, each ending in a separator."""
    roots = (str(Path.cwd()), os.environ.get('RUNNER_TEMP', ''), tempfile.gettempdir())
    return tuple(
        os.path.realpath(root).rstrip(os.sep) + os.sep for root in roots if root
    )


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

    def _publish(self, severity: str, message: str) -> None:
        """Print one finding, as a workflow annotation under GitHub Actions.

        An annotation reaches the Checks tab and the run summary; a plain line
        reaches only the job log. GitHub reads workflow commands from stdout.
        """
        if os.environ.get('GITHUB_ACTIONS', ''):
            print(f'::{severity}::{_command_data(message)}')
        else:
            print(f'{severity}: {message}', file=sys.stderr)

    def _record_to(self, env_var: str, items: Sequence[str], *, label: str) -> None:
        """Append `items` to the file `env_var` names, warning if refused or failed.

        A filesystem error becomes a warning rather than an exception: the job log
        keeps every finding, so a lost file must not fail a check that passed.
        """
        target = os.environ.get(env_var, '').strip()
        if not target or not items:
            return
        # The path is environment input (CodeQL py/path-injection).
        resolved = os.path.realpath(target)
        roots = _record_roots()
        if not resolved.startswith(roots):
            self._publish(
                'warning',
                f'could not record {label} to {target}: not under {", ".join(roots)}',
            )
            return
        path = Path(resolved)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a', encoding='utf-8') as handle:
                handle.writelines(f'{item}\n' for item in items)
        except OSError as exc:
            self._publish('warning', f'could not record {label} to {path}: {exc}')

    def emit(self, ok_message: str) -> int:
        """Print and record the findings, and return a process exit code.

        The warnings are appended to the file `PR_WARNINGS_FILE` names and the
        errors to the file `PR_ERRORS_FILE` names, when each is set. A check with
        nothing to record writes no file.

        Returns:
            0 when nothing blocks, warnings or not; 1 otherwise.
        """
        for warning in self.warnings:
            self._publish('warning', warning)
        for error in self.errors:
            self._publish('error', error)
        self._record_to('PR_WARNINGS_FILE', self.warnings, label='warnings')
        self._record_to('PR_ERRORS_FILE', self.errors, label='errors')
        if self.ok:
            suffix = ' (with warnings)' if self.warnings else ''
            print(f'{ok_message}{suffix}')
            return 0
        return 1
