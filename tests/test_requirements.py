"""Tests for the requirements the action installs, read from uv.lock."""

from pathlib import Path

import pytest

from pr_checks import requirements as requirements_module
from pr_checks.requirements import requirements

__all__ = ()

_ROOT = Path(__file__).resolve().parents[1]

_LOCK = """\
version = 1
revision = 3

[[package]]
name = "pr-checks"
version = "0.0.0"
source = { editable = "." }
dependencies = [{ name = "alpha" }]

[package.dev-dependencies]
test = [{ name = "pytest" }]

[[package]]
name = "alpha"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [{ name = "beta" }]
wheels = [
    { url = "https://example.invalid/alpha.whl", hash = "sha256:aa" },
]

[[package]]
name = "beta"
version = "2.0.0"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://example.invalid/beta-312.whl", hash = "sha256:b1" },
    { url = "https://example.invalid/beta-313.whl", hash = "sha256:b2" },
]

[[package]]
name = "pytest"
version = "9.0.0"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://example.invalid/pytest.whl", hash = "sha256:cc" },
]
"""


def test_the_runtime_closure_is_pinned_with_every_wheel_hash() -> None:
    """Each runtime dependency, direct or not, is pinned with each wheel's hash.

    A development dependency is left out.
    """
    assert requirements(_LOCK) == (
        'alpha==1.0.0 \\\n'
        '    --hash=sha256:aa\n'
        'beta==2.0.0 \\\n'
        '    --hash=sha256:b1 \\\n'
        '    --hash=sha256:b2\n'
    )


def test_a_dependency_reached_twice_is_listed_once() -> None:
    """A package both the project and another dependency need appears once."""
    lock = _LOCK.replace(
        'dependencies = [{ name = "alpha" }]',
        'dependencies = [{ name = "alpha" }, { name = "beta" }]',
    )
    assert requirements(lock) == requirements(_LOCK)


def test_the_lock_in_this_repository_yields_markdown_it_py() -> None:
    """The real uv.lock names the body check's parser and its dependency."""
    text = requirements((_ROOT / 'uv.lock').read_text(encoding='utf-8'))
    names = [line.split('==')[0] for line in text.splitlines() if '==' in line]
    assert names == ['markdown-it-py', 'mdurl']
    assert text.count('--hash=sha256:') >= 2


@pytest.mark.parametrize(
    ('change', 'message'),
    [
        pytest.param(
            ('version = 1', 'version = 2'), 'expected uv.lock version 1', id='version'
        ),
        pytest.param(
            (
                '{ name = "beta" }',
                '{ name = "beta", marker = "sys_platform == \'linux\'" }',
            ),
            'beta: extras and markers are not supported',
            id='marker',
        ),
        pytest.param(
            (
                'source = { registry = "https://pypi.org/simple" }\ndependencies',
                'source = { git = "https://example.invalid/alpha" }\ndependencies',
            ),
            'alpha: not from a package index',
            id='git source',
        ),
    ],
)
def test_a_lock_the_action_cannot_install_from_is_refused(
    change: tuple[str, str], message: str
) -> None:
    """A lock the installer would misread raises rather than guessing."""
    with pytest.raises(ValueError, match=message):
        requirements(_LOCK.replace(*change, 1))


def test_a_package_without_a_wheel_is_refused() -> None:
    """The action installs wheels only, so a package with none cannot be installed."""
    lock = _LOCK.replace(
        'wheels = [\n    { url = "https://example.invalid/alpha.whl", '
        'hash = "sha256:aa" },\n]\n',
        '',
    )
    with pytest.raises(ValueError, match='alpha: the lock records no wheel'):
        requirements(lock)


def test_the_command_prints_the_requirements(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command line prints what `requirements` returns."""
    lock = tmp_path / 'uv.lock'
    lock.write_text(_LOCK, encoding='utf-8')

    assert requirements_module.main([str(lock)]) == 0
    assert capsys.readouterr().out == requirements(_LOCK)


def test_the_command_reports_a_refused_lock(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refused lock is a usage error naming the problem."""
    lock = tmp_path / 'uv.lock'
    lock.write_text(_LOCK.replace('version = 1', 'version = 2', 1), encoding='utf-8')

    with pytest.raises(SystemExit) as stopped:
        requirements_module.main([str(lock)])

    assert stopped.value.code == 2
    assert 'expected uv.lock version 1, not 2' in capsys.readouterr().err
