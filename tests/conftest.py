"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def sample_file_id() -> str:
    """Sample file_id for testing."""
    return "active436"
