"""Print the package's runtime dependencies from uv.lock, pinned and hashed for pip.

The action installs them with `pip install --require-hashes --only-binary=:all:`, so
uv.lock, which Dependabot updates, is the one place the versions and hashes live.
This module uses only the standard library: the action runs it before anything is
installed.

Usage:
    python -m pr_checks.requirements uv.lock > requirements.txt
"""

from __future__ import annotations

__all__ = ('main', 'requirements')

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any

_PROJECT = 'pr-checks'
_LOCK_VERSION = 1


def _closure(packages: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the project's runtime dependencies and theirs, each once, by name."""
    seen: dict[str, dict[str, Any]] = {}
    pending = list(packages[_PROJECT].get('dependencies', []))
    while pending:
        dependency = pending.pop()
        if 'extra' in dependency or 'marker' in dependency:
            message = f'{dependency["name"]}: extras and markers are not supported'
            raise ValueError(message)
        name = dependency['name']
        if name in seen:
            continue
        seen[name] = packages[name]
        pending.extend(packages[name].get('dependencies', []))
    return [seen[name] for name in sorted(seen)]


def requirements(lock: str) -> str:
    """Return a requirements file for the project's runtime dependencies in `lock`.

    Each package is pinned to its locked version with the hash of every wheel the
    lock records.

    Raises:
        ValueError: The lock is another version, or a dependency comes from
            somewhere other than a package index or has no wheel.
    """
    document = tomllib.loads(lock)
    if document.get('version') != _LOCK_VERSION:
        message = (
            f'expected uv.lock version {_LOCK_VERSION}, not {document.get("version")}'
        )
        raise ValueError(message)
    packages = {package['name']: package for package in document['package']}
    entries = []
    for package in _closure(packages):
        name, version = package['name'], package['version']
        if 'registry' not in package['source']:
            message = f'{name}: not from a package index'
            raise ValueError(message)
        hashes = [f'--hash={wheel["hash"]}' for wheel in package.get('wheels', [])]
        if not hashes:
            message = f'{name}: the lock records no wheel'
            raise ValueError(message)
        entries.append(' \\\n    '.join([f'{name}=={version}', *hashes]) + '\n')
    return ''.join(entries)


def main(argv: list[str] | None = None) -> int:
    """Print the requirements and return a process exit code."""
    parser = argparse.ArgumentParser(
        description='Print the runtime dependencies from uv.lock, pinned and hashed.'
    )
    parser.add_argument('lock', type=Path, help='path to uv.lock')
    args = parser.parse_args(argv)
    try:
        sys.stdout.write(requirements(args.lock.read_text(encoding='utf-8')))
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
