"""A smoke test that the package installs and imports."""

import importlib

__all__ = ()


def test_the_package_imports_with_a_docstring() -> None:
    """The installed package imports and says what it is."""
    package = importlib.import_module('pr_checks')
    assert package.__doc__ is not None
    assert package.__doc__.strip() != ''
