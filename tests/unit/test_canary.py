"""Canary test to verify toolchain is working."""

from vibe_check import __version__


def test_version_exists() -> None:
    """Package version should be defined."""
    assert __version__ is not None
    assert isinstance(__version__, str)


def test_version_format() -> None:
    """Version should follow semver-like format."""
    parts = __version__.split(".")
    assert len(parts) >= 2  # At least major.minor
    assert all(part.isdigit() for part in parts[:2])
