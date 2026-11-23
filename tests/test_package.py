"""Smoke test: the package imports (keeps `make test` meaningful before the stages exist)."""

import etymo


def test_package_imports() -> None:
    assert etymo.__doc__
